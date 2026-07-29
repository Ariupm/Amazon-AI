"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

const API = "http://127.0.0.1:8765";
const REQUIRED_BACKEND = "natural-title-composition-v24";

type Candidate = {
  asin: string; parent_asin?: string; brand?: string; size?: string;
  title: string; url: string; image?: string; price?: string;
  rating?: number; rating_count?: number; recent_sales_signal?: string;
  monthly_sales_estimate?: number;
  text_similarity?: number; image_similarity?: number; overall_similarity?: number;
  product_type_similarity?: number; market_value?: number;
  visual_images_compared?: number; visual_reason?: string;
  attribute_similarity?: number; market_similarity?: number; category_match?: boolean;
  auto_selected?: boolean; match_reasons?: string[];
  selected?: boolean; source: "amazon_search" | "manual";
};
type Product = {
  asin: string; requested_asin: string; title: string; brand?: string; price?: string;
  parent_asin?: string; is_parent_request?: boolean; suspected_main_asin?: string;
  suspected_main_confidence?: "high" | "medium" | "low"; suspected_main_reason?: string;
  images: string[]; bullets: string[]; variants: {
    asin: string; title?: string; image?: string; price?: string; url: string; color?: string; size?: string;
    rating?: number; rating_count?: number; recent_sales_signal?: string;
    monthly_sales_estimate?: number; is_suspected_main?: boolean; main_score?: number; main_reason?: string;
    bullets?: string[];
  }[];
};
type TaskMode = "optimize" | "new-variant" | "new-product";
type OptimizeScope = "family" | "single";
type TitleFormat = "classic" | "split";
type KeywordSummary = {
  filename: string; sheet: string; valid: boolean; rows: number;
  keyword_column?: string; volume_columns: string[]; month_columns: string[];
  preview: string[]; warnings: string[];
  keywords: { term: string; volume?: number; month?: string }[];
};
type GeneratedTitle = {
  id: string; color?: string; size?: string; main_title: string;
  highlight_item?: string; full_title: string; main_count: number;
  highlight_count: number; full_count: number; keywords_used: string[];
  warnings: string[];
  strategy: "traffic" | "click" | "balanced"; score: number;
  keyword_evidence: string[]; unused_keywords: string[]; ad_keywords: string[];
};
type KeywordAnalysis = {
  term: string; volume?: number; month?: string; rank?: number;
  relevance: number; role: string; reason: string;
  cluster: string; recommended_placement: KeywordPlacement;
  purchase_intent: number; click_value: number; total_score: number;
};
type KeywordPlacement = "main" | "highlight" | "ads" | "exclude";
type KeywordSelection = { term: string; placement: KeywordPlacement; enabled: boolean };
type SizeScenario = {
  size?: string; product_type: string; primary_scenes: string[];
  secondary_scenes: string[]; reasoning: string;
};
type CompetitorTitleAnalysis = {
  sample_size: number; common_openings: string[]; common_features: string[];
  recommended_structure: string; consumer_note: string;
  dominant_formula: string; formula_coverage_percent: number;
  common_slot_orders: string[]; position_insights: string[];
  median_length: number; length_range: string; anti_patterns: string[];
  punctuation_insights: string[];
};
type CompetitorTermAnalysis = {
  term: string; document_frequency: number; weighted_frequency: number;
  coverage_percent: number; matched_facts: string[];
  recommended_placement: "main" | "highlight" | "reference";
};
type SizeCompetitorStudy = {
  size: string; sample_size: number; dominant_formula: string;
  formula_coverage_percent: number; frequent_terms: CompetitorTermAnalysis[];
  aba_terms: KeywordAnalysis[]; note: string;
};
type SearchPlan = {
  productType: string; directDefinition: string; excludedTerms: string;
  features: string[]; guidance: string[];
};
type WeightedQuery = { query: string; weight: number; enabled: boolean };
type PainInsight = {
  phrase: string; mentions: number; evidence: string[]; sourcePhrases: string[];
  improvement: string; confirmed: boolean; selected: boolean; example: string;
};

const uploadGuides = [
  { key: "aba", name: "ABA 综合词库", desc: "必填；可以直接包含每月补充的卖家精灵预测搜索量。", accept: ".xlsx,.csv" },
  { key: "negative", name: "否词 / 品牌禁用词库", desc: "建议上传；拦截品牌词、侵权词、禁用词和公司规则。", accept: ".xlsx,.csv,.txt" },
  { key: "seller-sprite", name: "卖家精灵扩展数据", desc: "选填；仅用于补充竞争度、趋势、排名等主词库没有的字段。", accept: ".xlsx,.csv" },
  { key: "ads", name: "广告搜索词报告", desc: "选填；以后有真实点击、订单和转化数据时再补充。", accept: ".xlsx,.csv" },
];

