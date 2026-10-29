const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const source = readFileSync(join(__dirname, "../static/main/js/marketplace-pages.js"), "utf8");

function mount(fetch = async () => new Response("{}")) {
  class Element extends EventTarget {
    constructor() { super(); this.dataset = {}; }
    setAttribute() {}
    before() {}
  }
  const elements = new Map(["main-content", "market-page-assets", "market-page-dialogs"].map((id) => [id, new Element()]));
  const document = new EventTarget();
  document.scripts = [];
  document.currentScript = { src: "http://localhost/static/example.js", dataset: {} };
  document.getElementById = (id) => elements.get(id);
  document.querySelector = () => new Element();
  document.createElement = () => new Element();
  const window = new EventTarget();
  const timers = new Map();
  let nextTimer = 0;
  runInNewContext(source, {
    document, window, fetch, URL, AbortController, DOMException,
    history: { scrollRestoration: "auto" },
    location: { href: "http://localhost/clothing-catalog/", pathname: "/clothing-catalog/" },
    setTimeout(callback) { timers.set(++nextTimer, callback); return nextTimer; },
    clearTimeout(id) { timers.delete(id); },
  });
  let scope;
  window.MarketplacePages.register((page) => { scope = page; });
  return { scope, document, window, timers };
}

test("leaving a page detaches listeners, clears timers, and cleans up once", () => {
  const { scope, timers } = mount();
  const target = new EventTarget();
  let events = 0;
  let cleanups = 0;
  scope.on(target, "example", () => { events += 1; });
  scope.cleanup(() => { cleanups += 1; });
  const cancelled = scope.timeout(() => {}, 100);
  scope.clearTimeout(cancelled);
  assert.equal(timers.size, 0);
  scope.timeout(() => {}, 100);
  target.dispatchEvent(new Event("example"));
  scope.destroy();
  scope.destroy();
  target.dispatchEvent(new Event("example"));
  assert.equal(events, 1);
  assert.equal(cleanups, 1);
  assert.equal(timers.size, 0);
});

test("leaving aborts response-body work and prevents stale data being consumed", async () => {
  let signal;
  const { scope } = mount(async (url, options) => {
    signal = options.signal;
    return new Response('{"count":1}');
  });
  const response = await scope.fetch("/results/");
  scope.destroy();
  assert.equal(signal.aborted, true);
  await assert.rejects(response.json(), { name: "AbortError" });
});

test("an individual request can be cancelled without destroying the page", async () => {
  let signal;
  const { scope } = mount(async (url, options) => {
    signal = options.signal;
    return new Response("ready");
  });
  const request = new AbortController();
  const response = await scope.fetch("/results/", { signal: request.signal });
  request.abort();
  assert.equal(signal.aborted, true);
  assert.equal(scope.signal.aborted, false);
  await assert.rejects(response.text(), { name: "AbortError" });
});

test("navigation can wait for an in-flight send before leaving", async () => {
  const { scope } = mount();
  let resolve;
  let ready = false;
  scope.beforeLeave(() => new Promise((done) => { resolve = done; }));
  const waiting = scope.whenIdle().then(() => { ready = true; });
  assert.equal(ready, false);
  resolve();
  await waiting;
  assert.equal(ready, true);
});

test("preloaded page modules do not initialize against the outgoing page", () => {
  const { document, window } = mount();
  let mounts = 0;
  document.currentScript = { src: "http://localhost/static/next.js", dataset: { marketDynamic: "true" } };
  window.MarketplacePages.register(() => { mounts += 1; });
  assert.equal(mounts, 0);
});
