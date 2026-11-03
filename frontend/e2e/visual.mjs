import { BASE, createReporter, launch, login, shot, waitForText } from "./support.mjs";

const reporter = createReporter();
const { check } = reporter;

const ROUTES = [
  ["/", "总览", "20-narrow-overview"],
  ["/accounts", "账号", "21-narrow-accounts"],
  ["/members", "成员与 Key", "22-narrow-members"],
  ["/usage", "用量", "23-narrow-usage"],
  ["/logs", "日志", "24-narrow-logs"],
  ["/settings", "设置", "25-narrow-settings"],
];

const browser = await launch();
try {
  const page = await browser.newPage();
  reporter.attach(page);
  await page.setViewport({ width: 360, height: 800, deviceScaleFactor: 2 });
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await login(page);
  await waitForText(page, "h1", "总览", 15_000);
  await shot(page, "26-narrow-login-shell");

  for (const [route, heading, name] of ROUTES) {
    await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
    await waitForText(page, "h1", heading);
    await shot(page, name);
  }
  check("all routes render at 360px", true);

  // The sidebar collapses into a drawer below 768px.
  const sidebarHidden = await page.evaluate(() => {
    const aside = document.querySelector("aside");
    return !aside || getComputedStyle(aside).display === "none";
  });
  check("sidebar collapses on narrow screens", sidebarHidden);

  await page.evaluate(() => {
    const button = Array.from(document.querySelectorAll("button")).find((item) =>
      (item.getAttribute("aria-label") ?? "").includes("打开导航"),
    );
    button?.click();
  });
  await page.waitForFunction(
    () => (document.querySelector('[role="dialog"]')?.textContent ?? "").includes("导航"),
    { timeout: 5000 },
  );
  check("mobile drawer opens", true);
  await shot(page, "27-narrow-drawer");

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth + 1,
  );
  check("no horizontal page overflow at 360px", overflow);

  check("no CSP violations", reporter.cspViolations.length === 0, reporter.cspViolations.join(" | "));
  const unexpected = reporter.consoleErrors.filter(
    (text) => !/favicon/i.test(text) && !/status of 401/i.test(text),
  );
  check("console has no errors", unexpected.length === 0, unexpected.slice(0, 3).join(" | "));
} finally {
  await browser.close();
}

reporter.finish();
