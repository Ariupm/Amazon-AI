"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

const API = "http://127.0.0.1:8765";
const REQUIRED_BACKEND = "keyword-workflow-v6";

type Candidate = {
  asin: string; parent_asin?: string; brand?: string; size?: string;
  title: string; url: string; image?: string; price?: string;
  rating?: number; rating_count?: number; recent_sales_signal?: string;
  monthly_sales_estimate?: number;
  text_similarity?: number; image_similarity?: number; overall_similarity?: number;
  visual_images_compared?: number; visual_reason?: string;
  attribute_similarity?: number; market_similarity?: number; category_match?: boolean;
  auto_selected?: boolean; match_reasons?: string[];
  selected?: boolean; source: "amazon_search" | "manual";
};
type Product = {
  asin: string; requested_asin: string; title: string; brand?: string; price?: string;
  images: string[]; bullets: string[]; variants: {
    asin: string; title?: string; image?: string; price?: string; url: string;
    rating?: number; rating_count?: number; recent_sales_signal?: string;
    bullets?: string[];
  }[];
};
type TaskMode = "optimize" | "new-variant";
type TitleFormat = "classic" | "split";
type KeywordSummary = {
  filename: string; sheet: string; valid: boolean; rows: number;
  keyword_column?: string; volume_columns: string[]; month_columns: string[];
  preview: string[]; warnings: string[];
};

const uploadGuides = [
  { key: "aba", name: "ABA 综合词库", desc: "必填；可以直接包含每月补充的卖家精灵预测搜索量。", accept: ".xlsx,.csv" },
  { key: "negative", name: "否词 / 品牌禁用词库", desc: "建议上传；拦截品牌词、侵权词、禁用词和公司规则。", accept: ".xlsx,.csv,.txt" },
  { key: "seller-sprite", name: "卖家精灵扩展数据", desc: "选填；仅用于补充竞争度、趋势、排名等主词库没有的字段。", accept: ".xlsx,.csv" },
  { key: "ads", name: "广告搜索词报告", desc: "选填；以后有真实点击、订单和转化数据时再补充。", accept: ".xlsx,.csv" },
];

