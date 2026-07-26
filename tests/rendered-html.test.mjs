import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the real Amazon collector", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>采数｜Amazon 真实商品数据采集器<\/title>/i);
  assert.match(html, /真实商品数据采集器/);
  assert.match(html, /商品 ASIN（最多 100 个）/);
  assert.match(html, /启动真实抓取器\.bat/);
  assert.match(html, /完整逐子体/);
  assert.doesNotMatch(html, /Everyday 多功能轻量托特包/);
});

test("keeps the title workspace route available", async () => {
  const response = await render();
  const html = await response.text();
  assert.match(html, /href="\/titles"/);
  assert.match(html, /标题工作台/);
  assert.match(html, /本机真实浏览器模式/);
});

test("renders child bullets with a product fallback", async () => {
  const collector = await readFile(new URL("../app/collector.tsx", import.meta.url), "utf8");
  assert.match(collector, /hero\?\.bullets\?\.length \? hero\.bullets : product\.bullets/);
  assert.match(collector, /bullets\.map/);
});
