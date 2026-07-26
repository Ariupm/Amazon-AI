"use client";

import { FormEvent, useMemo, useState } from "react";

const API = "http://127.0.0.1:8765";
const MAX_ASINS = 100;

type Variant = {
  asin: string; url: string; title?: string; image?: string; color?: string; size?: string;
  price?: string; list_price?: string; recent_sales_signal?: string; rating?: number;
  rating_count?: number; bullets?: string[]; data_quality: "complete" | "partial"; is_suspected_main?: boolean;
};
type Insight = { phrase: string; mentions: number; evidence: string[] };
type Product = {
  requested_asin: string; asin: string; parent_asin?: string; is_parent_request: boolean;
  expected_child_count?: number; suspected_main_asin?: string;
  suspected_main_confidence?: "high" | "medium" | "low"; suspected_main_reason?: string;
  source_url: string; canonical_url?: string; title: string; price?: string; list_price?: string;
  rating?: number; rating_count?: number; recent_sales_signal?: string; images: string[];
  bullets: string[]; variants: Variant[]; warnings: string[];
  insights: { analyzed_reviews: number; advantages: Insight[]; pains: Insight[] };
};
type Batch = {
  items: { requested_asin: string; success: boolean; result?: Product; error?: string }[];
  total: number; succeeded: number; failed: number;
};

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}

export default function Collector() {
  const [input, setInput] = useState("");
  const [marketplace, setMarketplace] = useState("US");
  const [pages, setPages] = useState(2);
  const [mode, setMode] = useState("full");
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");
  const [batch, setBatch] = useState<Batch | null>(null);
  const asins = useMemo(() => [...new Set(input.toUpperCase().split(/[\s,;]+/).map(x => x.trim()).filter(Boolean))], [input]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!asins.length) return setMessage("请至少输入一个 ASIN。");
    if (asins.length > MAX_ASINS) return setMessage(`单批最多 ${MAX_ASINS} 个 ASIN，请拆分后重试。`);
    const invalid = asins.find(asin => !/^[A-Z0-9]{10}$/.test(asin));
    if (invalid) return setMessage(`${invalid} 不是有效的 10 位 ASIN。`);
    setRunning(true); setBatch(null);
    setMessage(`正在用同一个 Chrome 依次采集 ${asins.length} 个 ASIN，请不要关闭登录窗口…`);
    try {
      const response = await fetch(`${API}/api/scrape/batch`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asins, marketplace, max_review_pages: pages, headless: false, variant_mode: mode }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "采集失败");
      setBatch(payload);
      setMessage(`采集完成：成功 ${payload.succeeded}，失败 ${payload.failed}。`);
    } catch (error) {
      setMessage(error instanceof TypeError
        ? "未连接到本机真实抓取器。请先运行“启动真实抓取器.bat”，保持窗口开启后重试。"
        : error instanceof Error ? error.message : "采集失败");
    } finally { setRunning(false); }
  }

  async function exportXlsx() {
    if (!batch) return;
    setMessage("正在下载商品图片并生成 XLSX…");
    try {
      const response = await fetch(`${API}/api/export/xlsx`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(batch),
      });
      if (!response.ok) throw new Error();
      download(await response.blob(), `amazon-products-with-images-${Date.now()}.xlsx`);
      setMessage("XLSX 已导出：第一列为内嵌图片，第二列保留图片 URL。");
    } catch { setMessage("无法连接本机抓取器导出 XLSX，请确认本地服务仍在运行。"); }
  }

  return <main>
    <header className="topbar">
      <a className="brand" href="/" aria-label="采数首页"><span className="brandMark">采</span><span>采数</span></a>
      <nav aria-label="主导航"><a className="active" href="#workspace">数据采集</a><a href="/titles">标题工作台</a></nav>
      <span className="workspaceStatus"><i /> 本机真实浏览器模式</span>
    </header>
    <section className="collectorHero" id="workspace">
      <div><span className="eyebrow"><i /> AMAZON REAL DATA</span><h1>真实商品数据采集器</h1><p>调用你电脑上的 Chrome 实际访问 Amazon。支持父子体识别、批量采集、主推判断、评论优痛点和图片版 XLSX。</p></div>
      <form className="collectorForm" onSubmit={submit}>
        <label className="asinArea"><span>商品 ASIN（最多 100 个）</span><b className={asins.length > MAX_ASINS ? "over" : ""}>{asins.length} / {MAX_ASINS} 个 ASIN</b><textarea value={input} onChange={e => setInput(e.target.value)} placeholder={"B0CT1NWL9J\nB0DSFFXYMD"} /></label>
        <label><span>站点</span><select value={marketplace} onChange={e => setMarketplace(e.target.value)}><option value="US">美国站</option><option value="UK">英国站</option><option value="DE">德国站</option><option value="JP">日本站</option></select></label>
        <label><span>评论页数</span><select value={pages} onChange={e => setPages(Number(e.target.value))}><option>0</option><option>1</option><option>2</option><option>3</option><option>5</option></select></label>
        <label><span>变体模式</span><select value={mode} onChange={e => setMode(e.target.value)}><option value="full">完整逐子体</option><option value="fast">极速清单</option></select></label>
        <button className="collectorSubmit" disabled={running}>{running ? "正在真实采集…" : "开始真实采集"}</button>
      </form>
      <div className="localNotice"><b>使用前：</b>先在本机运行“启动真实抓取器.bat”。登录或验证码出现时会一直等待；一批 ASIN 共用一个浏览器。</div>
    </section>
    {message && <section className={`collectorStatus ${running ? "busy" : ""}`}>{message}</section>}
    {batch ? <section className="liveResults">
      <div className="batchBar"><div><b>本批次结果</b><span>{batch.total} 个输入 · {batch.succeeded} 成功 · {batch.failed} 失败</span></div><div><button onClick={exportXlsx}>导出 XLSX（内嵌图片）</button><button onClick={() => download(new Blob([JSON.stringify(batch, null, 2)], { type: "application/json" }), "amazon-products.json")}>导出 JSON</button></div></div>
      {batch.items.map(item => item.success && item.result ? <ProductResult key={item.requested_asin} product={item.result} /> : <article className="failedResult" key={item.requested_asin}><b>{item.requested_asin}</b><span>{item.error}</span></article>)}
    </section> : !running && <section className="emptyState"><div className="orbit"><div className="cube">▦</div></div><h2>等待真实采集</h2><p>结果只会在本机浏览器成功读取 Amazon 商品标题后显示。</p><div className="featureRow"><span>◎ 父子体识别</span><span>◇ 月销量信号</span><span>✦ 评论优痛点</span><span>↓ 图片 XLSX</span></div></section>}
    <footer><span>采数 · Amazon 真实数据采集器</span><span>价格与库存受站点、配送地址及登录状态影响</span></footer>
  </main>;
}