export default function MarketWorkspace() {
  const [taskMode, setTaskMode] = useState<TaskMode>("new-variant");
  const [titleFormat, setTitleFormat] = useState<TitleFormat>("split");
  const [asin, setAsin] = useState("");
  const [marketplace, setMarketplace] = useState("US");
  const [product, setProduct] = useState<Product | null>(null);
  const [imagePreview, setImagePreview] = useState("");
  const [facts, setFacts] = useState({ category: "", material: "", style: "", useCase: "", mustHave: "" });
  const [files, setFiles] = useState<Record<string, string>>({});
  const [manualAsins, setManualAsins] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [message, setMessage] = useState("");
  const [sourceMessage, setSourceMessage] = useState("使用前请先双击项目中的“启动真实抓取器.bat”，再点击读取。");
  const [loading, setLoading] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [newColors, setNewColors] = useState("");
  const [newSizes, setNewSizes] = useState("");
  const [customQueries, setCustomQueries] = useState("");
  const [discoveryMeta, setDiscoveryMeta] = useState<{features:string[];queries:string[];excluded:number;sameBrand:number;collapsed:number;parents:number;brands:number} | null>(null);
  const [searchPages, setSearchPages] = useState(1);
  const [resultLimit, setResultLimit] = useState(24);
  const [candidatePage, setCandidatePage] = useState(1);
  const [backendVersion, setBackendVersion] = useState("");
  const [abaSummary, setAbaSummary] = useState<KeywordSummary | null>(null);
  const [confirmMessage, setConfirmMessage] = useState("");
  const [researchStarted, setResearchStarted] = useState(false);
  const candidatePageSize = 10;

  const selected = useMemo(() => candidates.filter(item => item.selected), [candidates]);
  const colors = useMemo(() => splitLines(newColors), [newColors]);
  const sizes = useMemo(() => splitLines(newSizes), [newSizes]);
  const titleCount = taskMode === "new-variant" ? Math.max(1, colors.length) * Math.max(1, sizes.length) : 1;
  const candidatePages = Math.max(1, Math.ceil(candidates.length / candidatePageSize));
  const visibleCandidates = useMemo(
    () => candidates.slice((candidatePage - 1) * candidatePageSize, candidatePage * candidatePageSize),
    [candidates, candidatePage],
  );

  function splitLines(value: string) {
    return [...new Set(value.split(/\r?\n/).map(item => item.trim()).filter(Boolean))];
  }

  function resetDiscovery() {
    setCandidates([]);
    setCustomQueries("");
    setDiscoveryMeta(null);
    setCandidatePage(1);
    setConfirmed(false);
    setConfirmMessage("");
    setResearchStarted(false);
  }

  async function ensureCurrentBackend() {
    let response: Response;
    try {
      response = await fetch(`${API}/health?time=${Date.now()}`, { cache: "no-store" });
    } catch {
      throw new Error("请先运行本项目中的“启动真实抓取器.bat”。");
    }
    const health = await response.json();
    setBackendVersion(health.version || health.feature_version || "未知");
    if (!response.ok || health.feature_version !== REQUIRED_BACKEND) {
      throw new Error("检测到旧版本机抓取器仍占用 8765 端口。请关闭旧抓取器窗口，再重新双击本项目中的“启动真实抓取器.bat”。");
    }
  }

  async function readProduct(event: FormEvent) {
    event.preventDefault();
    if (!/^[A-Z0-9]{10}$/.test(asin)) {
      setSourceMessage(`请输入有效的 10 位${taskMode === "new-variant" ? "父体" : "子体"} ASIN。`);
      return;
    }
    setLoading("product");
    setSourceMessage("正在检查本机抓取器版本…");
    try {
      await ensureCurrentBackend();
      setSourceMessage("本机抓取器版本正确，正在打开 Chrome 读取 Amazon 真实页面…");
      const response = await fetch(`${API}/api/scrape/batch`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asins: [asin], marketplace, max_review_pages: 0, headless: false, variant_mode: "fast" }),
      });
      const batch = await response.json();
      if (!response.ok || !batch.items?.[0]?.success) throw new Error(batch.detail || batch.items?.[0]?.error || "读取失败");
      setProduct(batch.items[0].result);
      resetDiscovery();
      setSourceMessage(taskMode === "new-variant" ? `父体读取完成：已取得 ${batch.items[0].result.variants?.length || 0} 个现有子体，后续竞品搜索会全部排除。` : "该子体资料已读取。请确认商品事实，再发现竞品。");
    } catch (error) {
      setSourceMessage(error instanceof TypeError ? "未连接到本机抓取器。请双击当前项目中的“启动真实抓取器.bat”，看到“最新版真实抓取器已启动”后再试。" : error instanceof Error ? error.message : "读取失败");
    } finally { setLoading(""); }
  }

  async function discover() {
    if (!/^[A-Z0-9]{10}$/.test(asin)) return setMessage("自动发现需要先输入本品 ASIN。");
    setLoading("discover"); setMessage("正在搜索 Amazon，并进入候选详情识别品牌、尺寸和父体；随后执行多图视觉比对与月销量排序…");
    try {
      await ensureCurrentBackend();
      const response = await fetch(`${API}/api/competitors/discover`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          asin, marketplace, limit: resultLimit, search_pages: searchPages, headless: false,
          category: facts.category || null, material: facts.material || null,
          style: facts.style || null, use_case: facts.useCase || null,
          brand: product?.brand || null,
          features: facts.mustHave.split(/[,，\n]+/).map(value => value.trim()).filter(Boolean),
          search_queries: customQueries.split(/\r?\n/).map(value => value.trim()).filter(Boolean),
          exclude_asins: product ? [product.asin, product.requested_asin, ...product.variants.map(variant => variant.asin)] : [],
          reference_titles: product ? [product.title, ...product.variants.map(variant => variant.title || "")].filter(Boolean) : [],
          reference_bullets: product ? [...product.bullets, ...product.variants.flatMap(variant => variant.bullets || [])] : [],
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "竞品发现失败");
      setCandidates(result.candidates.map((item: Candidate) => ({ ...item, selected: item.auto_selected, source: "amazon_search" })));
      setCandidatePage(1);
      const returnedQueries = result.search_queries || [];
      setDiscoveryMeta({
        features: result.target_features || [], queries: returnedQueries,
        excluded: result.excluded_own_asins || 0, sameBrand: result.excluded_same_brand || 0,
        collapsed: result.collapsed_same_brand_size || 0,
        parents: result.competitor_parent_count || 0, brands: result.competitor_brand_count || 0,
      });
      setCustomQueries(returnedQueries.join("\n"));
      const selectedCount = result.candidates.filter((item: Candidate) => item.auto_selected).length;
      setMessage(`已按月销量信号从高到低排序；同品牌同尺寸合并 ${result.collapsed_same_brand_size || 0} 个重复候选，当前覆盖 ${result.competitor_brand_count || 0} 个品牌、${result.competitor_parent_count || 0} 个父体，保留 ${result.candidates.length} 个候选，其中 ${selectedCount} 个达到 60 分门槛。`);
    } catch (error) {
      setMessage(error instanceof TypeError ? "请先运行本机真实抓取器。" : error instanceof Error ? error.message : "竞品发现失败");
    } finally { setLoading(""); }
  }

  async function exportCompetitors(mode: "all" | "selected") {
    const items = mode === "selected" ? selected : candidates;
    if (!items.length) return setMessage(mode === "selected" ? "请先勾选需要导出的竞品。" : "当前没有可导出的竞品。");
    setLoading("export");
    try {
      const response = await fetch(`${API}/api/competitors/export/xlsx`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_asin: asin, items }),
      });
      if (!response.ok) throw new Error("竞品表格生成失败");
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `竞品候选-${asin || "未命名"}.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage(`已导出 ${items.length} 个竞品候选，表格第一列包含商品图片。`);
    } catch (error) {
      setMessage(error instanceof TypeError ? "请先启动本机真实抓取器。" : error instanceof Error ? error.message : "导出失败");
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

  function lockCompetitors() {
    if (!selected.length) {
      setConfirmMessage("请至少勾选 1 个竞品后再锁定。");
      return;
    }
    setConfirmed(true);
    setConfirmMessage(`✓ 已锁定 ${selected.length} 个竞品，本轮研究将只使用这些商品。`);
    setMessage(`已确认 ${selected.length} 个竞品，正在进入关键词资料。`);
    setTimeout(() => document.getElementById("keyword-materials")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  async function handleReferenceFile(key: string, file?: File) {
    if (!file) return;
    setFiles(current => ({ ...current, [key]: file.name }));
    setResearchStarted(false);
    if (key !== "aba") return;
    setAbaSummary(null);
    setLoading("aba");
    try {
      await ensureCurrentBackend();
      const response = await fetch(`${API}/api/keywords/inspect?filename=${encodeURIComponent(file.name)}`, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "ABA 词库读取失败");
      setAbaSummary(result);
      setMessage(result.valid
        ? `ABA 词库读取完成：识别 ${result.rows} 个关键词。`
        : `ABA 文件已上传，但未识别到有效关键词列。`);
    } catch (error) {
      setAbaSummary({
        filename: file.name, sheet: "", valid: false, rows: 0,
        volume_columns: [], month_columns: [], preview: [],
        warnings: [error instanceof Error ? error.message : "ABA 词库读取失败"],
      });
    } finally {
      setLoading("");
    }
  }

  function uploadImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setImagePreview(URL.createObjectURL(file));
    setMessage("图片已载入。请确认系统需要识别的类目、材质、风格和用途。");
  }

  const nextBlockers = [
    !product ? "尚未读取本品" : "",
    !confirmed ? "尚未确认并锁定竞品" : "",
    taskMode === "new-variant" && !colors.length ? "尚未填写新增颜色" : "",
    taskMode === "new-variant" && !sizes.length ? "尚未填写新增尺寸" : "",
    !abaSummary?.valid ? "ABA 综合词库尚未通过读取校验" : "",
  ].filter(Boolean);

  function enterResearch() {
    if (nextBlockers.length) return;
    setResearchStarted(true);
    setTimeout(() => document.getElementById("title-research")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  return <main className="titleApp">
    <header className="topbar"><a className="brand" href="/"><span className="brandMark">采</span><span>采数</span></a><nav><a href="/">数据采集</a><a className="active" href="/titles">标题工作台</a></nav><span className="workspaceStatus"><i /> 真实资料模式</span></header>
    <section className="titleHero"><div><span className="eyebrow"><i /> TITLE COPILOT</span><h1>标题半自动化工作台</h1><p>读取真实商品、竞品与关键词资料，为现有商品优化标题，或为新增颜色和尺寸编写标题。</p></div><div className="workflowBadge"><span>当前阶段</span><b>01 · 明确标题任务</b><small>AI 生成候选，人工确认最终版本</small></div></section>
    <div className="marketShell">
      <aside className="studioSteps"><p>真实工作流</p>{[["01","选择任务","修改标题 / 新增变体标题"],["02","准备本品","ASIN / 产品部资料"],["03","竞品研究","自动候选 + 人工 ASIN"],["04","关键词资料","ABA / 否词 / 选填资料"],["05","生成标题","规则检查、确认与导出"]].map(([no,title,desc], index) => {
        const currentStep = researchStarted ? 4 : confirmed ? 3 : product ? 2 : 1;
        const done = index < currentStep;
        return <button className={index === currentStep ? "active" : done ? "done" : ""} key={no}><span>{done ? "✓" : no}</span><div><b>{title}</b><small>{desc}</small></div></button>;
      })}</aside>
      <section className="marketContent">
        <div className="guideBanner"><b>先选择本次任务</b><span>修改标题读取具体子体；新增颜色或尺寸的标题读取父体，并继承同父体下已经验证的真实商品信息。</span></div>
        <article className="panel taskPanel">
          <div className="panelHead"><div><h3>1. 选择标题任务</h3><p>两种任务需要的 ASIN 和生成逻辑不同</p></div><span className="requiredMark">必选</span></div>
          <div className="taskChoices">
            <button className={taskMode === "optimize" ? "selected" : ""} onClick={() => { setTaskMode("optimize"); setProduct(null); resetDiscovery(); }}>
              <span>修改</span><b>优化现有商品标题</b><p>输入具体子体 ASIN，仅优化该商品；保留其真实颜色、尺寸和卖点。</p>
            </button>
            <button className={taskMode === "new-variant" ? "selected" : ""} onClick={() => { setTaskMode("new-variant"); setProduct(null); resetDiscovery(); }}>
              <span>新增</span><b>编写新增变体标题</b><p>输入父体 ASIN，再填写将新增的颜色与尺寸；这里只写标题，不负责创建变体。</p>
            </button>
          </div>
        </article>
        <article className="panel sourcePanel">
          <div className="panelHead"><div><h3>2. 获取本品真实资料</h3><p>{taskMode === "new-variant" ? "读取父体和现有子体，提炼同系列可继承的标题骨架与真实卖点" : "读取需要修改标题的具体子体，只使用该商品真实具备的属性"}</p></div><span className="requiredMark">ASIN 必填</span></div>
          <div className="sourceGrid">
            <form className="asinSource" onSubmit={readProduct}><label>{taskMode === "new-variant" ? "父体 ASIN" : "需要修改的子体 ASIN"}</label><div><input value={asin} maxLength={10} onChange={e => {setAsin(e.target.value.toUpperCase().replace(/\s/g, ""));setProduct(null);resetDiscovery();}} placeholder="例如 B0XXXXXXXX" /><select value={marketplace} onChange={e => {setMarketplace(e.target.value);resetDiscovery();}}><option value="US">美国站</option><option value="UK">英国站</option><option value="DE">德国站</option><option value="JP">日本站</option></select><button disabled={loading === "product"}>{loading === "product" ? "读取中…" : taskMode === "new-variant" ? "读取父体" : "读取子体"}</button></div>{product && <div className="targetMini">{product.images[0] && <img src={product.images[0]} alt="" />}<span><b>{product.title}</b><small>{product.asin} · {product.price || "价格未展示"} · 五点 {product.bullets.length} 条{taskMode === "new-variant" ? ` · 已读取 ${product.variants.length} 个现有子体；这些 ASIN 会全部排除` : ""}</small></span></div>}</form>
            <label className="imageSource"><span>上传产品部资料图</span><input type="file" accept="image/*,.pdf" onChange={uploadImage} />{imagePreview ? <img src={imagePreview} alt="上传预览" /> : <div><b>＋ 选择资料</b><small>产品结构、材质、工艺、洗护与可证明卖点</small></div>}</label>
          </div>
          <div className={`sourceStatus ${loading === "product" ? "working" : product ? "success" : "notice"}`}><i /> <span>{sourceMessage}</span></div>
          {taskMode === "new-variant" && <div className="variantTitleInputs">
            <div className="variantIntro"><b>新增标题变量</b><span>一行一个；系统按颜色 × 尺寸生成标题。新 ASIN 由商品在 Amazon 创建后产生，此处不需要填写。</span></div>
            <label>新增颜色<textarea value={newColors} onChange={e => setNewColors(e.target.value)} placeholder={"Beige\nDark Green\nBrown"} /></label>
            <label>新增尺寸<textarea value={newSizes} onChange={e => setNewSizes(e.target.value)} placeholder={"2' x 3'\n5' x 7'\n8' x 10'"} /></label>
            <div className="combinationCount"><span>预计生成</span><b>{titleCount}</b><small>个标题候选</small></div>
          </div>}
          <div className="titleFormatRow"><div><b>标题制式</b><span>生成前仍可切换</span></div><button className={titleFormat === "classic" ? "selected" : ""} onClick={() => setTitleFormat("classic")}><b>原标题</b><small>完整标题 ≤ 200 字符</small></button><button className={titleFormat === "split" ? "selected" : ""} onClick={() => setTitleFormat("split")}><b>二段标题</b><small>主标题 ≤ 75 + Highlight Item ≤ 125</small></button></div>
          <div className="factsGrid"><label>类目大词<input value={facts.category} onChange={e => setFacts({...facts, category:e.target.value})} placeholder="例如 Area Rug" /></label><label>材质<input value={facts.material} onChange={e => setFacts({...facts, material:e.target.value})} placeholder="例如 Polyester" /></label><label>风格 / 外观<input value={facts.style} onChange={e => setFacts({...facts, style:e.target.value})} placeholder="例如 Modern Abstract" /></label><label>主要用途<input value={facts.useCase} onChange={e => setFacts({...facts, useCase:e.target.value})} placeholder="例如 Living Room" /></label><label className="wideFact">必须真实具备的卖点<input value={facts.mustHave} onChange={e => setFacts({...facts, mustHave:e.target.value})} placeholder="用逗号分隔，例如 Washable, Non Slip, Low Pile" /></label></div>
        </article>
        <article className="panel discoverPanel">
          <div className="panelHead"><div><h3>3. 发现并确认真实竞品</h3><p>先识别花型、工艺、纹理和功能；尺寸不进入系统搜索词{backendVersion && <em className="backendVersion"> · 本机 v{backendVersion}</em>}</p></div><div className="discoverActions"><label>Amazon 翻页<select value={searchPages} onChange={e => setSearchPages(Number(e.target.value))}><option value={1}>1 页</option><option value={2}>2 页</option><option value={3}>3 页</option></select></label><label>最多保留<select value={resultLimit} onChange={e => setResultLimit(Number(e.target.value))}><option value={24}>24 个</option><option value={40}>40 个</option><option value={60}>60 个</option></select></label><button onClick={discover} disabled={loading === "discover" || !product}>{loading === "discover" ? "正在搜索…" : "自动发现疑似竞品"}</button></div></div>
          <div className="competitorRules"><b>筛选与排序</b><span>类目不一致直接排除</span><span>同品牌＋同尺寸只留 1 款</span><span>月销量信号优先排序</span><span>真实属性 35%</span><span>标题特征 30%</span><span>多图视觉 20%</span><span>价格与市场信号 15%</span><small>视觉分比较去白底后的轮廓 55%＋纹理边缘 25%＋颜色 20%，取多图最佳两组均值。</small></div>
          {discoveryMeta && <div className="discoveryProfile"><div><b>本品特征画像</b><p>{discoveryMeta.features.length ? discoveryMeta.features.join(" · ") : "页面未识别到足够的差异化特征，请补充上方产品事实。"}</p></div><label><b>实际搜索词（可修改后一行一组，再次搜索）</b><textarea value={customQueries} onChange={event => setCustomQueries(event.target.value)} /></label><small>已排除本父体 {discoveryMeta.excluded} 个 ASIN及 {discoveryMeta.sameBrand} 个本品牌搜索结果；合并 {discoveryMeta.collapsed} 个同品牌同尺寸重复项，当前覆盖 {discoveryMeta.brands} 个竞品品牌、{discoveryMeta.parents} 个父体。修改搜索词后可再次搜索。</small></div>}
          <div className="manualCompetitors"><textarea value={manualAsins} onChange={e => setManualAsins(e.target.value)} placeholder={"也可以一行一个批量添加竞品 ASIN\nB0XXXXXXXX\nB0YYYYYYYY"} /><button onClick={addManual} disabled={loading === "manual"}>{loading === "manual" ? "读取中…" : "添加人工竞品"}</button></div>
          {message && <div className="marketMessage">{message}</div>}
          {candidates.length ? <><div className="candidateToolbar"><span>共 {candidates.length} 个候选 · 月销量信号优先 · 第 {candidatePage}/{candidatePages} 页</span><div><button onClick={() => exportCompetitors("selected")} disabled={loading === "export"}>导出已选 XLSX</button><button onClick={() => exportCompetitors("all")} disabled={loading === "export"}>导出全部 XLSX</button></div></div><div className="candidateGrid">{visibleCandidates.map(item => <article className={item.selected ? "candidate selected" : "candidate"} key={item.asin}>{item.image ? <img src={item.image} alt="" /> : <div className="noCandidateImage">无图</div>}<div><div className="candidateMeta"><a href={item.url} target="_blank">{item.asin} ↗</a><span>{item.source === "manual" ? "人工添加" : `竞品匹配 ${item.overall_similarity ?? "—"}分`}</span></div><div className="candidateIdentity"><b>{item.brand || "品牌未识别"}</b><span>{item.size || "尺寸未识别"}</span>{item.parent_asin && <span>父体 {item.parent_asin}</span>}</div><h4>{item.title}</h4><p>{item.price || "价格未知"} · ★ {item.rating ?? "—"} · {item.recent_sales_signal || "月销量未知"}{item.monthly_sales_estimate ? `（按 ${item.monthly_sales_estimate.toLocaleString()} 排序）` : ""}</p>{item.source !== "manual" && <><div className="scoreBreakdown"><span>标题特征 {item.text_similarity ?? "—"}</span><span>属性 {item.attribute_similarity ?? "—"}</span><span title={item.visual_reason || ""}>视觉 {item.image_similarity ?? "—"} · {item.visual_images_compared || 0} 组</span><span>市场 {item.market_similarity ?? "—"}</span></div><p className="visualReason">{item.visual_reason}</p><p className="matchReasons">{item.match_reasons?.join(" · ") || "等待人工核验"}</p></>}<label><input type="checkbox" checked={!!item.selected} onChange={() => setCandidates(current => current.map(value => value.asin === item.asin ? {...value, selected:!value.selected} : value))} />纳入竞品研究</label></div></article>)}</div><div className="candidatePagination"><button disabled={candidatePage <= 1} onClick={() => setCandidatePage(page => page - 1)}>← 上一页</button><span>{candidatePage} / {candidatePages}</span><button disabled={candidatePage >= candidatePages} onClick={() => setCandidatePage(page => page + 1)}>下一页 →</button></div></> : <div className="candidateEmpty"><b>还没有竞品候选</b><span>请先读取父体，再点击“自动发现”；系统会把已读取的全部本品子体排除。</span></div>}
          {candidates.length > 0 && <div className="confirmCompetitors"><div><span>已选择 <b>{selected.length}</b> 个竞品</span>{confirmMessage && <small className={confirmed ? "confirmSuccess" : "confirmError"}>{confirmMessage}</small>}</div><button className={confirmed ? "locked" : ""} onClick={lockCompetitors}>{confirmed ? `✓ 已锁定 ${selected.length} 个竞品` : "确认竞品并锁定本轮研究"}</button></div>}
        </article>
        <article className="panel uploadPanel" id="keyword-materials">
          <div className="panelHead"><div><h3>4. 补充关键词与公司资料</h3><p>ABA 综合词库必填；卖家精灵扩展数据和广告报告均为选填</p></div><span className="selectedCount">{Object.keys(files).length} 个文件</span></div>
          <div className="uploadGrid">{uploadGuides.map(guide => <label className={`uploadCard ${guide.key === "aba" ? "requiredUpload" : ""}`} key={guide.key}><input type="file" accept={guide.accept} onChange={e => handleReferenceFile(guide.key, e.target.files?.[0])} /><b>{files[guide.key] ? "✓ " : "＋ "}{guide.name}{guide.key === "aba" && <em>必填</em>}</b><p>{guide.desc}</p><span>{files[guide.key] || "点击选择文件"}</span></label>)}</div>
          {loading === "aba" && <div className="fileInspection working">正在读取 ABA 表头、关键词列和搜索量列…</div>}
          {abaSummary && <div className={abaSummary.valid ? "fileInspection success" : "fileInspection error"}><b>{abaSummary.valid ? `✓ 已识别 ${abaSummary.rows} 个关键词` : "ABA 词库未通过校验"}</b><span>{abaSummary.keyword_column ? `关键词列：${abaSummary.keyword_column}` : "未找到关键词列"}{abaSummary.volume_columns.length ? ` · 搜索量列：${abaSummary.volume_columns.join("、")}` : " · 未找到搜索量列"}{abaSummary.sheet ? ` · 工作表：${abaSummary.sheet}` : ""}</span>{abaSummary.warnings.map(warning => <small key={warning}>{warning}</small>)}</div>}
        </article>
        <div className="nextPhase"><div><b>下一步：竞品标题结构、关键词池与标题候选</b><span>{nextBlockers.length ? `还需完成：${nextBlockers.join("；")}` : taskMode === "new-variant" ? `资料完整，可为 ${titleCount} 个颜色/尺寸组合进入研究。` : "资料完整，可进入当前子体标题研究。"}</span></div><button disabled={!!nextBlockers.length} onClick={enterResearch}>{researchStarted ? "✓ 已进入标题研究" : "进入真实标题研究 →"}</button></div>
        {researchStarted && <article className="panel researchPanel" id="title-research"><div className="panelHead"><div><h3>5. 真实标题研究</h3><p>本轮研究输入已锁定；后续标题候选只使用真实商品、已选竞品和已读取词库。</p></div><span className="selectedCount">输入已就绪</span></div><div className="researchInputs"><div><span>本品</span><b>{product?.asin}</b><small>{product?.title}</small></div><div><span>竞品</span><b>{selected.length} 个已锁定</b><small>同品牌同尺寸已归并</small></div><div><span>ABA 词库</span><b>{abaSummary?.rows || 0} 个关键词</b><small>{abaSummary?.volume_columns.length ? `已识别 ${abaSummary.volume_columns.length} 个搜索量字段` : "未识别搜索量字段"}</small></div><div><span>标题任务</span><b>{taskMode === "new-variant" ? `${titleCount} 个新增变体组合` : "优化当前子体"}</b><small>{titleFormat === "split" ? "二段标题制式" : "原标题制式"}</small></div></div></article>}
      </section>
    </div>
    <footer><span>采数 · 标题半自动化工作台</span><span>不生成虚假流量，不自动确认竞品</span></footer>
  </main>;
}
