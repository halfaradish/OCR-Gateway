import {
  BASE,
  clickButtonWithText,
  createReporter,
  launch,
  login,
  shot,
  waitForText,
} from "./support.mjs";

const reporter = createReporter();
const { check } = reporter;

async function bodyText(page) {
  return page.evaluate(() => document.body.innerText);
}

async function waitForBody(page, text, timeout = 10_000) {
  await page.waitForFunction(
    (expected) => document.body.innerText.includes(expected),
    { timeout },
    text,
  );
}

const browser = await launch();
try {
  const page = await browser.newPage();
  reporter.attach(page);

  let slowStatus = true;
  let failStatus = false;
  await page.setRequestInterception(true);
  page.on("request", async (request) => {
    if (request.url().includes("/api/admin/local-ocr/status")) {
      if (slowStatus) {
        slowStatus = false;
        await new Promise((resolve) => setTimeout(resolve, 2500));
      } else if (failStatus) {
        await request.respond({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            error: { code: "INTERNAL_ERROR", message: "status unavailable" },
          }),
        });
        return;
      }
    }
    await request.continue();
  });

  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await login(page);
  await page.waitForFunction(() => location.pathname === "/", { timeout: 10_000 });

  await page.goto(`${BASE}/settings`, { waitUntil: "domcontentloaded" });
  await waitForText(page, "h1", "设置");
  await waitForBody(page, "本地 OCR");
  check("local OCR card is visible", true);

  const settingsEditable = await page.$eval(
    "#cache_ttl_seconds",
    (element) => !element.disabled,
  );
  const hasSkeleton = await page.evaluate(
    () => document.querySelector(".animate-pulse") !== null,
  );
  check("settings stay editable while local status is slow", settingsEditable);
  check("local status shows a skeleton while loading", hasSkeleton);

  const switchSelector = 'button[aria-label="启用本地 OCR"]';
  await waitForBody(page, "已停止", 15_000);
  const disabled = await page.$eval(switchSelector, (element) => element.disabled);
  check("local OCR switch is enabled when the extra is installed", disabled === false);
  if (disabled) {
    throw new Error("local extra is not installed in this environment");
  }

  await page.click(switchSelector);
  await clickButtonWithText(page, "保存设置");
  await waitForBody(page, "设置已保存");
  await page.waitForFunction(
    () => document.body.innerText.includes("就绪"),
    { timeout: 60_000 },
  );
  check("local OCR reaches ready after enable", true);
  const readyText = await bodyText(page);
  check("local OCR card shows the bundled model", readyText.includes("PP-OCRv6"));
  await shot(page, "local-ocr-ready");

  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForBody(page, "本地 OCR");
  const checked = await page.$eval(switchSelector, (element) =>
    element.getAttribute("aria-checked"),
  );
  check("local OCR switch persists", checked === "true");
  await page.waitForFunction(
    () => document.body.innerText.includes("就绪"),
    { timeout: 60_000 },
  );
  check("local OCR is ready after reload", true);

  await page.click(switchSelector);
  await clickButtonWithText(page, "保存设置");
  await waitForBody(page, "设置已保存");
  await page.waitForFunction(
    () => document.body.innerText.includes("已停止"),
    { timeout: 30_000 },
  );
  check("local OCR stops after disable", true);

  // Error state: failed status fetches show the inline error + retry.
  failStatus = true;
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForBody(page, "本地状态暂不可用", 20_000);
  check("local status shows an inline error", true);
  failStatus = false;
  const retried = await page.evaluate(() => {
    const button = Array.from(document.querySelectorAll("button")).find((item) =>
      (item.textContent ?? "").includes("重试"),
    );
    button?.click();
    return Boolean(button);
  });
  check("local status offers a retry", retried);
  await waitForBody(page, "已停止", 15_000);
  check("local status recovers after retry", true);

  await page.setViewport({ width: 480, height: 900 });
  const switchVisible = await page.$eval(
    switchSelector,
    (element) => element.getBoundingClientRect().width > 0,
  );
  check("local OCR switch stays visible on a narrow viewport", switchVisible);
  await shot(page, "local-ocr-narrow");
} finally {
  await browser.close();
}
reporter.finish();