function ProductResult({ product }: { product: Product }) {
  const main = product.is_parent_request ? product.variants.find(v => v.is_suspected_main) || product.variants.find(v => v.asin === product.suspected_main_asin) : undefined;
  const hero = main || product.variants[0], image = hero?.image || product.images[0], url = hero?.url || product.canonical_url || product.source_url;
  const bullets = hero?.bullets?.length ? hero.bullets : product.bullets;
  return <section className="liveProduct">
    <div className="taskLabel"><span>{product.is_parent_request ? `父体任务 · ${product.variants.length}/${product.expected_child_count || product.variants.length} 个子体` : "子体任务"}</span><b>{product.requested_asin}</b></div>
    {main && <div className="mainSignal"><b>主推链接：{main.asin}</b><span>{product.suspected_main_reason} · 置信度 {product.suspected_main_confidence === "high" ? "高" : product.suspected_main_confidence === "medium" ? "中" : "低"}</span></div>}
    <article className="realProductCard"><div className="realImage">{image ? <img src={image} alt="" /> : <span>暂无图片</span>}</div><div className="realInfo"><div className="realSource"><span>{main ? "主推链接" : "真实来源"}</span><a href={url} target="_blank" rel="noreferrer">{hero?.asin || product.asin} ↗</a></div><h2>{hero?.title || product.title}</h2><div className="realFacts"><b>{hero?.price || product.price || "价格未展示"}</b>{(hero?.list_price || product.list_price) && <del>Typical price: {hero?.list_price || product.list_price}</del>}<span>★ {hero?.rating ?? product.rating ?? "—"} · {hero?.rating_count ?? product.rating_count ?? "—"} 条评分</span><span>{hero?.recent_sales_signal || product.recent_sales_signal || "月销量信号未展示"}</span></div>{bullets.length > 0 && <ul>{bullets.map(x => <li key={x}>{x}</li>)}</ul>}</div></article>
    {product.warnings.length > 0 && <div className="resultWarnings">{product.warnings.map(warning => <span key={warning}>! {warning}</span>)}</div>}
    <div className="liveSectionHead"><div><h2>{product.is_parent_request ? "全部真实子体" : "当前子体信息"}</h2><p>主推子体按月销量信号优先置顶</p></div><b>{product.variants.length} 个</b></div>
    <div className="liveTable"><table><thead><tr><th>图片</th><th>ASIN / 标题</th><th>颜色 / 尺寸</th><th>价格</th><th>月销量信号</th><th>状态</th></tr></thead><tbody>{product.variants.map(variant => <tr className={variant.is_suspected_main ? "mainRow" : ""} key={variant.asin}><td>{variant.image ? <img src={variant.image} alt="" /> : "无图"}</td><td><a href={variant.url} target="_blank" rel="noreferrer"><b>{variant.is_suspected_main && <em>主推</em>} {variant.asin} ↗</b></a><span>{variant.title || "标题未读取"}</span></td><td><b>{variant.color || "颜色未展示"}</b><span>{variant.size || "尺寸未展示"}</span></td><td><b>{variant.price || "未展示"}</b>{variant.list_price && <del>Typical: {variant.list_price}</del>}</td><td>{variant.recent_sales_signal || "未展示"}</td><td><i className={variant.data_quality}>{variant.data_quality === "complete" ? "完整" : "部分"}</i></td></tr>)}</tbody></table></div>
    <div className="liveSectionHead"><div><h2>评论洞察</h2><p>分析 {product.insights.analyzed_reviews} 条本次实际读取的评论</p></div></div>
    <div className="liveInsights"><InsightPanel title="用户认可的优点" items={product.insights.advantages} /><InsightPanel title="用户集中的痛点" items={product.insights.pains} pain /></div>
  </section>;
}

function InsightPanel({ title, items, pain = false }: { title: string; items: Insight[]; pain?: boolean }) {
  return <article className={pain ? "liveInsight pain" : "liveInsight"}><h3>{pain ? "!" : "↗"} {title}</h3>{items.length ? items.map(item => <div key={item.phrase}><p><b>{item.phrase}</b><span>{item.mentions} 次</span></p>{item.evidence.slice(0, 2).map(x => <blockquote key={x}>“{x}”</blockquote>)}</div>) : <p className="noInsight">真实评论不足，暂时无法形成分析。</p>}</article>;
}
