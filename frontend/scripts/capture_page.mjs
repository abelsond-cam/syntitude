#!/usr/bin/env node
/**
 * Drive a headless Chrome over the DevTools protocol and screenshot the page — no dependencies.
 *
 * ⭐ **Why this exists.** Rendering the rebuilt page beside the frozen one found bugs that ~650 tests
 * could not: a locus response carrying two of the track's ten intergenic regions, a switcher whose
 * buttons stacked down the page gutter, a popover printing an enum where the product belongs, and a
 * fan the PUBLISHED page has never drawn. jsdom computes no layout and loads no stylesheet, so none of
 * those is visible to a unit test. This is the instrument that made them visible, kept so the
 * appearance review can be re-run by anyone with Chrome and Node ≥ 22 (for the global `WebSocket`).
 *
 * Usage:
 *   node scripts/capture_page.mjs steps.json
 *
 * `steps.json` is a list, run in order:
 *   { "url": "http://localhost:5173/?species=kp#1098", "settle": 3500 }   navigate, then wait (ms)
 *   { "eval": "document.querySelector('.locus-name').textContent" }      run JS, print the result
 *   { "media": "dark" }                                                  emulate prefers-color-scheme
 *   { "shot": "out/kp.png", "w": 1440, "h": 1200, "y": 0 }               screenshot a region
 *   { "wait": 1000 }                                                     just wait
 *
 * ⚠ Navigating to the URL the page is already on is a same-document hash change, not a reload — add a
 * throwaway query parameter (`&r=2`) when a fresh load is what you mean.
 *
 * Environment: `CHROME` (the browser binary; defaults to the macOS Google Chrome path, then
 * `google-chrome` / `chromium` on the PATH), `CAPTURE_PORT` (the debugging port, default 9333).
 * Console errors, exceptions and failed requests are printed at the end — a page that "looks fine"
 * while logging a 404 is exactly the case worth seeing.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

const [scriptPath] = process.argv.slice(2);
if (!scriptPath) {
  console.error("usage: node scripts/capture_page.mjs steps.json");
  process.exit(2);
}
const steps = JSON.parse(readFileSync(scriptPath, "utf8"));
const port = Number(process.env.CAPTURE_PORT ?? 9333);
const MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const chrome = process.env.CHROME ?? (existsSync(MAC_CHROME) ? MAC_CHROME : "google-chrome");

const profile = mkdtempSync(join(tmpdir(), "capture-page-"));
const browser = spawn(
  chrome,
  [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "--window-size=1440,2400",
    "about:blank",
  ],
  // ⚠ Its own process GROUP, so the renderer and GPU children die with it — killing only the parent
  // leaves them writing into the profile directory while it is being removed.
  { stdio: "ignore", detached: true },
);
const browserExited = new Promise((resolve) => browser.once("exit", resolve));

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function pageTarget() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = targets.find((target) => target.type === "page");
      if (page) return page;
    } catch {
      // not listening yet
    }
    await sleep(200);
  }
  throw new Error(`no Chrome page target on port ${port} — is ${chrome} installed?`);
}

let exitCode = 0;
try {
  const page = await pageTarget();
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve);
    socket.addEventListener("error", reject);
  });
  let id = 0;
  const pending = new Map();
  const log = [];
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      pending.get(message.id)(message);
      pending.delete(message.id);
      return;
    }
    const params = message.params ?? {};
    if (message.method === "Runtime.consoleAPICalled" && params.type !== "debug") {
      log.push(`${params.type}: ${params.args.map((arg) => arg.value ?? arg.description).join(" ")}`);
    } else if (message.method === "Runtime.exceptionThrown") {
      log.push(`EXCEPTION: ${params.exceptionDetails.exception?.description ?? params.exceptionDetails.text}`);
    } else if (message.method === "Log.entryAdded") {
      log.push(`${params.entry.level}: ${params.entry.text} ${params.entry.url ?? ""}`);
    }
  });
  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const next = ++id;
      pending.set(next, resolve);
      socket.send(JSON.stringify({ id: next, method, params }));
    });

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Log.enable");

  for (const step of steps) {
    if (step.url) {
      await send("Page.navigate", { url: step.url });
      await sleep(step.settle ?? 2500);
    }
    if (step.media) {
      await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: step.media }] });
      await sleep(400);
    }
    if (step.eval) {
      const reply = await send("Runtime.evaluate", {
        expression: step.eval,
        awaitPromise: true,
        returnByValue: true,
      });
      const value = reply.result?.result?.value ?? reply.result?.exceptionDetails?.text ?? null;
      console.log("eval:", JSON.stringify(value));
      await sleep(step.settle ?? 600);
    }
    if (step.wait) await sleep(step.wait);
    if (step.shot) {
      const width = step.w ?? 1440;
      const height = step.h ?? 2400;
      await send("Emulation.setDeviceMetricsOverride", {
        width,
        height,
        deviceScaleFactor: 1,
        mobile: width < 600,
      });
      await sleep(400);
      const reply = await send("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: true,
        clip: { x: 0, y: step.y ?? 0, width, height, scale: 1 },
      });
      mkdirSync(dirname(step.shot), { recursive: true });
      writeFileSync(step.shot, Buffer.from(reply.result.data, "base64"));
      console.log("shot:", step.shot);
    }
  }
  console.log(log.length ? `console, exceptions and failed requests:\n${log.join("\n")}` : "console: clean");
  socket.close();
} catch (error) {
  console.error(String(error));
  exitCode = 1;
} finally {
  try {
    process.kill(-browser.pid, "SIGTERM");
  } catch {
    browser.kill();
  }
  await Promise.race([browserExited, sleep(5000)]);
  rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
}
process.exit(exitCode);
