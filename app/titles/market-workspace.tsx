"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

const API = "http://127.0.0.1:8765";

type Candidate = {
  asin: string; title: string; url: string; image?: string; price?: string;
  rating?: number; rating_count?: number; recent_sales_signal?: string;
  text_similarity?: number; image_similarity?: number; overall_similarity?: number;
  selected?: boolean; source: "amazon_search" | "manual";
};
type Product = {
  asin: string; requested_asin: string; title: string; brand?: string; price?: string;
  images: string[]; bullets: string[]; variants: {
    asin: string; title?: string; image?: string; price?: string; url: string;
    rating?: number; rating_count?: number; recent_sales_signal?: string;
  }[];
};

const uploadGuides = [
  ["卖家精灵关键词表", "提供真实搜索量、竞品覆盖和流量词。没有时搜索量显示未知。", ".xlsx,.xls,.csv"],
  ["ABA / SQP 报告", "用于判断搜索词排名、点击和购买表现。", ".xlsx,.xls,.csv"],
  ["广告搜索词报告", "识别已经产生点击和转化的投放词。", ".xlsx,.xls,.csv"],
  ["品牌规范 / 禁用词", "约束品牌表达、侵权词、禁用词和公司规则。", ".xlsx,.xls,.csv,.txt,.docx,.pdf"],
];

