import {
  BASE,
  clickButtonWithText,
  clickDialogButton,
  clickRowButton,
  createReporter,
  launch,
  login,
  shot,
  waitForText,
} from "./support.mjs";

const reporter = createReporter();
const { check } = reporter;

async function goto(page, route) {
  await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
}

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

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function fill(page, selector, value) {
  await page.waitForSelector(selector);
  await page.click(selector);
  await page.keyboard.down("Control");
  await page.keyboard.press("KeyA");
  await page.keyboard.up("Control");
  if (value === "") await page.keyboard.press("Backspace");
  else await page.type(selector, value);
}

const browser = await launch();
try {
  const page = await browser.newPage();
  reporter.attach(page);
  await page.evaluateOnNewDocument(() => {
    window.__csvBlob = null;
    const original = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (blob) => {
      window.__csvBlob = blob;
      return original(blob);
    };
  });
  page.on("dialog", (dialog) => void dialog.accept());

  await goto(page, "/login");
  await login(page);
  await waitForText(page, "h1", "总览", 15_000);

  // ───────────────────────── 账号页 ─────────────────────────
  await goto(page, "/accounts");
  await waitForText(page, "h1", "账号");
  await clickButtonWithText(page, "新建账号");
  await fill(page, "#name", "e2e-baidu");
  await fill(page, "#credential-app_id", "10001");
  await fill(page, "#credential-api_key", "AK-e2e");
  await fill(page, "#credential-secret_key", "SK-e2e");
  await clickDialogButton(page, "保存");
  await waitForBody(page, "e2e-baidu");
  check("account create", true);
  check(
    "unconfigured quota hint",
    (await bodyText(page)).includes("未配置额度，可能超用"),
  );
  await shot(page, "10-accounts");

  await clickRowButton(page, "e2e-baidu", "编辑");
  await fill(page, "#quota_monthly", "200");
  await clickDialogButton(page, "保存");
  await waitForBody(page, "/ 200");
  check("account edit with blank credentials keeps them", true);

  const storedTimeout = await page.evaluate(async () => {
    const response = await fetch("/api/admin/accounts", { credentials: "same-origin" });
    const rows = await response.json();
    return rows.find((row) => row.name === "e2e-baidu")?.timeout_ms ?? null;
  });
  check("blank timeout keeps the stored value", storedTimeout === 8000, String(storedTimeout));

  await clickRowButton(page, "e2e-baidu", "测活");
  await waitForBody(page, "测活结果");
  await waitForBody(page, "错误码", 30_000);
  check("account test shows a failure result", true);
  await clickDialogButton(page, "关闭");

  await clickRowButton(page, "e2e-baidu", "重置");
  await waitForBody(page, "清零");
  check("reset confirm mentions quota reset", true);
  await clickDialogButton(page, "取消");

  await page.select("#provider-filter", "tencent");
  await page.waitForFunction(
    () => !document.body.innerText.includes("e2e-baidu"),
    { timeout: 5000 },
  );
  check("provider filter applies", true);
  await page.select("#provider-filter", "");
  await waitForBody(page, "e2e-baidu");

  await clickRowButton(page, "e2e-baidu", "删除");
  await waitForBody(page, "删除账号");
  await clickDialogButton(page, "删除");
  await page.waitForFunction(
    () => !document.body.innerText.includes("e2e-baidu"),
    { timeout: 10_000 },
  );
  check("account delete", true);

  // ───────────────────── 成员与 Key 页 ─────────────────────
  await goto(page, "/members");
  await waitForText(page, "h1", "成员与 Key");
  await clickButtonWithText(page, "新建成员");
  await fill(page, "#member-name", "e2e-member");
  await clickDialogButton(page, "创建");
  await waitForBody(page, "e2e-member");
  check("member create", true);

  await clickButtonWithText(page, "创建 Key");
  await fill(page, "#key-name", "e2e-key");
  await clickDialogButton(page, "创建");
  await waitForBody(page, "Key 已创建");
  const plaintext = await page.evaluate(() => {
    const node = document.querySelector("code");
    return node?.textContent ?? "";
  });
  check("key plaintext shown once", plaintext.startsWith("ocr_") && plaintext.length > 20);
  await clickDialogButton(page, "我已保存");
  await waitForBody(page, "e2e-key");

  const keysText = await bodyText(page);
  check("key list shows only the prefix", !keysText.includes(plaintext));
  check("key list shows the prefix", /ocr_\S+…/.test(keysText));
  await shot(page, "11-members");

  await clickRowButton(page, "e2e-member", "删除");
  await waitForBody(page, "会一并吊销");
  const cascadeText = await bodyText(page);
  check("member delete warns about cascade", /个 Key 会一并吊销/.test(cascadeText));
  await clickDialogButton(page, "删除成员");
  await page.waitForFunction(
    () => !document.body.innerText.includes("e2e-member"),
    { timeout: 10_000 },
  );
  check("member delete", true);

  // ───────────────────────── 用量页 ─────────────────────────
  await goto(page, "/usage");
  await waitForText(page, "h1", "用量");
  await waitForBody(page, "汇总");
  const beforeUrl = page.url();
  await page.select("#usage-provider", "tencent");
  await page.waitForFunction(() => window.location.search.includes("provider=tencent"));
  check("usage filter goes into the URL", page.url() !== beforeUrl);

  await clickButtonWithText(page, "按成员");
  await page.waitForFunction(() => window.location.search.includes("group=user"));
  await waitForBody(page, "Ming");
  check("usage group switch updates the table", true);
  await shot(page, "12-usage");

  await clickButtonWithText(page, "导出 CSV");
  await new Promise((resolve) => setTimeout(resolve, 400));
  const csv = await page.evaluate(async () => {
    const blob = window.__csvBlob;
    if (!blob) return null;
    const bytes = new Uint8Array(await blob.arrayBuffer());
    // `Blob.text()` strips a leading BOM, so inspect the raw bytes instead.
    return {
      hasBom: bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf,
      text: new TextDecoder().decode(bytes),
    };
  });
  check("csv exported", Boolean(csv && csv.text.length > 0));
  check("csv starts with a UTF-8 BOM", csv?.hasBom === true);
  check("csv uses CRLF", Boolean(csv?.text.includes("\r\n")));
  check("csv header is present", Boolean(csv?.text.includes("维度,请求")));

  // ───────────────────────── 日志页 ─────────────────────────
  await goto(page, "/logs");
  await waitForText(page, "h1", "日志");
  await page.select("#logs-status", "failure");
  await page.waitForFunction(() => window.location.search.includes("status=failure"));
  await waitForBody(page, "失败");
  const failureRows = await page.evaluate(() =>
    Array.from(document.querySelectorAll("tbody tr")).length,
  );
  check("logs status filter applies", failureRows > 0, String(failureRows));

  await page.evaluate(() => {
    const row = document.querySelector("tbody tr");
    row?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await waitForBody(page, "请求详情");
  const detail = await bodyText(page);
  check("log detail shows metadata", detail.includes("request_id") && detail.includes("图片指纹"));
  await shot(page, "13-logs");
  await clickDialogButton(page, "关闭");

  await page.select("#logs-status", "");
  await page.waitForFunction(() => !window.location.search.includes("status="));
  await clickButtonWithText(page, "下一页");
  await page.waitForFunction(() => window.location.search.includes("offset=50"));
  // keepPreviousData holds the previous page until the next one arrives.
  await page.waitForFunction(
    () => document.querySelectorAll("tbody tr").length < 50,
    { timeout: 10_000 },
  );
  const secondPageRows = await page.evaluate(
    () => document.querySelectorAll("tbody tr").length,
  );
  check("logs pagination works", secondPageRows > 0 && secondPageRows < 50, String(secondPageRows));

  // ───────────────────────── 设置页 ─────────────────────────
  await goto(page, "/settings");
  await waitForText(page, "h1", "设置");
  await waitForBody(page, "可编辑");

  let putCount = 0;
  page.on("request", (request) => {
    if (request.method() === "PUT" && request.url().includes("/api/admin/settings")) {
      putCount += 1;
    }
  });

  await fill(page, "#cache_ttl_seconds", "120");
  const saveButton = await page.evaluateHandle(() =>
    Array.from(document.querySelectorAll("button")).find((button) =>
      (button.textContent ?? "").includes("保存设置"),
    ),
  );
  await saveButton.asElement().click();
  await saveButton.asElement().click();
  await waitForBody(page, "设置已保存", 10_000);
  await waitForBody(page, "缓存已清空", 10_000);
  check("settings saved with cache cleared", true);
  check("double click sends one request", putCount === 1, `PUT count=${putCount}`);
  await shot(page, "14-settings");

  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForBody(page, "可编辑");
  const persisted = await page.$eval("#cache_ttl_seconds", (element) => element.value);
  check("settings persist after reload", persisted === "120", persisted);

  await fill(page, "#cache_ttl_seconds", "59");
  await clickButtonWithText(page, "保存设置");
  await waitForBody(page, "缓存 TTL 需在 60 到 86400 秒之间。");
  check("invalid settings show a field error", true);

  await fill(page, "#cache_ttl_seconds", "3600");
  await clickButtonWithText(page, "保存设置");
  await waitForBody(page, "设置已保存");
  check("settings restored", true);

  await clickButtonWithText(page, "清空缓存");
  await page.waitForFunction(
    () => /已清空 \S+ 条缓存/.test(document.body.innerText),
    { timeout: 10_000 },
  );
  check("cache clear reports the count", true);

  // Dirty form guard blocks navigation.
  await fill(page, "#cache_ttl_seconds", "600");
  await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll("a"));
    const target = links.find((link) => (link.textContent ?? "").includes("总览"));
    target?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await waitForBody(page, "放弃未保存的修改？");
  check("unsaved changes guard blocks navigation", true);
  await clickDialogButton(page, "继续编辑");
  check("staying keeps the settings page", page.url().endsWith("/settings"));

  const violations = reporter.cspViolations;
  check("no CSP violations across admin pages", violations.length === 0, violations.join(" | "));
  const unexpected = reporter.consoleErrors.filter(
    (text) =>
      !/favicon/i.test(text) &&
      !/Failed to load resource: the server responded with a status of 401/i.test(text) &&
      // Account probe hits the real vendor; a failed fetch is logged by the browser.
      !/Failed to load resource: a network error|net::ERR_/i.test(text) &&
      !new RegExp(escapeRegExp("aip.baidubce.com")).test(text),
  );
  check("console has no unexpected errors", unexpected.length === 0, unexpected.slice(0, 3).join(" | "));
} finally {
  await browser.close();
}

reporter.finish();
