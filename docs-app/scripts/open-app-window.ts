/**
 * Open the reader in a chromeless window, so it reads as an application rather
 * than a tab. `--app=` gives us no address bar, no tab strip, its own taskbar
 * entry, and its own window geometry.
 *
 * We poll the dev server first: launching Chrome against a port that is not yet
 * listening shows an error page, and Chrome will not retry.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { platform } from "node:os";

const URL = "http://localhost:5178";
const TIMEOUT_MS = 30_000;
const POLL_MS = 150;

const CANDIDATES: Record<string, string[]> = {
  linux: [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/microsoft-edge",
    "/snap/bin/chromium",
    "/var/lib/flatpak/exports/bin/com.google.Chrome",
  ],
  darwin: [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  ],
  win32: [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  ],
};

function findBrowser(): string | null {
  return CANDIDATES[platform()]?.find((p) => existsSync(p)) ?? null;
}

async function waitForServer(): Promise<boolean> {
  const deadline = Date.now() + TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      // A 404 is still a listening server; we only care that the socket answers.
      await fetch(URL, { signal: AbortSignal.timeout(1000) });
      return true;
    } catch {
      await new Promise((r) => setTimeout(r, POLL_MS));
    }
  }
  return false;
}

async function main(): Promise<void> {
  if (!(await waitForServer())) {
    console.error(`window · dev server never came up on ${URL}`);
    process.exitCode = 1;
    return;
  }

  const browser = findBrowser();

  if (browser) {
    // A dedicated profile dir keeps the reader's window state, zoom level and
    // localStorage separate from the user's day-to-day browsing profile, and
    // stops `--app` from merging into an already-running Chrome session.
    const args = [
      `--app=${URL}`,
      "--user-data-dir=/tmp/handbook-reader-profile",
      "--window-size=1440,900",
      "--no-first-run",
      "--no-default-browser-check",
    ];
    spawn(browser, args, { detached: true, stdio: "ignore" }).unref();
    console.log("window · opened in app mode");
    return;
  }

  const opener =
    platform() === "darwin"
      ? "open"
      : platform() === "win32"
        ? "start"
        : "xdg-open";
  spawn(opener, [URL], {
    detached: true,
    stdio: "ignore",
    shell: platform() === "win32",
  }).unref();
  console.log(
    `window · no Chrome found; opened ${URL} in your default browser`,
  );
}

void main();