export default function MarketWorkspace() {
  const [asin, setAsin] = useState("");
  const [marketplace, setMarketplace] = useState("US");
  const [product, setProduct] = useState<Product | null>(null);
  const [imagePreview, setImagePreview] = useState("");
  const [facts, setFacts] = useState({ category: "", material: "", style: "", useCase: "", mustHave: "" });
  const [files, setFiles] = useState<Record<string, string>>({});
  const [manualAsins, setManualAsins] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  const selected = useMemo(() => candidates.filter(item => item.selected), [candidates]);

  async function readProduct(event: FormEvent) {
    event.preventDefault();
    if (!/^[A-Z0-9]{10}$/.test(asin)) return setMessage("请输入有效的 10 位本品 ASIN。");
    setLoading("product"); setMessage("正在调用本机 Chrome 读取本品真实资料…");
    try {
      const response = await fetch(`${API}/api/scrape/batch`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asins: [asin], marketplace, max_review_pages: 0, headless: false, variant_mode: "fast" }),
      });
      const batch = await response.json();
      if (!response.ok || !batch.items?.[0]?.success) throw new Error(batch.detail || batch.items?.[0]?.error || "读取失败");
      setProduct(batch.items[0].result);
      setMessage("本品资料已读取。请确认图片和商品事实，再发现竞品。");
    } catch (error) {
      setMessage(error instanceof TypeError ? "请先运行本机“启动真实抓取器.bat”。" : error instanceof Error ? error.message : "读取失败");
    } finally { setLoading(""); }
  }

  async function discover() {
    if (!/^[A-Z0-9]{10}$/.test(asin)) return setMessage("自动发现需要先输入本品 ASIN。");
    setLoading("discover"); setMessage("正在实际搜索 Amazon，并计算图文相似度…");
    try {
      const response = await fetch(`${API}/api/competitors/discover`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asin, marketplace, limit: 12, headless: false }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "竞品发现失败");
      setCandidates(result.candidates.map((item: Candidate, index: number) => ({ ...item, selected: index < 6, source: "amazon_search" })));
      setMessage(`已按“${result.search_query}”找到 ${result.candidates.length} 个疑似竞品，请人工确认。`);
    } catch (error) {
      setMessage(error instanceof TypeError ? "请先运行本机真实抓取器。" : error instanceof Error ? error.message : "竞品发现失败");
    } finally { setLoading(""); }
  }

  async function addManual() {
    const asins = [...new Set(manualAsins.toUpperCase().split(/[\s,;]+/).filter(value => /^[A-Z0-9]{10}$/.test(value)))];
    if (!asins.length) return setMessage("请一行输入一个有效竞品 ASIN。");
    setLoading("manual"); setMessage(`正在读取 ${asins.length} 个人工竞品…`);
    try {
      const response = await fetch(`${API}/api/scrape/batch`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asins, marketplace, max_review_pages: 0, headless: false, variant_mode: "fast" }),
      });
      const batch = await response.json();
      if (!response.ok) throw new Error(batch.detail || "读取失败");
      const added: Candidate[] = batch.items.filter((item: { success: boolean }) => item.success).map((item: { result: Product }) => {
        const result = item.result, variant = result.variants[0];
        return { asin: result.requested_asin, title: variant?.title || result.title, url: variant?.url || `https://www.amazon.com/dp/${result.requested_asin}`, image: variant?.image || result.images[0], price: variant?.price || result.price, rating: variant?.rating, rating_count: variant?.rating_count, recent_sales_signal: variant?.recent_sales_signal, selected: true, source: "manual" as const };
      });
      setCandidates(current => {
        const merged = [...current, ...added];
        return [...new Map(merged.map(item => [item.asin, item])).values()];
      });
      setManualAsins(""); setMessage(`已添加 ${added.length} 个真实竞品。`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "读取失败"); }
    finally { setLoading(""); }
  }

  function uploadImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setImagePreview(URL.createObjectURL(file));
    setMessage("图片已载入。请确认系统需要识别的类目、材质、风格和用途。");
  }

  return <main className="titleApp">
    <header className="topbar"><a className="brand" href="/"><span className="brandMark">采</span><span>采数</span></a><nav><a href="/">数据采集</a><a className="active" href="/titles">标题工作台</a></nav><span className="workspaceStatus"><i /> 真实资料模式</span></header>
    <section className="titleHero"><div><span className="eyebrow"><i /> TITLE COPILOT</span><h1>标题半自动化工作台</h1><p>从真实商品和竞品开始。没有资料也没关系，按页面提示逐项补充。</p></div><div className="workflowBadge"><span>当前阶段</span><b>01 · 资料准备与竞品发现</b><small>所有候选都需要人工确认</small></div></section>
    <div className="marketShell">
      <aside className="studioSteps"><p>真实工作流</p>{[["01","准备本品","ASIN / 图片 / 商品事实"],["02","发现竞品","自动候选 + 人工 ASIN"],["03","确认竞品","排除不相关商品"],["04","关键词资料","ABA / 卖家精灵 / 广告"],["05","标题规则","生成、检查与导出"]].map(([no,title,desc], index) => <button className={index === 0 ? "active" : confirmed && index < 3 ? "done" : ""} key={no}><span>{confirmed && index < 3 ? "✓" : no}</span><div><b>{title}</b><small>{desc}</small></div></button>)}</aside>
      <section className="marketContent">
        <div className="guideBanner"><b>零资料也可以开始</b><span>至少提供“本品 ASIN”或“一张商品主图”。资料越完整，竞品识别和标题选词越可靠。</span></div>
        <article className="panel sourcePanel">
          <div className="panelHead"><div><h3>1. 获取本品真实资料</h3><p>推荐优先使用 ASIN；图片和商品事实用于补充与人工校正</p></div><span className="requiredMark">至少完成一项</span></div>
          <div className="sourceGrid">
            <form className="asinSource" onSubmit={readProduct}><label>本品 ASIN</label><div><input value={asin} maxLength={10} onChange={e => setAsin(e.target.value.toUpperCase().replace(/\s/g, ""))} placeholder="例如 B0XXXXXXXX" /><select value={marketplace} onChange={e => setMarketplace(e.target.value)}><option value="US">美国站</option><option value="UK">英国站</option><option value="DE">德国站</option><option value="JP">日本站</option></select><button disabled={loading === "product"}>{loading === "product" ? "读取中…" : "读取商品"}</button></div>{product && <div className="targetMini">{product.images[0] && <img src={product.images[0]} alt="" />}<span><b>{product.title}</b><small>{product.asin} · {product.price || "价格未展示"} · 五点 {product.bullets.length} 条</small></span></div>}</form>
            <label className="imageSource"><span>上传商品主图</span><input type="file" accept="image/*" onChange={uploadImage} />{imagePreview ? <img src={imagePreview} alt="上传预览" /> : <div><b>＋ 选择图片</b><small>JPG / PNG / WEBP</small></div>}</label>
          </div>
          <div className="factsGrid"><label>类目大词<input value={facts.category} onChange={e => setFacts({...facts, category:e.target.value})} placeholder="例如 Area Rug" /></label><label>材质<input value={facts.material} onChange={e => setFacts({...facts, material:e.target.value})} placeholder="例如 Polyester" /></label><label>风格 / 外观<input value={facts.style} onChange={e => setFacts({...facts, style:e.target.value})} placeholder="例如 Modern Abstract" /></label><label>主要用途<input value={facts.useCase} onChange={e => setFacts({...facts, useCase:e.target.value})} placeholder="例如 Living Room" /></label><label className="wideFact">必须真实具备的卖点<input value={facts.mustHave} onChange={e => setFacts({...facts, mustHave:e.target.value})} placeholder="用逗号分隔，例如 Washable, Non Slip, Low Pile" /></label></div>
        </article>
        <article className="panel discoverPanel">
          <div className="panelHead"><div><h3>2. 发现并确认真实竞品</h3><p>系统找疑似候选，人工决定是否纳入研究</p></div><button onClick={discover} disabled={loading === "discover"}>{loading === "discover" ? "正在搜索…" : "自动发现疑似竞品"}</button></div>
          <div className="manualCompetitors"><textarea value={manualAsins} onChange={e => setManualAsins(e.target.value)} placeholder={"也可以一行一个批量添加竞品 ASIN\nB0XXXXXXXX\nB0YYYYYYYY"} /><button onClick={addManual} disabled={loading === "manual"}>{loading === "manual" ? "读取中…" : "添加人工竞品"}</button></div>
          {message && <div className="marketMessage">{message}</div>}
          {candidates.length ? <div className="candidateGrid">{candidates.map(item => <article className={item.selected ? "candidate selected" : "candidate"} key={item.asin}>{item.image ? <img src={item.image} alt="" /> : <div className="noCandidateImage">无图</div>}<div><div className="candidateMeta"><a href={item.url} target="_blank">{item.asin} ↗</a><span>{item.source === "manual" ? "人工添加" : `图文相似 ${item.overall_similarity ?? "—"}%`}</span></div><h4>{item.title}</h4><p>{item.price || "价格未知"} · ★ {item.rating ?? "—"} · {item.recent_sales_signal || "月销量未知"}</p><label><input type="checkbox" checked={!!item.selected} onChange={() => setCandidates(current => current.map(value => value.asin === item.asin ? {...value, selected:!value.selected} : value))} />纳入竞品研究</label></div></article>)}</div> : <div className="candidateEmpty"><b>还没有竞品候选</b><span>读取本品后点击“自动发现”，或直接批量添加你已知的竞品 ASIN。</span></div>}
          {candidates.length > 0 && <div className="confirmCompetitors"><span>已选择 <b>{selected.length}</b> 个竞品</span><button onClick={() => {setConfirmed(true);setMessage(`已确认 ${selected.length} 个竞品，可进入关键词资料准备。`)}}>确认竞品并锁定本轮研究</button></div>}
        </article>
        <article className="panel uploadPanel">
          <div className="panelHead"><div><h3>3. 补充关键词与公司资料</h3><p>全部为可选；未上传时不会显示虚假搜索量</p></div><span className="selectedCount">{Object.keys(files).length} 个文件</span></div>
          <div className="uploadGrid">{uploadGuides.map(([name,desc,accept]) => <label className="uploadCard" key={name}><input type="file" accept={accept} onChange={e => e.target.files?.[0] && setFiles({...files,[name]:e.target.files[0].name})} /><b>{files[name] ? "✓ " : "＋ "}{name}</b><p>{desc}</p><span>{files[name] || "点击选择文件"}</span></label>)}</div>
        </article>
        <div className="nextPhase"><div><b>下一步：竞品标题结构与关键词池</b><span>只有确认后的真实竞品和已上传的数据会进入分析。</span></div><button disabled={!confirmed}>进入真实竞品研究 →</button></div>
      </section>
    </div>
    <footer><span>采数 · 标题半自动化工作台</span><span>不生成虚假流量，不自动确认竞品</span></footer>
  </main>;
}
