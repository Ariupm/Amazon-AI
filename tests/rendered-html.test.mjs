import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, {
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

test("title workspace starts from real inputs without fake competitors", async () => {
  const response = await render("/titles");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /明确标题任务/);
  assert.match(html, /优化现有商品标题/);
  assert.match(html, /编写新增变体标题/);
  assert.match(html, /父体 ASIN/);
  assert.match(html, /新增颜色/);
  assert.match(html, /新增尺寸/);
  assert.match(html, /主标题 ≤ 75 \+ Highlight Item ≤ 125/);
  assert.doesNotMatch(html, /新增变体计划表|卖家 SKU|库存计划/);
  assert.match(html, /自动发现疑似竞品/);
  assert.match(html, /类目不一致直接排除/);
  assert.match(html, /真实属性 35%/);
  assert.match(html, /尺寸不进入系统搜索词/);
  assert.match(html, /视觉 20%/);
  assert.match(html, /Amazon 翻页/);
  const workspace = await readFile(new URL("../app/titles/market-workspace.tsx", import.meta.url), "utf8");
  assert.match(workspace, /本品特征画像/);
  assert.match(workspace, /实际搜索词/);
  assert.match(workspace, /每个竞品品牌只保留 1 个/);
  assert.match(workspace, /月销量信号优先/);
  assert.match(workspace, /轮廓 55%/);
  assert.match(workspace, /可修改后一行一组/);
  assert.match(workspace, /同品牌重复项/);
  assert.match(workspace, /exclude_asins/);
  assert.match(workspace, /导出全部 XLSX/);
  assert.match(workspace, /search-first-brand-dedupe-v10/);
  assert.match(workspace, /verify_detail_pages/);
  assert.match(workspace, /旧版本机抓取器仍占用 8765 端口/);
  assert.match(workspace, /正在检查本机抓取器版本/);
  assert.match(workspace, /未连接到本机抓取器/);
  assert.match(html, /ABA 综合词库/);
  assert.match(workspace, /lockCompetitors/);
  assert.match(workspace, /已锁定.*个竞品/);
  assert.match(workspace, /scrollIntoView/);
  assert.match(workspace, /ABA 综合词库尚未通过读取校验/);
  assert.match(workspace, /api\/keywords\/inspect/);
  assert.match(workspace, /api\/titles\/generate/);
  assert.match(workspace, /生成标题候选/);
  assert.match(workspace, /复制完整标题/);
  assert.match(workspace, /新增颜色或新增尺寸至少填写一项/);
  assert.match(workspace, /查看待完成项/);
  assert.match(workspace, /focusSelector/);
  assert.doesNotMatch(workspace, /disabled=\{!!nextBlockers\.length\}/);
  assert.doesNotMatch(html, /BAGSMART|LOVEVOOK|61\.2K|综合质量/);
});

test("renders child bullets with a product fallback", async () => {
  const collector = await readFile(new URL("../app/collector.tsx", import.meta.url), "utf8");
  assert.match(collector, /hero\?\.bullets\?\.length \? hero\.bullets : product\.bullets/);
  assert.match(collector, /bullets\.map/);
});

test("launcher replaces stale competitor-discovery servers", async () => {
  const launcher = await readFile(new URL("../run_scraper.ps1", import.meta.url), "utf8");
  assert.match(launcher, /search-first-brand-dedupe-v10/);
  assert.match(launcher, /检测到旧版抓取器/);
  assert.match(launcher, /netstat -ano/);
  assert.match(launcher, /Get-ListenerProcessId/);
  assert.doesNotMatch(launcher, /if \(\$hasBatchApi\)/);
});
