import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../public/analytics-consent.js", import.meta.url), "utf8");

function createPage(pathname = "/notices") {
  const storage = new Map();
  const cookieWrites = [];
  const scripts = [];

  class Element {
    constructor(tagName) {
      this.tagName = tagName;
      this.children = [];
      this.dataset = {};
      this.listeners = {};
      this.attributes = {};
      this.parentNode = null;
      this.id = "";
    }

    append(...nodes) {
      for (const node of nodes) {
        if (node && typeof node === "object") node.parentNode = this;
        this.children.push(node);
      }
    }

    appendChild(node) {
      this.append(node);
      if (this.tagName === "head" && node.tagName === "script") scripts.push(node);
      return node;
    }

    addEventListener(name, callback) {
      this.listeners[name] = callback;
    }

    setAttribute(name, value) {
      this.attributes[name] = value;
    }

    remove() {
      if (!this.parentNode) return;
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }

    click() {
      this.listeners.click?.();
    }
  }

  const body = new Element("body");
  const head = new Element("head");
  const findById = (node, id) => {
    if (node.id === id) return node;
    for (const child of node.children) {
      if (child && typeof child === "object") {
        const match = findById(child, id);
        if (match) return match;
      }
    }
    return null;
  };
  const document = {
    body,
    head,
    referrer: "https://search.example/path?private=1#fragment",
    createElement: (tagName) => new Element(tagName),
    createTextNode: (textContent) => ({ textContent }),
    getElementById: (id) => findById(body, id),
    querySelectorAll: () => [],
  };
  Object.defineProperty(document, "cookie", {
    get: () => "",
    set: (value) => cookieWrites.push(value),
  });

  const origin = "https://coupasthreadauto.me";
  const window = {
    dataLayer: [],
    location: {
      href: `${origin}${pathname}?email=private@example.com#token`,
      origin,
      pathname,
      hostname: "coupasthreadauto.me",
    },
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
    },
  };

  vm.runInNewContext(source, { window, document, URL, Date, encodeURIComponent });
  return { body, document, window, storage, cookieWrites, scripts, findById };
}

const findChoiceButton = (node, choice) => {
  if (node.dataset?.consent === choice) return node;
  for (const child of node.children ?? []) {
    if (child && typeof child === "object") {
      const match = findChoiceButton(child, choice);
      if (match) return match;
    }
  }
  return null;
};

const queuedCommands = (window) => window.dataLayer.map((args) => Array.from(args));

test("Analytics loads only after consent and supports withdrawal and renewed consent", () => {
  const page = createPage();
  assert.equal(page.scripts.length, 0);
  assert.ok(page.document.getElementById("analytics-consent-banner"));

  findChoiceButton(page.document.getElementById("analytics-consent-banner"), "granted").click();
  assert.equal(page.scripts.length, 1);
  assert.match(page.scripts[0].src, /G-TQ30XL5VX0/);
  assert.equal(page.storage.get("thread-auto-analytics-consent-v1"), "granted");

  let commands = queuedCommands(page.window);
  assert.ok(commands.some((entry) => entry[0] === "consent" && entry[1] === "default" && entry[2].analytics_storage === "granted"));
  const firstPageView = commands.find((entry) => entry[0] === "event" && entry[1] === "page_view");
  assert.equal(firstPageView[2].page_location, "https://coupasthreadauto.me/notices");
  assert.equal(firstPageView[2].page_referrer, "https://search.example/path");

  page.document.getElementById("analytics-consent-manage").click();
  findChoiceButton(page.document.getElementById("analytics-consent-banner"), "denied").click();
  assert.equal(page.storage.get("thread-auto-analytics-consent-v1"), "denied");
  assert.ok(page.cookieWrites.some((value) => value.includes("_ga_TQ30XL5VX0=; Max-Age=0")));
  commands = queuedCommands(page.window);
  assert.ok(commands.some((entry) => entry[0] === "consent" && entry[1] === "update" && entry[2].analytics_storage === "denied"));

  page.document.getElementById("analytics-consent-manage").click();
  findChoiceButton(page.document.getElementById("analytics-consent-banner"), "granted").click();
  assert.equal(page.scripts.length, 1);
  assert.equal(page.storage.get("thread-auto-analytics-consent-v1"), "granted");
  commands = queuedCommands(page.window);
  assert.ok(commands.some((entry) => entry[0] === "consent" && entry[1] === "update" && entry[2].analytics_storage === "granted"));
  assert.equal(commands.filter((entry) => entry[0] === "event" && entry[1] === "page_view").length, 2);
});

test("password recovery pages never create Analytics consent UI or load the Google tag", () => {
  const page = createPage("/reset-password/complete");
  assert.equal(page.scripts.length, 0);
  assert.equal(page.document.getElementById("analytics-consent-banner"), null);
  assert.equal(page.document.getElementById("analytics-consent-manage"), null);
});
