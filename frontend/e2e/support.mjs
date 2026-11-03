import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";

import puppeteer from "puppeteer-core";

export const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8000";
export const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "password123";
export const ARTIFACTS = path.resolve(process.env.E2E_ARTIFACTS ?? "e2e-artifacts");

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
];

export function findChrome() {
  const executablePath = CHROME_CANDIDATES.find(
    (candidate) => candidate && existsSync(candidate),
  );
  if (!executablePath) {
    console.error("No Chrome/Edge executable found; set CHROME_PATH.");
    process.exit(2);
  }
  return executablePath;
}

export function createReporter() {
  const failures = [];
  const consoleErrors = [];
  const cspViolations = [];

  return {
    failures,
    consoleErrors,
    cspViolations,
    check(name, condition, detail = "") {
      if (condition) {
        console.log(`  ok   ${name}`);
        return;
      }
      console.error(`  FAIL ${name} ${detail}`);
      failures.push(`${name} ${detail}`.trim());
    },
    attach(page) {
      page.on("console", (message) => {
        if (message.type() !== "error") return;
        const text = message.text();
        consoleErrors.push(text);
        if (/content security policy/i.test(text)) cspViolations.push(text);
      });
      page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));
    },
    finish() {
      if (failures.length > 0) {
        console.error(`e2e FAILED (${failures.length})`);
        process.exit(1);
      }
      console.log("e2e PASSED");
    },
  };
}

export async function shot(page, name) {
  await mkdir(ARTIFACTS, { recursive: true });
  // Park the pointer so hover tooltips do not leak into the acceptance screenshots.
  await page.mouse.move(0, 0);
  await page.screenshot({ path: path.join(ARTIFACTS, `${name}.png`), fullPage: true });
}

export async function waitForText(page, selector, text, timeout = 10_000) {
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

export async function login(page, password = PASSWORD) {
  await page.waitForSelector("#password", { timeout: 10_000 });
  await page.focus("#password");
  await page.keyboard.down("Control");
  await page.keyboard.press("KeyA");
  await page.keyboard.up("Control");
  await page.type("#password", password);
  await page.click("button[type=submit]");
}

export async function clickButtonWithText(page, text, options = {}) {
  await page.waitForFunction(
    (label) =>
      Array.from(document.querySelectorAll("button")).some((button) =>
        (button.textContent ?? "").includes(label),
      ),
    { timeout: options.timeout ?? 10_000 },
    text,
  );
  const clicked = await page.evaluate((label) => {
    const buttons = Array.from(document.querySelectorAll("button"));
    const target = buttons.find((button) => (button.textContent ?? "").includes(label));
    if (!target) return false;
    target.click();
    return true;
  }, text);
  if (!clicked) throw new Error(`button not found: ${text}`);
}

export async function fillByLabel(page, labelText, value) {
  const id = await page.evaluate((label) => {
    const nodes = Array.from(document.querySelectorAll("label"));
    const match = nodes.find((node) => (node.textContent ?? "").trim() === label);
    return match?.getAttribute("for") ?? null;
  }, labelText);
  if (!id) throw new Error(`label not found: ${labelText}`);
  await page.click(`#${id}`);
  await page.keyboard.down("Control");
  await page.keyboard.press("KeyA");
  await page.keyboard.up("Control");
  if (value !== "") await page.type(`#${id}`, value);
}

export async function launch() {
  return puppeteer.launch({
    executablePath: findChrome(),
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
    defaultViewport: { width: 1440, height: 900 },
  });
}

/** Click a button inside the open dialog (Radix renders `role="dialog"`). */
export async function clickDialogButton(page, text, timeout = 10_000) {
  await page.waitForFunction(
    (label) =>
      Array.from(document.querySelectorAll('[role="dialog"] button')).some((button) =>
        (button.textContent ?? "").includes(label),
      ),
    { timeout },
    text,
  );
  const clicked = await page.evaluate((label) => {
    const buttons = Array.from(document.querySelectorAll('[role="dialog"] button'));
    const target = buttons.find((button) => (button.textContent ?? "").includes(label));
    if (!target) return false;
    target.click();
    return true;
  }, text);
  if (!clicked) throw new Error(`dialog button not found: ${text}`);
}

/** Click a button inside the table row that contains `rowText`. */
export async function clickRowButton(page, rowText, buttonText, timeout = 10_000) {
  await page.waitForFunction(
    (rowLabel, buttonLabel) =>
      Array.from(document.querySelectorAll("tbody tr")).some(
        (row) =>
          (row.textContent ?? "").includes(rowLabel) &&
          Array.from(row.querySelectorAll("button")).some((button) =>
            (button.textContent ?? "").includes(buttonLabel),
          ),
      ),
    { timeout },
    rowText,
    buttonText,
  );
  const clicked = await page.evaluate(
    (rowLabel, buttonLabel) => {
      const row = Array.from(document.querySelectorAll("tbody tr")).find((item) =>
        (item.textContent ?? "").includes(rowLabel),
      );
      if (!row) return false;
      const target = Array.from(row.querySelectorAll("button")).find((button) =>
        (button.textContent ?? "").includes(buttonLabel),
      );
      if (!target) return false;
      target.click();
      return true;
    },
    rowText,
    buttonText,
  );
  if (!clicked) throw new Error(`row button not found: ${rowText} / ${buttonText}`);
}