export default function MarketWorkspace() {
  const [taskMode, setTaskMode] = useState<TaskMode>("new-variant");
  const [optimizeScope, setOptimizeScope] = useState<OptimizeScope>("family");
  const [titleFormat, setTitleFormat] = useState<TitleFormat>("split");
  const [asin, setAsin] = useState("");
  const [marketplace, setMarketplace] = useState("US");
  const [product, setProduct] = useState<Product | null>(null);
  const [mainChildAsin, setMainChildAsin] = useState("");
  const [imagePreview, setImagePreview] = useState("");
  const [imageData, setImageData] = useState("");
  const [facts, setFacts] = useState({ brand: "", productName: "", category: "", material: "", style: "", useCase: "", mustHave: "" });
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
  const [weightedQueries, setWeightedQueries] = useState<WeightedQuery[]>([]);
  const [searchPlan, setSearchPlan] = useState<SearchPlan | null>(null);
  const [discoveryMeta, setDiscoveryMeta] = useState<{features:string[];queries:string[];excluded:number;sameBrand:number;collapsed:number;parents:number;brands:number;cards:number;unique:number;ownResults:number;termFiltered:number;typeFiltered:number;pool:number} | null>(null);
  const [searchPages, setSearchPages] = useState(1);
  const [verifyDetailPages, setVerifyDetailPages] = useState(false);
  const [resultLimit, setResultLimit] = useState(24);
  const [candidatePage, setCandidatePage] = useState(1);
  const [backendVersion, setBackendVersion] = useState("");
  const [abaSummary, setAbaSummary] = useState<KeywordSummary | null>(null);
  const [confirmMessage, setConfirmMessage] = useState("");
  const [researchStarted, setResearchStarted] = useState(false);
  const [nextNotice, setNextNotice] = useState("");
  const [generatedTitles, setGeneratedTitles] = useState<GeneratedTitle[]>([]);
  const [trafficKeywords, setTrafficKeywords] = useState<{ term: string; volume?: number; month?: string; rank?: number }[]>([]);
  const [keywordAnalysis, setKeywordAnalysis] = useState<KeywordAnalysis[]>([]);
  const [keywordSelections, setKeywordSelections] = useState<KeywordSelection[]>([]);
  const [keywordPlanMessage, setKeywordPlanMessage] = useState("");
  const [negativeTerms, setNegativeTerms] = useState<string[]>([]);
  const [negativeSummary, setNegativeSummary] = useState<{valid:boolean;rows:number} | null>(null);
  const [sizeScenarios, setSizeScenarios] = useState<SizeScenario[]>([]);
  const [competitorTitleAnalysis, setCompetitorTitleAnalysis] = useState<CompetitorTitleAnalysis | null>(null);
  const [competitorTerms, setCompetitorTerms] = useState<CompetitorTermAnalysis[]>([]);
  const [semanticClusters, setSemanticClusters] = useState<string[]>([]);
  const [sizeCompetitorStudies, setSizeCompetitorStudies] = useState<SizeCompetitorStudy[]>([]);
  const [painInsights, setPainInsights] = useState<PainInsight[]>([]);
  const [reviewCompetitorLimit, setReviewCompetitorLimit] = useState(10);
  const candidatePageSize = 10;

  const selected = useMemo(() => candidates.filter(item => item.selected), [candidates]);
  const colors = useMemo(() => splitLines(newColors), [newColors]);
  const sizes = useMemo(() => splitLines(newSizes), [newSizes]);
  const optimizeVariants = useMemo(() => {
    if (taskMode !== "optimize" || !product) return [];
    const ranked = [...product.variants].sort((a, b) =>
      Number(b.asin === mainChildAsin) - Number(a.asin === mainChildAsin)
      || (b.monthly_sales_estimate || 0) - (a.monthly_sales_estimate || 0)
      || (b.main_score || 0) - (a.main_score || 0)
    );
    const bySize = new Map<string, Product["variants"][number]>();
    ranked.forEach(variant => {
      const key = variant.size?.trim() || "尺寸未识别";
      if (!bySize.has(key)) bySize.set(key, variant);
    });
    return [...bySize.values()];
  }, [taskMode, product, mainChildAsin]);
  const optimizeSizes = useMemo(() => {
    if (optimizeScope === "single") {
      const chosen = product?.variants.find(item => item.asin === mainChildAsin);
      return chosen ? [chosen.size?.trim() || "尺寸未识别"] : [];
    }
    return optimizeVariants.map(item => item.size?.trim() || "尺寸未识别");
  }, [optimizeScope, optimizeVariants, product, mainChildAsin]);
  const titleCount = taskMode === "optimize"
    ? Math.max(1, optimizeSizes.length)
    : Math.max(1, colors.length) * Math.max(1, sizes.length);
  const newProductReady = taskMode === "new-product" && !!facts.category.trim() && !!facts.material.trim() && !!facts.style.trim() && !!facts.mustHave.trim() && sizes.length > 0;
  const sourceReady = taskMode === "new-product" ? newProductReady : !!product;
  const candidatePages = Math.max(1, Math.ceil(candidates.length / candidatePageSize));
  const visibleCandidates = useMemo(
    () => candidates.slice((candidatePage - 1) * candidatePageSize, candidatePage * candidatePageSize),
    [candidates, candidatePage],
  );

  function splitLines(value: string) {
    return [...new Set(value.split(/\r?\n/).map(item => item.trim()).filter(Boolean))];
  }

  function inferCategory(title: string) {
    const normalized = title.toLowerCase();
    if (/\brunner rugs?\b/.test(normalized)) return "Runner Rug";
    if (/\bround (?:area )?rugs?\b/.test(normalized)) return "Round Area Rug";
    if (/\baccent rugs?\b/.test(normalized)) return "Accent Rug";
    if (/\barea rugs?\b/.test(normalized)) return "Area Rug";
    if (/\brugs?\b/.test(normalized)) return "Area Rug";
    return "";
  }

  function extractLabels(corpus: string, rules: { pattern: RegExp; label: string }[]) {
    const matches = rules.flatMap(rule => {
      const match = rule.pattern.exec(corpus);
      rule.pattern.lastIndex = 0;
      return match ? [{ label: rule.label, index: match.index }] : [];
    });
    return [...new Map(matches.sort((a, b) => a.index - b.index).map(item => [item.label, item])).values()]
      .map(item => item.label);
  }

  function inferProductFacts(title: string, bullets: string[]) {
    const corpus = [title, ...bullets].join(" ").replace(/[|/]/g, " ");
    const material = extractLabels(corpus, [
      { pattern: /\bfaux wool\b/i, label: "Faux Wool" },
      { pattern: /\bpolyester\b/i, label: "Polyester" },
      { pattern: /\bpolypropylene\b/i, label: "Polypropylene" },
      { pattern: /\bnylon\b/i, label: "Nylon" },
      { pattern: /\bcotton\b/i, label: "Cotton" },
      { pattern: /\bwool\b/i, label: "Wool" },
      { pattern: /\bjute\b/i, label: "Jute" },
      { pattern: /\bchenille\b/i, label: "Chenille" },
      { pattern: /\bmicrofiber\b/i, label: "Microfiber" },
      { pattern: /\bviscose\b/i, label: "Viscose" },
      { pattern: /\bacrylic\b/i, label: "Acrylic" },
    ]).filter((label, index, items) => label !== "Wool" || !items.includes("Faux Wool"));
    const style = extractLabels(corpus, [
      { pattern: /\bboho\b/i, label: "Boho" },
      { pattern: /\bvintage\b/i, label: "Vintage" },
      { pattern: /\bdistressed\b/i, label: "Distressed" },
      { pattern: /\bmodern\b/i, label: "Modern" },
      { pattern: /\btraditional\b/i, label: "Traditional" },
      { pattern: /\bfarmhouse\b/i, label: "Farmhouse" },
      { pattern: /\bmoroccan\b/i, label: "Moroccan" },
      { pattern: /\bpersian\b/i, label: "Persian" },
      { pattern: /\boriental\b/i, label: "Oriental" },
      { pattern: /\babstract\b/i, label: "Abstract" },
      { pattern: /\bgeometric\b/i, label: "Geometric" },
      { pattern: /\bfloral\b/i, label: "Floral" },
      { pattern: /\btribal\b/i, label: "Tribal" },
      { pattern: /\bminimalist\b/i, label: "Minimalist" },
      { pattern: /\bcontemporary\b/i, label: "Contemporary" },
    ]);
    const useCases = extractLabels(corpus, [
      { pattern: /\bliving room\b/i, label: "Living Room" },
      { pattern: /\bbedroom\b/i, label: "Bedroom" },
      { pattern: /\bdining room\b/i, label: "Dining Room" },
      { pattern: /\bkitchen\b/i, label: "Kitchen" },
      { pattern: /\bhallway\b/i, label: "Hallway" },
      { pattern: /\b(?:entryway|entrance)\b/i, label: "Entryway" },
      { pattern: /\blaundry(?: room)?\b/i, label: "Laundry Room" },
      { pattern: /\bbathroom\b/i, label: "Bathroom" },
      { pattern: /\bnursery\b/i, label: "Nursery" },
      { pattern: /\bhome office\b/i, label: "Home Office" },
    ]);
    const features = extractLabels(corpus, [
      { pattern: /\bmachine washable\b/i, label: "Machine Washable" },
      { pattern: /\bwashable\b/i, label: "Washable" },
      { pattern: /\bnon[- ]?slip\b/i, label: "Non-Slip" },
      { pattern: /\bstain[- ]?resistant\b/i, label: "Stain-Resistant" },
      { pattern: /\blow pile\b/i, label: "Low Pile" },
      { pattern: /\bhigh[- ]?low pile\b/i, label: "High-Low Pile" },
      { pattern: /\bsoft\b/i, label: "Soft" },
      { pattern: /\bnon[- ]?shedding\b/i, label: "Non-Shedding" },
      { pattern: /\bfade[- ]?resistant\b/i, label: "Fade-Resistant" },
      { pattern: /\bwaterproof\b/i, label: "Waterproof" },
      { pattern: /\breversible\b/i, label: "Reversible" },
      { pattern: /\brubber backing\b/i, label: "Rubber Backing" },
      { pattern: /\bTPR backing\b/i, label: "TPR Backing" },
      { pattern: /\btextured\b/i, label: "Textured" },
      { pattern: /\btufted\b/i, label: "Tufted" },
    ]).filter((label, index, items) =>
      (label !== "Washable" || !items.includes("Machine Washable"))
      && (label !== "Low Pile" || !items.includes("High-Low Pile"))
    );
    return {
      category: inferCategory(title),
      material: material.join(", "),
      style: style.join(", "),
      useCase: useCases.join(", "),
      mustHave: features.join(", "),
    };
  }

  function errorDetail(value: unknown, fallback: string) {
    if (typeof value === "string" && value.trim()) return value;
    if (Array.isArray(value)) {
      const messages = value.map(item => {
        if (item && typeof item === "object" && "msg" in item) return String(item.msg);
        return typeof item === "string" ? item : "";
      }).filter(Boolean);
      if (messages.length) return messages.join("；");
    }
    return fallback;
  }

  function resetDiscovery() {
    setCandidates([]);
    setCustomQueries("");
    setWeightedQueries([]);
    setSearchPlan(null);
    setDiscoveryMeta(null);
    setCandidatePage(1);
    setConfirmed(false);
    setConfirmMessage("");
    setResearchStarted(false);
    setNextNotice("");
    setGeneratedTitles([]);
    setTrafficKeywords([]);
    setKeywordAnalysis([]);
    setKeywordSelections([]);
    setKeywordPlanMessage("");
    setSizeScenarios([]);
    setCompetitorTitleAnalysis(null);
    setCompetitorTerms([]);
    setSemanticClusters([]);
    setSizeCompetitorStudies([]);
    setPainInsights([]);
  }

  function recommendedMainChild(loadedProduct: Product) {
    const explicit = loadedProduct.suspected_main_asin
      && loadedProduct.variants.find(item => item.asin === loadedProduct.suspected_main_asin);
    if (explicit) return explicit;
    return [...loadedProduct.variants].sort((a, b) =>
      (b.monthly_sales_estimate || 0) - (a.monthly_sales_estimate || 0)
      || (b.main_score || 0) - (a.main_score || 0)
    )[0];
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
      setSourceMessage(`请输入有效的 10 位${taskMode === "optimize" ? "父体或子体" : taskMode === "new-variant" ? "父体" : "子体"} ASIN。`);
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
      const loadedProduct = batch.items[0].result as Product;
      const recommended = recommendedMainChild(loadedProduct);
      const factTitle = taskMode === "optimize" ? recommended?.title || loadedProduct.title : loadedProduct.title;
      const factBullets = taskMode === "optimize" ? recommended?.bullets || loadedProduct.bullets || [] : loadedProduct.bullets || [];
      const inferred = inferProductFacts(factTitle, factBullets);
      setProduct(loadedProduct);
      setMainChildAsin(taskMode === "optimize" ? recommended?.asin || loadedProduct.asin : "");
      setFacts(current => ({
        ...current,
        brand: current.brand || loadedProduct.brand || "",
        category: current.category || inferred.category,
        material: current.material || inferred.material,
        style: current.style || inferred.style,
        useCase: current.useCase || inferred.useCase,
        mustHave: current.mustHave || inferred.mustHave,
      }));
      resetDiscovery();
      const inferredCount = [inferred.category, inferred.material, inferred.style, inferred.useCase, inferred.mustHave].filter(Boolean).length;
      setSourceMessage(taskMode === "new-variant"
        ? `父体读取完成：已取得 ${batch.items[0].result.variants?.length || 0} 个现有子体，后续竞品搜索会全部排除。已从标题和五点回填 ${inferredCount} 组商品事实，请人工确认。`
        : taskMode === "optimize"
          ? optimizeScope === "family"
            ? `父体读取完成：识别 ${loadedProduct.variants.length} 个子体、${new Set(loadedProduct.variants.map(item => item.size).filter(Boolean)).size} 个尺寸。系统已按公开月销量信号推荐主推子体；请人工确认。`
            : `子体读取完成：本轮只优化所选子体。若 Amazon 同时返回家族数据，仍不会批量生成其他尺寸。`
          : `该子体资料已读取，并从标题和五点回填 ${inferredCount} 组商品事实。请确认后再发现竞品。`);
    } catch (error) {
      setSourceMessage(error instanceof TypeError ? "未连接到本机抓取器。请双击当前项目中的“启动真实抓取器.bat”，看到“最新版真实抓取器已启动”后再试。" : error instanceof Error ? error.message : "读取失败");
    } finally { setLoading(""); }
  }

  function competitorSourcePayload(categoryOverride?: string) {
    const mainVariant = product?.variants.find(item => item.asin === mainChildAsin);
    const targetName = taskMode === "new-product"
      ? [facts.brand, facts.productName || facts.category, facts.material, facts.style, facts.mustHave].filter(Boolean).join(" ")
      : mainVariant?.title || product?.title || "";
    return {
      target_name: targetName.slice(0, 160) || null,
      category: categoryOverride || facts.category || null, material: facts.material || null,
      style: facts.style || null, use_case: facts.useCase || null,
      features: facts.mustHave.split(/[,，\n]+/).map(value => value.trim()).filter(Boolean),
      reference_titles: product ? [product.title, ...product.variants.map(variant => variant.title || "")].filter(Boolean).slice(0, 100) : [],
      reference_bullets: product ? [...product.bullets, ...product.variants.flatMap(variant => variant.bullets || [])].slice(0, 100) : [facts.material, facts.style, facts.useCase, facts.mustHave].filter(Boolean),
    };
  }

  async function prepareSearchPlan() {
    if (!sourceReady) return setMessage(taskMode === "new-product" ? "请先完整填写新品资料。" : "请先读取本品资料。");
    const resolvedCategory = facts.category.trim() || inferCategory(product?.title || "");
    if (!resolvedCategory) {
      setMessage("未能从商品标题识别类目，请填写“类目大词”后再生成搜索方案。");
      setTimeout(() => {
        const field = document.querySelector('input[placeholder="例如 Area Rug"]') as HTMLInputElement | null;
        field?.scrollIntoView({ behavior: "smooth", block: "center" });
        field?.focus();
      }, 50);
      return;
    }
    if (!facts.category.trim()) setFacts(current => ({ ...current, category: resolvedCategory }));
    setLoading("plan"); setMessage("正在整理本品画像、分层搜索词与排除建议，不会访问 Amazon…");
    try {
      await ensureCurrentBackend();
      const response = await fetch(`${API}/api/competitors/plan`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(competitorSourcePayload(resolvedCategory)),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(errorDetail(result.detail, "搜索方案生成失败"));
      setSearchPlan({
        productType: result.product_type,
        directDefinition: result.direct_competitor_definition,
        excludedTerms: (result.excluded_terms || []).join("\n"),
        features: result.target_features || [],
        guidance: result.guidance || [],
      });
      const defaults = [40, 25, 20, 10, 5, 5];
      setWeightedQueries((result.search_queries || []).map((query: string, index: number) => ({
        query, weight: defaults[index] ?? 5, enabled: true,
      })));
      setCustomQueries((result.search_queries || []).join("\n"));
      setCandidates([]); setDiscoveryMeta(null); setConfirmed(false);
      setMessage("搜索方案已生成。请确认产品类型、直接竞品定义、搜索词和排除项，再开始抓取。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "搜索方案生成失败");
    } finally { setLoading(""); }
  }

  async function discover() {
    if (taskMode !== "new-product" && !/^[A-Z0-9]{10}$/.test(asin)) return setMessage("自动发现需要先输入并读取本品 ASIN。");
    if (taskMode === "new-product" && !newProductReady) return setMessage("全新商品请先完整填写类目、材质、风格、产品特征和至少一个尺寸。");
    if (!searchPlan) return setMessage("请先生成并确认竞品搜索方案。");
    const activeQueries = weightedQueries.filter(item => item.enabled && item.query.trim() && item.weight > 0);
    if (!activeQueries.length) return setMessage("请至少启用一组权重大于 0 的搜索词。");
    setLoading("discover"); setMessage(imageData ? `正在按产品事实搜索 Amazon，并用上传图片与候选${verifyDetailPages ? "详情图" : "搜索页主图"}进行视觉比对…` : "正在按产品事实搜索 Amazon；未上传产品图，本轮不计算视觉相似度…");
    try {
      await ensureCurrentBackend();
      const response = await fetch(`${API}/api/competitors/discover`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          asin: taskMode === "new-product" ? null : asin,
          ...competitorSourcePayload(),
          reference_image_data: taskMode === "new-product" ? imageData || null : null,
          marketplace, limit: resultLimit, search_pages: searchPages,
          verify_detail_pages: verifyDetailPages, headless: false,
          product_type: searchPlan.productType,
          direct_competitor_definition: searchPlan.directDefinition,
          excluded_terms: splitLines(searchPlan.excludedTerms),
          brand: product?.brand || facts.brand || null,
          search_queries: activeQueries.map(item => item.query.trim()),
          search_query_weights: Object.fromEntries(activeQueries.map(item => [item.query.trim(), item.weight])),
          exclude_asins: product ? [product.asin, product.requested_asin, ...product.variants.map(variant => variant.asin)] : [],
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
        cards: result.search_card_count || 0, unique: result.unique_search_asins || 0,
        ownResults: result.excluded_own_results || 0, termFiltered: result.excluded_by_terms || 0,
        typeFiltered: result.excluded_by_product_type || 0, pool: result.weighted_pool_count || 0,
      });
      setCustomQueries(returnedQueries.join("\n"));
      const selectedCount = result.candidates.filter((item: Candidate) => item.auto_selected).length;
      setMessage(`已按确认方案完成搜索；同品牌只保留 1 个，合并 ${result.collapsed_same_brand_size || 0} 个重复候选，当前覆盖 ${result.competitor_brand_count || 0} 个品牌，保留 ${result.candidates.length} 个候选，其中 ${selectedCount} 个产品相似度达到 60 分。`);
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
    if (key === "negative") {
      setNegativeSummary(null);
      setLoading("negative");
      try {
        await ensureCurrentBackend();
        const response = await fetch(`${API}/api/keywords/negative/inspect?filename=${encodeURIComponent(file.name)}`, {
          method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "否词词库读取失败");
        setNegativeTerms(result.terms || []);
        setNegativeSummary({ valid: result.valid, rows: result.rows });
        setMessage(`否词词库读取完成：已载入 ${result.rows} 个硬拦截词。`);
      } catch (error) {
        setNegativeTerms([]);
        setNegativeSummary({ valid: false, rows: 0 });
        setMessage(error instanceof Error ? error.message : "否词词库读取失败");
      } finally { setLoading(""); }
      return;
    }
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
        volume_columns: [], month_columns: [], preview: [], keywords: [],
        warnings: [error instanceof Error ? error.message : "ABA 词库读取失败"],
      });
    } finally {
      setLoading("");
    }
  }

  function uploadImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setMessage("视觉比对只支持 JPG、PNG、WEBP 等图片文件。");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setMessage("产品图片不能超过 8 MB。");
      return;
    }
    setImagePreview(URL.createObjectURL(file));
    const reader = new FileReader();
    reader.onload = () => setImageData(typeof reader.result === "string" ? reader.result : "");
    reader.readAsDataURL(file);
    setMessage("产品图已载入；发现竞品时会在本机执行轮廓、纹理边缘和颜色比对。");
  }

  const nextBlockers = [
    !sourceReady ? taskMode === "new-product" ? "全新商品资料未填写完整" : "尚未读取本品" : "",
    !confirmed ? "尚未确认并锁定竞品" : "",
    taskMode === "new-variant" && !colors.length && !sizes.length ? "新增颜色或新增尺寸至少填写一项" : "",
    !abaSummary?.valid ? "ABA 综合词库尚未通过读取校验" : "",
  ].filter(Boolean);

  function enterResearch() {
    if (nextBlockers.length) {
      setNextNotice(`暂时不能进入：${nextBlockers.join("；")}。已为你定位到第一个待完成项。`);
      let targetId = "keyword-materials";
      let focusSelector = "";
      if (!sourceReady) targetId = "product-source";
      else if (!confirmed) targetId = "competitor-discovery";
      else if (taskMode === "new-variant" && !colors.length && !sizes.length) {
        targetId = "variant-title-inputs";
        focusSelector = "#new-colors";
      } else if (taskMode === "new-product" && !sizes.length) {
        targetId = "variant-title-inputs";
        focusSelector = "#new-sizes";
      }
      setTimeout(() => {
        document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "center" });
        if (focusSelector) (document.querySelector(focusSelector) as HTMLTextAreaElement | null)?.focus();
      }, 50);
      return;
    }
    setNextNotice("");
    setResearchStarted(true);
    setTimeout(() => document.getElementById("title-research")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  function titleRequestPayload(includeSelections = true) {
    const confirmedImprovements = painInsights.filter(item => item.confirmed && item.improvement.trim()).map(item => item.improvement.trim());
    const mainVariant = product?.variants.find(item => item.asin === mainChildAsin);
    const targetSizes = taskMode === "optimize" ? optimizeSizes : sizes;
    const normalizeSize = (value?: string) => (value || "").toLowerCase().replace(/[×’′"]/g, "x").replace(/\s+/g, "");
    const competitorTitlesBySize = Object.fromEntries(targetSizes.map(size => {
      const exact = selected.filter(item => normalizeSize(item.size) && normalizeSize(item.size) === normalizeSize(size));
      return [size, exact.slice(0, 20).map(item => item.title)];
    }));
    return {
      brand: product?.brand || facts.brand || null,
      product_title: mainVariant?.title || product?.title || [facts.brand, facts.productName || facts.category, facts.material, facts.style, facts.mustHave].filter(Boolean).join(" "),
      bullets: mainVariant?.bullets || product?.bullets || [facts.material, facts.style, facts.useCase, facts.mustHave].filter(Boolean),
      competitor_titles: selected.map(item => item.title),
      competitor_titles_by_size: competitorTitlesBySize,
      keywords: abaSummary?.keywords || [],
      keyword_selections: includeSelections ? keywordSelections : [],
      negative_terms: negativeTerms,
      category: facts.category || null,
      material: facts.material || null,
      style: facts.style || null,
      use_case: facts.useCase || null,
      must_have: facts.mustHave.split(/[,，\n]+/).map(value => value.trim()).filter(Boolean),
      verified_improvements: confirmedImprovements,
      colors: taskMode === "optimize" ? [] : colors,
      sizes: targetSizes,
      title_format: titleFormat,
    };
  }

  async function exportGeneratedTitles() {
    if (!generatedTitles.length) return setMessage("请先生成标题后再导出。");
    setLoading("title-export");
    try {
      await ensureCurrentBackend();
      const response = await fetch(`${API}/api/titles/export/xlsx`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          parent_asin: product?.parent_asin || (product?.is_parent_request ? product.requested_asin : null),
          main_child_asin: mainChildAsin || null,
          title_format: titleFormat,
          items: generatedTitles.map(item => ({
            asin: optimizeVariants.find(variant => (variant.size?.trim() || "尺寸未识别") === (item.size || "尺寸未识别"))?.asin || null,
            size: item.size || "尺寸未识别", strategy: item.strategy,
            main_title: item.main_title, highlight_item: item.highlight_item || null,
            full_title: item.full_title, score: item.score,
            keywords_used: item.keywords_used, warnings: item.warnings,
          })),
        }),
      });
      if (!response.ok) throw new Error("多尺寸标题表格生成失败");
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `多尺寸标题-${product?.parent_asin || asin || "未命名"}.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage(`已导出 ${new Set(generatedTitles.map(item => item.size || "尺寸未识别")).size} 个尺寸，Excel 第一行按尺寸横向排列。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "标题导出失败");
    } finally { setLoading(""); }
  }

  async function analyzeCompetitorReviews() {
    const targets = selected.slice(0, reviewCompetitorLimit);
    if (!targets.length) return setMessage("请先锁定竞品。");
    setLoading("reviews");
    setMessage(`正在读取前 ${targets.length} 个头部竞品近期评论并提取低星痛点…`);
    try {
      await ensureCurrentBackend();
      const response = await fetch(`${API}/api/scrape/batch`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asins: targets.map(item => item.asin), marketplace, max_review_pages: 1, headless: false, variant_mode: "fast" }),
      });
      const batch = await response.json();
      if (!response.ok) throw new Error(batch.detail || "竞品评论读取失败");
      const rawPains: {phrase:string;mentions:number;evidence:string[]}[] = [];
      for (const item of batch.items || []) {
        for (const pain of item.result?.insights?.pains || []) {
          rawPains.push({ phrase: pain.phrase, mentions: pain.mentions || 0, evidence: pain.evidence || [] });
        }
      }
      const themes = [
        { key:"slip", label:"防滑与安全风险", pattern:/\b(slip|slid|slide|sliding|trip|tripped|dangerous|moves?|moving)\b/i, example:"例如 Reinforced Non-Slip Backing" },
        { key:"thin", label:"轻薄、软塌或不平整", pattern:/\b(thin|flimsy|crease|curl|curled|flat|wrinkle|fold)\b/i, example:"例如 Lay-Flat Construction / Reinforced Body" },
        { key:"print", label:"图案、颜色与实物差异", pattern:/\b(print|printed|color|colour|fade|faded|pattern|beautiful|picture|photo)\b/i, example:"例如 High-Definition Print / Colorfast Surface" },
        { key:"texture", label:"触感与表面质感", pattern:/\b(soft|rough|stiff|stuffed|texture|plush)\b/i, example:"例如 Soft Faux-Wool Surface" },
        { key:"durability", label:"耐用性、掉毛与边缘问题", pattern:/\b(shed|shedding|edge|fray|frayed|tear|torn|durable|durability)\b/i, example:"例如 Reinforced Edges / Non-Shedding Surface" },
        { key:"clean", label:"清洁与机洗表现", pattern:/\b(wash|washed|washing|clean|stain|dryer|drying)\b/i, example:"例如 Machine Washable / Stain-Resistant" },
        { key:"size", label:"尺寸与覆盖范围偏差", pattern:/\b(size|small|smaller|large|larger|short|narrow)\b/i, example:"例如 Accurate Size Labeling" },
        { key:"odor", label:"气味与包装体验", pattern:/\b(smell|odor|odour|chemical|package|packaging)\b/i, example:"例如 Low-Odor Material / Improved Packaging" },
      ];
      const grouped = new Map<string, {label:string;example:string;phrases:Set<string>;evidence:Set<string>;mentions:number}>();
      for (const pain of rawPains) {
        const corpus = `${pain.phrase} ${pain.evidence.join(" ")}`;
        const theme = themes.find(item => item.pattern.test(corpus));
        const key = theme?.key || `other:${pain.phrase.toLowerCase()}`;
        const current = grouped.get(key) || {
          label: theme?.label || pain.phrase, example: theme?.example || "填写我方已实现的具体改进",
          phrases: new Set<string>(), evidence: new Set<string>(), mentions: 0,
        };
        current.phrases.add(pain.phrase);
        pain.evidence.forEach(value => current.evidence.add(value));
        current.mentions = Math.max(current.mentions, pain.mentions || 0, current.evidence.size);
        grouped.set(key, current);
      }
      const insights: PainInsight[] = [...grouped.values()].map(item => ({
        phrase:item.label, mentions:item.mentions, evidence:[...item.evidence].slice(0, 5),
        sourcePhrases:[...item.phrases].slice(0, 6), improvement:"", confirmed:false,
        selected:false, example:item.example,
      })).sort((a, b) => b.mentions - a.mentions).slice(0, 12);
      setPainInsights(insights);
      setMessage(`已从 ${batch.succeeded || 0} 个竞品提取 ${insights.length} 个痛点；只有确认我方改进及证据后才会参与标题。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "竞品评论分析失败");
    } finally { setLoading(""); }
  }

  async function analyzeKeywordPlan() {
    if (!sourceReady || !abaSummary?.valid) return;
    setLoading("keyword-plan");
    setKeywordPlanMessage("正在重新计算流量、事实相关性、风格和建议位置…");
    setMessage("正在按商品事实、流量和头部竞品结构制定关键词布置方案…");
    try {
      await ensureCurrentBackend();
      const response = await fetch(`${API}/api/titles/plan`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(titleRequestPayload(false)),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "关键词方案生成失败");
      const analysis: KeywordAnalysis[] = result.keyword_analysis || [];
      setKeywordAnalysis(analysis);
      setKeywordSelections(analysis.map(item => ({
        term: item.term, placement: item.recommended_placement, enabled: item.recommended_placement !== "exclude",
      })));
      setTrafficKeywords(result.traffic_keywords || []);
      setSizeScenarios(result.size_scenarios || []);
      setCompetitorTitleAnalysis(result.competitor_analysis || null);
      setCompetitorTerms(result.competitor_terms || []);
      setSemanticClusters(result.semantic_clusters || []);
      setSizeCompetitorStudies(result.size_competitor_studies || []);
      setGeneratedTitles([]);
      setKeywordPlanMessage(`✓ 已重新分析 ${analysis.length} 个高相关词；风格匹配词优先建议进入主标题。`);
      setMessage(`已筛出 ${analysis.length} 个高相关流量词。请人工确认位置，再生成标题。`);
    } catch (error) {
      const text = error instanceof Error ? error.message : "关键词方案生成失败";
      setKeywordPlanMessage(`⚠ ${text}`);
      setMessage(text);
    } finally { setLoading(""); }
  }

  async function generateTitleCandidates() {
    if (!sourceReady || !abaSummary?.valid) return;
    setLoading("titles");
    setGeneratedTitles([]);
    setMessage("正在按本品真实属性、已锁定竞品结构和 ABA 流量词生成标题候选…");
    try {
      await ensureCurrentBackend();
      const response = await fetch(`${API}/api/titles/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(titleRequestPayload(true)),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "标题生成失败");
      setGeneratedTitles(result.candidates || []);
      setTrafficKeywords(result.traffic_keywords || []);
      setKeywordAnalysis(result.keyword_analysis || []);
      setSizeScenarios(result.size_scenarios || []);
      setCompetitorTitleAnalysis(result.competitor_analysis || null);
      setCompetitorTerms(result.competitor_terms || []);
      setSemanticClusters(result.semantic_clusters || []);
      setSizeCompetitorStudies(result.size_competitor_studies || []);
      setMessage(`已生成 ${result.candidates?.length || 0} 个真实标题候选，请逐条编辑和人工确认。`);
      setTimeout(() => document.getElementById("generated-titles")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "标题生成失败");
    } finally {
      setLoading("");
    }
  }

  function editGeneratedTitle(id: string, field: "main_title" | "highlight_item", value: string) {
    setGeneratedTitles(current => current.map(item => {
      if (item.id !== id) return item;
      const main = field === "main_title" ? value : item.main_title;
      const highlight = field === "highlight_item" ? value : item.highlight_item || "";
      const full = titleFormat === "split" && highlight ? `${main} | ${highlight}` : main;
      return {
        ...item,
        [field]: value,
        full_title: full,
        main_count: main.length,
        highlight_count: highlight.length,
        full_count: full.length,
      };
    }));
  }

  return <main className="titleApp">
    <header className="topbar"><a className="brand" href="/"><span className="brandMark">采</span><span>采数</span></a><nav><a href="/">数据采集</a><a className="active" href="/titles">标题工作台</a></nav><span className="workspaceStatus"><i /> 真实资料模式</span></header>
    <section className="titleHero"><div><span className="eyebrow"><i /> TITLE COPILOT</span><h1>标题半自动化工作台</h1><p>支持现有商品、父体新增变体，以及没有 ASIN 的全新商品竞品研究与标题编写。</p></div><div className="workflowBadge"><span>当前阶段</span><b>01 · 明确标题任务</b><small>AI 生成候选，人工确认最终版本</small></div></section>
    <div className="marketShell">
      <aside className="studioSteps"><p>真实工作流</p>{[["01","选择任务","修改标题 / 新增变体标题"],["02","准备本品","ASIN / 产品部资料"],["03","竞品研究","自动候选 + 人工 ASIN"],["04","关键词资料","ABA / 否词 / 选填资料"],["05","生成标题","规则检查、确认与导出"]].map(([no,title,desc], index) => {
        const currentStep = researchStarted ? 4 : confirmed ? 3 : sourceReady ? 2 : 1;
        const done = index < currentStep;
        return <button className={index === currentStep ? "active" : done ? "done" : ""} key={no}><span>{done ? "✓" : no}</span><div><b>{title}</b><small>{desc}</small></div></button>;
      })}</aside>
      <section className="marketContent">
        <div className="guideBanner"><b>先选择本次任务</b><span>优化现有商品优先读取父体并批量覆盖全部尺寸；新增变体读取父体；全新商品无需 ASIN。</span></div>
        <article className="panel taskPanel">
          <div className="panelHead"><div><h3>1. 选择标题任务</h3><p>三种任务使用不同的资料与竞品发现逻辑</p></div><span className="requiredMark">必选</span></div>
          <div className="taskChoices">
            <button className={taskMode === "optimize" ? "selected" : ""} onClick={() => { setTaskMode("optimize"); setProduct(null); setMainChildAsin(""); resetDiscovery(); }}>
              <span>修改</span><b>优化现有商品标题</b><p>优先输入父体 ASIN，读取全部尺寸；自动推荐主推子体，也支持人工指定。</p>
            </button>
            <button className={taskMode === "new-variant" ? "selected" : ""} onClick={() => { setTaskMode("new-variant"); setProduct(null); resetDiscovery(); }}>
              <span>新增</span><b>编写新增变体标题</b><p>输入父体 ASIN，再填写将新增的颜色与尺寸；这里只写标题，不负责创建变体。</p>
            </button>
            <button className={taskMode === "new-product" ? "selected" : ""} onClick={() => { setTaskMode("new-product"); setProduct(null); setAsin(""); resetDiscovery(); setSourceMessage("无需 ASIN。完整填写产品事实并上传产品图后，可直接寻找相似竞品。"); }}>
              <span>新品</span><b>全新商品（暂无 ASIN）</b><p>根据类目、材质、风格、产品特征、尺寸与产品图搜索真实竞品，再完成关键词与标题研究。</p>
            </button>
          </div>
        </article>
        <article className="panel sourcePanel" id="product-source">
          <div className="panelHead"><div><h3>2. 获取本品真实资料</h3><p>{taskMode === "new-product" ? "暂无 ASIN：使用产品部资料建立事实画像，并由图片参与真实视觉比对" : taskMode === "new-variant" ? "读取父体和现有子体，提炼同系列可继承的标题骨架与真实卖点" : "优先读取父体全部子体；按月销量信号推荐主推款，并为每个尺寸生成标题"}</p></div><span className="requiredMark">{taskMode === "new-product" ? "产品事实必填" : "ASIN 必填"}</span></div>
          <div className="sourceGrid">
            {taskMode === "new-product" ? <div className="newProductSource"><b>全新商品资料入口</b><p>搜索与评分只使用你确认的真实资料。品牌和产品名称可选，但类目、材质、风格、产品特征与尺寸必填。</p><label>目标站点<select value={marketplace} onChange={e => {setMarketplace(e.target.value);resetDiscovery();}}><option value="US">美国站</option><option value="UK">英国站</option><option value="DE">德国站</option><option value="JP">日本站</option></select></label><small>{newProductReady ? "✓ 核心资料已完整，可以发现竞品" : "请继续填写下方标有“新品必填”的字段"}</small></div> :
            <form className="asinSource" onSubmit={readProduct}>{taskMode === "optimize" && <div className="optimizeScopeSwitch"><button type="button" className={optimizeScope === "family" ? "selected" : ""} onClick={() => {setOptimizeScope("family");resetDiscovery();}}><b>父体批量优化</b><small>一次处理全部尺寸</small></button><button type="button" className={optimizeScope === "single" ? "selected" : ""} onClick={() => {setOptimizeScope("single");resetDiscovery();}}><b>单子体优化</b><small>只修改一个商品</small></button></div>}<label>{taskMode === "new-variant" ? "父体 ASIN" : optimizeScope === "single" ? "需要修改的子体 ASIN" : "父体 ASIN"}</label><div className="asinActionRow"><input value={asin} maxLength={10} onChange={e => {setAsin(e.target.value.toUpperCase().replace(/\s/g, ""));setProduct(null);setMainChildAsin("");resetDiscovery();}} placeholder="例如 B0XXXXXXXX" /><select value={marketplace} onChange={e => {setMarketplace(e.target.value);resetDiscovery();}}><option value="US">美国站</option><option value="UK">英国站</option><option value="DE">德国站</option><option value="JP">日本站</option></select><button className="readProductButton" disabled={loading === "product"}>{loading === "product" ? "正在读取…" : taskMode === "new-variant" ? "读取父体资料 →" : optimizeScope === "single" ? "读取子体资料 →" : "读取父体资料 →"}</button></div>{product && <div className="targetMini">{product.images[0] && <img src={product.images[0]} alt="" />}<span><b>{product.title}</b><small>{product.asin} · {product.price || "价格未展示"} · 五点 {product.bullets.length} 条{taskMode !== "new-product" ? ` · 已读取 ${product.variants.length} 个子体；这些 ASIN 会全部排除` : ""}</small></span></div>}</form>}
            <label className="imageSource"><span>{taskMode === "new-product" ? "上传产品主图（强烈建议）" : "上传产品部资料图"}</span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={uploadImage} />{imagePreview ? <img src={imagePreview} alt="上传预览" /> : <div><b>＋ 选择产品图</b><small>{taskMode === "new-product" ? "在本机与竞品多图比较轮廓、纹理和颜色；最大 8 MB" : "用于补充产品外观资料"}</small></div>}</label>
          </div>
          <div className={`sourceStatus ${loading === "product" ? "working" : sourceReady ? "success" : "notice"}`}><i /> <span>{sourceMessage}</span></div>
          {taskMode === "optimize" && product && <div className="parentVariantWorkbench">
            <div className="parentVariantHead"><div><span>{optimizeScope === "family" ? "父体批量优化" : "单子体优化"}</span><b>{optimizeScope === "family" ? "确认主推子体与尺寸范围" : "确认本次要修改的子体"}</b><small>月销量只是公开页面信号；无信号或信号接近时，以你的人工选择为准。</small></div><div><b>{optimizeSizes.length}</b><span>{optimizeScope === "family" ? "个尺寸将生成标题" : "个子体将生成标题"}</span></div></div>
            <div className="variantChoiceGrid">{product.variants.map(variant => <label className={variant.asin === mainChildAsin ? "selected" : ""} key={variant.asin}>
              <input type="radio" name="main-child" checked={variant.asin === mainChildAsin} onChange={() => {
                setMainChildAsin(variant.asin);
                const inferred = inferProductFacts(variant.title || product.title, variant.bullets || product.bullets);
                setFacts(current => ({...current, category:inferred.category || current.category, material:inferred.material || current.material, style:inferred.style || current.style, useCase:inferred.useCase || current.useCase, mustHave:inferred.mustHave || current.mustHave}));
                resetDiscovery();
              }} />
              <span><b>{variant.size || "尺寸未识别"}</b><small>{variant.asin}{variant.color ? ` · ${variant.color}` : ""}</small></span>
              <em>{variant.monthly_sales_estimate ? `${variant.monthly_sales_estimate.toLocaleString()}+ / 月` : variant.recent_sales_signal || "月销量信号未知"}</em>
              {variant.is_suspected_main && <i>系统推荐</i>}
            </label>)}</div>
            <p>{optimizeScope === "family" ? "同一尺寸有多个颜色时，只选销量信号最好的子体作为该尺寸事实样本；最终覆盖父体下全部不同尺寸。" : "本轮只生成所选子体的标题，不会连带修改父体下其他尺寸。"}</p>
          </div>}
          {taskMode !== "optimize" && <div className="variantTitleInputs" id="variant-title-inputs">
            <div className="variantIntro"><b>{taskMode === "new-product" ? "新品颜色与尺寸" : "新增标题变量"}</b><span>一行一个；系统按颜色 × 尺寸生成标题。{taskMode === "new-product" ? "尺寸会决定类目词和市场使用场景。" : "新 ASIN 由商品在 Amazon 创建后产生，此处不需要填写。"}</span></div>
            <label>新增颜色（与尺寸二选一，或都填）<textarea id="new-colors" value={newColors} onChange={e => setNewColors(e.target.value)} placeholder={"Beige\nDark Green\nBrown"} /></label>
            <label>{taskMode === "new-product" ? "新品尺寸（必填）" : "新增尺寸（与颜色二选一，或都填）"}<textarea id="new-sizes" value={newSizes} onChange={e => setNewSizes(e.target.value)} placeholder={"2' x 3'\n5' x 7'\n8' x 10'"} /></label>
            <div className="combinationCount"><span>预计生成</span><b>{titleCount}</b><small>个标题候选</small></div>
          </div>}
          <div className="titleFormatRow"><div><b>标题制式</b><span>生成前仍可切换</span></div><button className={titleFormat === "classic" ? "selected" : ""} onClick={() => setTitleFormat("classic")}><b>原标题</b><small>完整标题 ≤ 200 字符</small></button><button className={titleFormat === "split" ? "selected" : ""} onClick={() => setTitleFormat("split")}><b>二段标题</b><small>主标题 ≤ 75 + Highlight Item ≤ 125</small></button></div>
          <div className="factsGrid"><label>品牌（新品可选）<input value={facts.brand} onChange={e => setFacts({...facts, brand:e.target.value})} placeholder="例如 GENIMO" /></label><label>产品名称（新品可选）<input value={facts.productName} onChange={e => setFacts({...facts, productName:e.target.value})} placeholder="例如 Textured Area Rug" /></label><label>类目大词{taskMode === "new-product" && <em>新品必填</em>}<input value={facts.category} onChange={e => setFacts({...facts, category:e.target.value})} placeholder="例如 Area Rug" /></label><label>材质{taskMode === "new-product" && <em>新品必填</em>}<input value={facts.material} onChange={e => setFacts({...facts, material:e.target.value})} placeholder="例如 Polyester" /></label><label>风格 / 外观{taskMode === "new-product" && <em>新品必填</em>}<input value={facts.style} onChange={e => setFacts({...facts, style:e.target.value})} placeholder="例如 Modern Abstract / Arch Pattern" /></label><label>主要用途（可由尺寸辅助判断）<input value={facts.useCase} onChange={e => setFacts({...facts, useCase:e.target.value})} placeholder="例如 Living Room" /></label><label className="wideFact">必须真实具备的产品特征{taskMode === "new-product" && <em>新品必填</em>}<input value={facts.mustHave} onChange={e => setFacts({...facts, mustHave:e.target.value})} placeholder="结构、工艺、功能用逗号分隔，例如 High Low Pile, Washable, Non Slip" /></label></div>
        </article>
        <article className="panel discoverPanel" id="competitor-discovery">
          <div className="panelHead"><div><h3>3. 先确认方案，再发现竞品</h3><p>系统先整理画像和分层搜索词；你确认后才访问 Amazon{backendVersion && <em className="backendVersion"> · 本机 v{backendVersion}</em>}</p></div><div className="discoverActions"><button onClick={prepareSearchPlan} disabled={loading === "plan"}>{loading === "plan" ? "正在整理…" : searchPlan ? "重新生成搜索方案" : "生成搜索方案"}</button></div></div>
          <div className="competitorRules"><b>产品相似度</b><span>产品类型 35%</span><span>真实属性 30%</span><span>标题特征证据 15%</span><span>图片外观 20%</span><b>市场价值另算</b><span>销量、评价与价格只用于排序，不增加产品相似度</span><small>先硬性排除非同产品类型和确认的排除项，再计算相似度；每个竞品品牌只保留 1 款。</small></div>
          {searchPlan && <div className="discoveryProfile"><div><b>待确认的本品画像</b><p>{searchPlan.features.length ? searchPlan.features.join(" · ") : "暂未识别到稳定特征，请核对直接竞品定义。"}</p></div><label><b>产品类型（硬门槛）</b><input value={searchPlan.productType} onChange={event => setSearchPlan({...searchPlan, productType:event.target.value})} /></label><label><b>直接竞品定义</b><textarea value={searchPlan.directDefinition} onChange={event => setSearchPlan({...searchPlan, directDefinition:event.target.value})} /></label><div className="weightedQueryEditor"><b>确认搜索词——人工可手动赋予权重</b><div className="queryWeightHead"><span>启用</span><span>搜索词</span><span>权重</span><span /></div>{weightedQueries.map((item, index) => <div className="queryWeightRow" key={index}><input type="checkbox" checked={item.enabled} onChange={event => setWeightedQueries(current => current.map((value, position) => position === index ? {...value, enabled:event.target.checked} : value))} /><input value={item.query} onChange={event => setWeightedQueries(current => current.map((value, position) => position === index ? {...value, query:event.target.value} : value))} /><label><input type="number" min="0" max="100" value={item.weight} onChange={event => setWeightedQueries(current => current.map((value, position) => position === index ? {...value, weight:Math.max(0, Math.min(100, Number(event.target.value) || 0))} : value))} /><span>%</span></label><button onClick={() => setWeightedQueries(current => current.filter((_, position) => position !== index))}>删除</button></div>)}<button className="addQueryRow" onClick={() => setWeightedQueries(current => [...current, {query:"", weight:5, enabled:true}])}>＋ 添加搜索词</button><small>权重决定各搜索组进入候选池的名额比例；无需合计为 100，系统会自动按比例换算。</small></div><label><b>必须排除的商品词（一行一个）</b><textarea value={searchPlan.excludedTerms} onChange={event => setSearchPlan({...searchPlan, excludedTerms:event.target.value})} placeholder={"dish drying rack\nfaucet mat"} /></label><small>{searchPlan.guidance.join(" ")}</small><div className="discoverActions"><label>Amazon 翻页<select value={searchPages} onChange={e => setSearchPages(Number(e.target.value))}><option value={1}>1 页</option><option value={2}>2 页</option><option value={3}>3 页</option></select></label><label><input type="checkbox" checked={verifyDetailPages} onChange={e => setVerifyDetailPages(e.target.checked)} />短名单详情页复核</label><label>最多保留<select value={resultLimit} onChange={e => setResultLimit(Number(e.target.value))}><option value={24}>24 个</option><option value={40}>40 个</option><option value={60}>60 个</option></select></label><button onClick={discover} disabled={loading === "discover"}>{loading === "discover" ? "正在搜索…" : "确认方案并搜索竞品"}</button></div></div>}
          {searchPlan && <label className="candidateLimitToggle">最终候选上限<select value={resultLimit} onChange={event => setResultLimit(Number(event.target.value))}><option value={24}>24 个</option><option value={40}>40 个</option><option value={60}>60 个</option><option value={100}>100 个</option></select><small>这是上限，不足时不会用低相关商品凑数。</small></label>}
          {discoveryMeta && <div className="discoveryProfile"><b>本轮候选漏斗</b><p>搜索页卡片 {discoveryMeta.cards} 条 → 去重后 {discoveryMeta.unique} 个 ASIN → 权重候选池 {discoveryMeta.pool} 个 → 最终 {candidates.length} 个品牌代表商品</p><small>排除：本品家族结果 {discoveryMeta.ownResults} 条、本品牌 {discoveryMeta.sameBrand} 条、排除词 {discoveryMeta.termFiltered} 条、产品类型不符 {discoveryMeta.typeFiltered} 个；同品牌合并 {discoveryMeta.collapsed} 个。设置100代表最多保留100个，不会绕过这些规则补足数量。</small></div>}
          <div className="manualCompetitors"><textarea value={manualAsins} onChange={e => setManualAsins(e.target.value)} placeholder={"也可以一行一个批量添加竞品 ASIN\nB0XXXXXXXX\nB0YYYYYYYY"} /><button onClick={addManual} disabled={loading === "manual"}>{loading === "manual" ? "读取中…" : "添加人工竞品"}</button></div>
          {message && <div className="marketMessage">{message}</div>}
          {candidates.length ? <><div className="candidateToolbar"><span>共 {candidates.length} 个候选 · 市场价值优先排序 · 第 {candidatePage}/{candidatePages} 页</span><div><button onClick={() => exportCompetitors("selected")} disabled={loading === "export"}>导出已选 XLSX</button><button onClick={() => exportCompetitors("all")} disabled={loading === "export"}>导出全部 XLSX</button></div></div><div className="candidateGrid">{visibleCandidates.map(item => <article className={item.selected ? "candidate selected" : "candidate"} key={item.asin}>{item.image ? <img src={item.image} alt="" /> : <div className="noCandidateImage">无图</div>}<div><div className="candidateMeta"><a href={item.url} target="_blank">{item.asin} ↗</a><span>{item.source === "manual" ? "人工添加" : `产品相似度 ${item.overall_similarity ?? "—"}分`}</span></div><div className="candidateIdentity"><b>{item.brand || "品牌未识别"}</b><span>{item.size || "尺寸未识别"}</span>{item.parent_asin && <span>父体 {item.parent_asin}</span>}</div><h4>{item.title}</h4><p>{item.price || "价格未知"} · ★ {item.rating ?? "—"} · {item.recent_sales_signal || "月销量未知"}{item.monthly_sales_estimate ? `（按 ${item.monthly_sales_estimate.toLocaleString()} 排序）` : ""}</p>{item.source !== "manual" && <><div className="scoreBreakdown"><span>产品类型 {item.product_type_similarity ?? "—"}</span><span>属性 {item.attribute_similarity ?? "—"}</span><span>标题证据 {item.text_similarity ?? "—"}</span><span title={item.visual_reason || ""}>视觉 {item.image_similarity ?? "—"} · {item.visual_images_compared || 0} 组</span><span>市场价值 {item.market_value ?? item.market_similarity ?? "—"}</span></div><p className="visualReason">{item.visual_reason}</p><p className="matchReasons">{item.match_reasons?.join(" · ") || "等待人工核验"}</p></>}<label><input type="checkbox" checked={!!item.selected} onChange={() => setCandidates(current => current.map(value => value.asin === item.asin ? {...value, selected:!value.selected} : value))} />纳入竞品研究</label></div></article>)}</div><div className="candidatePagination"><button disabled={candidatePage <= 1} onClick={() => setCandidatePage(page => page - 1)}>← 上一页</button><span>{candidatePage} / {candidatePages}</span><button disabled={candidatePage >= candidatePages} onClick={() => setCandidatePage(page => page + 1)}>下一页 →</button></div></> : <div className="candidateEmpty"><b>{searchPlan ? "等待确认搜索方案" : "还没有竞品搜索方案"}</b><span>{searchPlan ? "核对上方产品类型、直接竞品定义、搜索词和排除项，再点击“确认方案并搜索竞品”。" : "先准备本品资料，再点击“生成搜索方案”；系统不会立即访问 Amazon。"}</span></div>}
          {candidates.length > 0 && <div className="confirmCompetitors"><div><span>已选择 <b>{selected.length}</b> 个竞品</span>{confirmMessage && <small className={confirmed ? "confirmSuccess" : "confirmError"}>{confirmMessage}</small>}</div><button className={confirmed ? "locked" : ""} onClick={lockCompetitors}>{confirmed ? `✓ 已锁定 ${selected.length} 个竞品` : "确认竞品并锁定本轮研究"}</button></div>}
          {confirmed && <div className="reviewPainStudy"><div className="painStudyHead"><div><span className="sectionEyebrow">REVIEW INSIGHTS · 可选</span><h3>竞品差评中，买家最在意什么？</h3><p>先看聚合后的痛点主题；只处理我方确实已经改进的部分。</p></div><div className="painStudyActions"><select aria-label="评论分析竞品范围" value={reviewCompetitorLimit} onChange={event => setReviewCompetitorLimit(Number(event.target.value))}><option value={5}>前5个头部竞品</option><option value={10}>前10个头部竞品</option><option value={20}>前20个头部竞品</option></select><button onClick={analyzeCompetitorReviews} disabled={loading === "reviews"}>{loading === "reviews" ? "正在归纳评论…" : painInsights.length ? "重新分析评论" : "提取低星评论痛点"}</button></div></div>
            {!!painInsights.length && <><div className="painSummary"><div><span>痛点主题</span><b>{painInsights.length}</b></div><div><span>评论证据</span><b>{painInsights.reduce((sum, item) => sum + item.evidence.length, 0)}</b></div><div><span>已确认改进</span><b>{painInsights.filter(item => item.confirmed).length}</b></div><p>系统已合并重复短语；评论原句默认折叠，不再用零散词组刷屏。</p></div>
              <div className="painInsightList">{painInsights.map((item, index) => <article className={`${item.selected ? "active" : ""} ${item.confirmed ? "confirmed" : ""}`} key={item.phrase}><div className="painCardTop"><div><span className="painRank">#{index + 1}</span><div><b>{item.phrase}</b><small>{item.sourcePhrases?.join(" · ") || "评论痛点主题"}</small></div></div><em>{item.mentions} 条证据</em></div><details><summary>查看评论原句</summary>{item.evidence.map(value => <blockquote key={value}>{value}</blockquote>)}</details><button className="painSelectButton" onClick={() => setPainInsights(current => current.map((value, currentIndex) => currentIndex === index ? {...value, selected:!value.selected, confirmed:value.selected ? false : value.confirmed} : value))}>{item.selected ? "收起改进验证" : "我方已针对该问题改进 →"}</button>{item.selected && <div className="painImprovement"><label>我方已实现的改进<input value={item.improvement} onChange={event => setPainInsights(current => current.map((value, currentIndex) => currentIndex === index ? {...value, improvement:event.target.value, confirmed:false} : value))} placeholder={item.example || "填写我方已实现的具体改进"} /></label><label className="painConfirm"><input type="checkbox" checked={item.confirmed} disabled={!item.improvement.trim()} onChange={event => setPainInsights(current => current.map((value, currentIndex) => currentIndex === index ? {...value, confirmed:event.target.checked} : value))} /><span><b>事实确认</b>我已核对产品资料，本品确实具备该改进</span></label></div>}</article>)}</div>
            </>}
          </div>}
        </article>
        <article className="panel uploadPanel" id="keyword-materials">
          <div className="panelHead"><div><h3>4. 补充关键词与公司资料</h3><p>ABA 综合词库必填；卖家精灵扩展数据和广告报告均为选填</p></div><span className="selectedCount">{Object.keys(files).length} 个文件</span></div>
          <div className="uploadGrid">{uploadGuides.map(guide => <label className={`uploadCard ${guide.key === "aba" ? "requiredUpload" : ""}`} key={guide.key}><input type="file" accept={guide.accept} onChange={e => handleReferenceFile(guide.key, e.target.files?.[0])} /><b>{files[guide.key] ? "✓ " : "＋ "}{guide.name}{guide.key === "aba" && <em>必填</em>}</b><p>{guide.desc}</p><span>{files[guide.key] || "点击选择文件"}</span></label>)}</div>
          {loading === "aba" && <div className="fileInspection working">正在读取 ABA 表头、关键词列和搜索量列…</div>}
          {abaSummary && <div className={abaSummary.valid ? "fileInspection success" : "fileInspection error"}><b>{abaSummary.valid ? `✓ 已识别 ${abaSummary.rows} 个关键词` : "ABA 词库未通过校验"}</b><span>{abaSummary.keyword_column ? `关键词列：${abaSummary.keyword_column}` : "未找到关键词列"}{abaSummary.volume_columns.length ? ` · 搜索量列：${abaSummary.volume_columns.join("、")}` : " · 未找到搜索量列"}{abaSummary.sheet ? ` · 工作表：${abaSummary.sheet}` : ""}</span>{abaSummary.warnings.map(warning => <small key={warning}>{warning}</small>)}</div>}
          {negativeSummary && <div className={negativeSummary.valid ? "fileInspection success" : "fileInspection error"}><b>{negativeSummary.valid ? `✓ 已载入 ${negativeSummary.rows} 个否词` : "否词词库未通过校验"}</b><span>命中后将从标题和广告词包中硬拦截。</span></div>}
        </article>
        <div className={`nextPhase ${nextBlockers.length ? "hasBlockers" : ""}`}><div><b>下一步：竞品标题结构、关键词池与标题候选</b><span>{nextBlockers.length ? `还需完成：${nextBlockers.join("；")}` : taskMode !== "optimize" ? `资料完整，可为 ${titleCount} 个颜色/尺寸组合进入研究。` : optimizeScope === "family" ? `资料完整，可为父体下 ${titleCount} 个尺寸进入研究。` : "资料完整，可进入当前子体标题研究。"}</span>{nextNotice && <small>{nextNotice}</small>}</div><button onClick={enterResearch}>{researchStarted ? "✓ 已进入标题研究" : nextBlockers.length ? "查看待完成项 →" : "进入真实标题研究 →"}</button></div>
        {researchStarted && <article className="panel researchPanel" id="title-research">
          <div className="panelHead"><div><h3>5. 真实标题研究</h3><p>本轮研究输入已锁定；点击生成后才会产生标题，结果仍需人工编辑和确认。</p></div><span className="selectedCount">{generatedTitles.length ? `已生成 ${generatedTitles.length} 个` : "等待生成"}</span></div>
          <div className="researchInputs"><div><span>本品</span><b>{product?.asin || "全新商品 · 暂无 ASIN"}</b><small>{product?.title || [facts.brand, facts.productName || facts.category].filter(Boolean).join(" ")}</small></div><div><span>竞品</span><b>{selected.length} 个已锁定</b><small>生成时优先匹配同尺寸竞品</small></div><div><span>ABA 词库</span><b>{abaSummary?.rows || 0} 个关键词</b><small>{abaSummary?.volume_columns.length ? `已识别 ${abaSummary.volume_columns.length} 个搜索量字段` : "未识别搜索量字段"}</small></div><div><span>标题任务</span><b>{taskMode === "new-product" ? `${titleCount} 个全新商品组合` : taskMode === "new-variant" ? `${titleCount} 个新增变体组合` : optimizeScope === "family" ? `${titleCount} 个现有尺寸` : "优化当前子体"}</b><small>{titleFormat === "split" ? "二段标题制式" : "原标题制式"}</small></div></div>
          <div className="generateAction"><div><b>{keywordSelections.length ? "关键词方案待确认" : "先制定关键词布置方案"}</b><span>高流量场景词在事实和尺寸匹配时可以进入主标题；普通表达少用连接词，已确认流量短语中的 for 保留。</span></div><button onClick={analyzeKeywordPlan} disabled={loading === "keyword-plan"}>{loading === "keyword-plan" ? "分析中…" : keywordSelections.length ? "重新分析关键词" : "分析并布置关键词"}</button></div>
          {keywordPlanMessage && <div className="keywordPlanMessage">{keywordPlanMessage}</div>}
          {!!keywordAnalysis.length && <section className="titleResearchReport">
            <div className="researchReportHead"><div><b>生成前分析结果</b><span>先判断消费者、市场结构、尺寸场景与候选词，再生成标题</span></div><em>数据来自本轮真实资料</em></div>
            {competitorTitleAnalysis && <div className="competitorWritingStudy">
              <div><span>分析样本</span><b>{competitorTitleAnalysis.sample_size} 个已锁定标题</b><small>头部10个样本优先参与结构判断</small></div>
              <div><span>标题长度</span><b>中位数 {competitorTitleAnalysis.median_length || "—"} 字符</b><small>中间区间：{competitorTitleAnalysis.length_range || "样本不足"}</small></div>
              <div className="wideStudy formulaStudy"><span>头部竞品主导公式</span><b>{competitorTitleAnalysis.dominant_formula || competitorTitleAnalysis.recommended_structure}</b><em>{competitorTitleAnalysis.formula_coverage_percent || 0}% 样本采用相同槽位顺序</em><small>{competitorTitleAnalysis.consumer_note}</small></div>
              {!!competitorTitleAnalysis.common_slot_orders?.length && <div className="wideStudy"><span>常见结构排序</span><div className="structureChips">{competitorTitleAnalysis.common_slot_orders.map(value => <i key={value}>{value}</i>)}</div></div>}
              {!!competitorTitleAnalysis.position_insights?.length && <div><span>各信息槽位出现位置</span><ul>{competitorTitleAnalysis.position_insights.map(value => <li key={value}>{value}</li>)}</ul></div>}
              <div><span>逗号与信息分组</span><ul>{(competitorTitleAnalysis.punctuation_insights || []).map(value => <li key={value}>{value}</li>)}</ul></div>
              <div className="wideStudy"><span>禁止照搬的错误</span><div className="structureChips">{(competitorTitleAnalysis.anti_patterns || []).map(value => <i key={value}>{value}</i>)}</div></div>
            </div>}
            {!!competitorTerms.length && <div className="competitorTermStudy"><div className="dualPoolHead"><div><span>词池 A · MARKET LANGUAGE</span><h4>头部竞品高频表达</h4><p>按不同竞品标题的出现覆盖率统计；前10个头部竞品获得更高权重。</p></div><em>{competitorTerms.length} 个市场表达</em></div><div className="competitorTermGrid">{competitorTerms.slice(0, 12).map(item => <article key={item.term}><div><b>{item.term}</b><span>{item.coverage_percent}% 竞品覆盖</span></div><small>{item.matched_facts.length ? `匹配本品：${item.matched_facts.join("、")}` : "仅作市场结构参考"} · {item.recommended_placement === "main" ? "建议主标题" : item.recommended_placement === "highlight" ? "建议 Highlight" : "结构参考"}</small></article>)}</div></div>}
            {!!semanticClusters.length && <div className="semanticClusterStudy"><div><b>本轮语义卖点簇</b><span>只有明确同义或上下位包含关系才合并；其余已确认属性保持独立。</span></div><div>{semanticClusters.map(value => <i key={value}>{value}</i>)}</div></div>}
            {!!sizeCompetitorStudies.length && <div className="sizeWritingStudy"><div className="dualPoolHead"><div><span>SIZE-SPECIFIC WRITING</span><h4>先按尺寸整理词，再分别写标题</h4><p>每个尺寸独立统计竞品词频、ABA相关词与标题公式；同尺寸样本不足时明确提示回退。</p></div><em>{sizeCompetitorStudies.length} 个尺寸</em></div><div className="sizeStudyGrid">{sizeCompetitorStudies.map(study => <article key={study.size}><div className="sizeStudyTop"><b>{study.size}</b><span>{study.sample_size} 个竞品样本</span></div><p className="sizeFormula">{study.dominant_formula || "样本不足，使用默认结构"} <em>{study.formula_coverage_percent}%</em></p><div className="sizeTermLine"><span>竞品高频</span><p>{study.frequent_terms.map(item => item.term).slice(0, 5).join(" · ") || "未识别"}</p></div><div className="sizeTermLine"><span>ABA候选</span><p>{study.aba_terms.map(item => item.term).slice(0, 5).join(" · ") || "暂无通过尺寸校验的词"}</p></div><small>{study.note}</small></article>)}</div></div>}
            {!!sizeScenarios.length && <div className="scenarioStudy"><h4>不同尺寸的市场场景判断</h4>{sizeScenarios.map(item => <article key={item.size || item.product_type}><div><b>{item.size || "当前尺寸"}</b><span>{item.product_type}</span></div><p>主场景：{item.primary_scenes.join(" / ")}</p><p>辅助场景：{item.secondary_scenes.join(" / ")}</p><small>{item.reasoning}</small></article>)}</div>}
            <div className="keywordStudy"><div className="keywordStudyHead"><div><span className="poolLabel">词池 B · SEARCH DEMAND</span><h4>ABA 搜索词与流量排名</h4><p>排名＝上传ABA词库最新月份的搜索量排名，不是 Amazon 自然位；只保留与本品、尺寸和场景一致的词。</p></div><span>{keywordAnalysis[0]?.month ? `最新字段：${keywordAnalysis[0].month}` : "词库未提供月份字段"}</span></div>
              <div className="keywordTable"><div className="keywordRow keywordHeader"><span>词库排名</span><span>候选关键词</span><span>最新搜索量</span><span>综合分</span><span>人工指定位置</span><span>判断</span></div>{keywordAnalysis.map(item => {
                const selection = keywordSelections.find(value => value.term === item.term);
                return <div className="keywordRow" key={item.term}><span>{item.rank ? `#${item.rank}` : "—"}</span><b>{item.term}</b><span>{item.volume?.toLocaleString() || "—"}</span><span>{item.total_score}分</span><select value={selection?.placement || item.recommended_placement} onChange={event => setKeywordSelections(current => current.map(value => value.term === item.term ? {...value, placement:event.target.value as KeywordPlacement, enabled:event.target.value !== "exclude"} : value))}><option value="main">主标题</option><option value="highlight">Item Highlight</option><option value="ads">广告词包</option><option value="exclude">不采用</option></select><small>{item.reason}</small></div>;
              })}</div>
            </div>
          </section>}
          {!!keywordSelections.length && <div className="generateAction"><div><b>人工确认后生成最多三种策略</b><span>流量优先、点击吸引、均衡转化；若两种策略形成相同标题会自动合并，不重复展示。</span></div><button onClick={generateTitleCandidates} disabled={loading === "titles"}>{loading === "titles" ? "正在生成…" : generatedTitles.length ? "按当前方案重新生成" : "确认关键词并生成标题"}</button></div>}
          {!!trafficKeywords.length && <div className="trafficKeywordBar"><b>通过校验的候选词</b>{trafficKeywords.slice(0, 10).map(item => <span key={item.term}>{item.rank ? `#${item.rank} · ` : ""}{item.term}{item.volume ? ` · ${item.volume.toLocaleString()}` : ""}</span>)}</div>}
          {!!generatedTitles.length && <><div className="titleExportBar"><div><b>{optimizeScope === "family" && taskMode === "optimize" ? "多尺寸标题已整理" : "标题候选已整理"}</b><span>{optimizeScope === "family" && taskMode === "optimize" ? "Excel 第一行以尺寸作为列标题，并附带可筛选的明细表。" : "可导出当前全部策略与人工编辑后的内容。"}</span></div><button onClick={exportGeneratedTitles} disabled={loading === "title-export"}>{loading === "title-export" ? "正在导出…" : "导出标题 Excel"}</button></div><div className="generatedTitles" id="generated-titles">{generatedTitles.map((item, index) => {
            const mainLimit = titleFormat === "split" ? 75 : 200;
            return <article className="generatedTitleCard" key={item.id}>
              <div className="generatedTitleHead"><div><span>{item.strategy === "traffic" ? "流量优先" : item.strategy === "click" ? "点击吸引" : "均衡转化"} · {item.score}分</span><b>{[item.color, item.size].filter(Boolean).join(" · ") || "当前商品"}</b></div><button onClick={() => navigator.clipboard?.writeText(item.full_title)}>复制完整标题</button></div>
              <label>{titleFormat === "split" ? "主标题" : "完整标题"}<span className={item.main_count <= mainLimit ? "countOk" : "countError"}>{item.main_count} / {mainLimit}</span><textarea value={item.main_title} onChange={event => editGeneratedTitle(item.id, "main_title", event.target.value)} /></label>
              {titleFormat === "split" && <label>Highlight Item<span className={item.highlight_count <= 125 ? "countOk" : "countError"}>{item.highlight_count} / 125</span><textarea value={item.highlight_item || ""} onChange={event => editGeneratedTitle(item.id, "highlight_item", event.target.value)} /></label>}
              <div className="titleEvidence"><span>覆盖词：{item.keywords_used.length ? item.keywords_used.join(" · ") : "未精确覆盖高相关 ABA 词"}</span>{item.keyword_evidence.map(value => <small key={value}>{value}</small>)}{!!item.unused_keywords.length && <small>未放入：{item.unused_keywords.join(" · ")}（字符或结构限制）</small>}{!!item.ad_keywords.length && <small>广告词包：{item.ad_keywords.join(" · ")}</small>}{item.warnings.map(warning => <small key={warning}>⚠ {warning}</small>)}</div>
            </article>;
          })}</div></>}
        </article>}
      </section>
    </div>
    <footer><span>采数 · 标题半自动化工作台</span><span>不生成虚假流量，不自动确认竞品</span></footer>
  </main>;
}
