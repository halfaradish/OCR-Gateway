import { mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

import puppeteer from "puppeteer-core";

const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8000";
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "password123";
const ARTIFACTS = path.resolve(process.env.E2E_ARTIFACTS ?? "e2e-artifacts");
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
];

const executablePath = CHROME_CANDIDATES.find((candidate) => candidate && existsSync(candidate));
if (!executablePath) {
  console.error("No Chrome/Edge executable found; set CHROME_PATH.");
  process.exit(2);
}

const failures = [];
const consoleErrors = [];
const cspViolations = [];

function check(name, condition, detail = "") {
  if (condition) {
    console.log(`  ok   ${name}`);
    return;
  }
  console.error(`  FAIL ${name} ${detail}`);
  failures.push(`${name} ${detail}`.trim());
}

async function shot(page, name) {
  await mkdir(ARTIFACTS, { recursive: true });
  // Park the pointer so hover tooltips do not leak into the acceptance screenshots.
  await page.mouse.move(0, 0);
  await page.screenshot({ path: path.join(ARTIFACTS, `${name}.png`), fullPage: true });
}

async function waitForText(page, selector, text, timeout = 8000) {
  await page.waitForFunction(
    (sel, expected) => {
      const node = document.querySelector(sel);
      return Boolean(node && node.textContent && node.textContent.includes(expected));
    },
    { timeout },
    selector,
    text,
  );
}

async function login(page) {
  await page.waitForSelector("#password", { timeout: 10_000 });
  await page.focus("#password");
  await page.keyboard.down("Control");
  await page.keyboard.press("KeyA");
  await page.keyboard.up("Control");
  await page.type("#password", PASSWORD);
  await page.click("button[type=submit]");
}

const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
  defaultViewport: { width: 1440, height: 900 },
});

try {
  const page = await browser.newPage();
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    consoleErrors.push(text);
    if (/content security policy/i.test(text)) cspViolations.push(text);
  });
  page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));

  console.log(`e2e: ${BASE}`);
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#password");
  await shot(page, "01-login");

  // Wrong password stays in place with an inline message.
  await page.type("#password", "definitely-wrong");
  await page.click("button[type=submit]");
  await waitForText(page, "[role=alert]", "密码不正确");
  check("wrong password shows inline error", true);

  await page.focus("#password");
  await page.keyboard.down("Control");
  await page.keyboard.press("KeyA");
  await page.keyboard.up("Control");
  await page.type("#password", PASSWORD);
  await page.click("button[type=submit]");
  await waitForText(page, "h1", "总览", 15000);
  check("login reaches overview", true);
  await shot(page, "02-overview");

  const storage = await page.evaluate(() => ({
    local: Object.keys(window.localStorage).length,
    session: Object.keys(window.sessionStorage).length,
  }));
  check("no token in web storage", storage.local === 0 && storage.session === 0, JSON.stringify(storage));

  const overviewText = await page.evaluate(() => document.body.innerText);
  check("overview shows metrics", overviewText.includes("今日请求") && overviewText.includes("账号配额"));
  check("overview has no empty-state placeholder when data exists", !overviewText.includes("该页面由后续切片实现"));

  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForText(page, "h1", "总览", 15000);
  check("session survives reload", true);

  // Stale CSRF cookie: the client refreshes `/me` and retries the write once (logout is a write).
  await page.setCookie({ name: "ocr_csrf", value: "stale-token", domain: "127.0.0.1", path: "/" });
  const logoutButton = await page.evaluateHandle(() =>
    Array.from(document.querySelectorAll("button")).find((button) =>
      (button.textContent ?? "").includes("登出"),
    ),
  );
  await logoutButton.click();
  await page.waitForSelector("#password", { timeout: 8000 });
  check("stale CSRF cookie is refreshed and the write retried", true);

  // Expired session: a protected query gets 401 and the app returns to login.
  await login(page);
  await waitForText(page, "h1", "总览", 15000);
  await page.deleteCookie({ name: "ocr_admin_session", domain: "127.0.0.1", path: "/" });
  await page.goto(`${BASE}/logs`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.location.pathname === "/login", { timeout: 8000 });
  check("expired session redirects to /login", true);

  // Unauthenticated deep link redirects to login, and login returns to the requested route.
  await page.goto(`${BASE}/accounts`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.location.pathname === "/login", { timeout: 8000 });
  check("unauthenticated route redirects to /login", true);

  await login(page);
  await page.waitForFunction(() => window.location.pathname === "/accounts", { timeout: 15000 });
  check("login returns to requested route", true);

  // All seven routes are reachable while authenticated.
  for (const [route, heading] of [
    ["/", "总览"],
    ["/accounts", "账号"],
    ["/members", "成员与 Key"],
    ["/usage", "用量"],
    ["/logs", "日志"],
    ["/settings", "设置"],
  ]) {
    await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
    await waitForText(page, "h1", heading);
  }
  check("all routes render for an authenticated admin", true);
  await shot(page, "03-settings");

  await page.goto(`${BASE}/no-such-page`, { waitUntil: "domcontentloaded" });
  await new Promise((resolve) => setTimeout(resolve, 300));
  const notFoundText = await page.evaluate(() => document.body.innerText);
  check("unknown route renders the 404 page", notFoundText.includes("页面不存在"));

  check("no CSP violations", cspViolations.length === 0, cspViolations.join(" | "));
  const unexpectedConsole = consoleErrors.filter(
    (text) =>
      !/favicon/i.test(text) &&
      // `/api/admin/me` answers 401 before login; that is the expected anonymous path.
      !/Failed to load resource: the server responded with a status of 401/i.test(text),
  );
  check("console has no errors", unexpectedConsole.length === 0, unexpectedConsole.slice(0, 3).join(" | "));
} finally {
  await browser.close();
}

if (failures.length > 0) {
  console.error(`e2e FAILED (${failures.length})`);
  process.exit(1);
}
console.log("e2e PASSED");
