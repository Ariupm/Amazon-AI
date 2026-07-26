"use client";

import { useEffect, useMemo, useState } from "react";
export { default } from "./market-workspace";

type Format = "classic" | "split";
type Keyword = { word: string; tier: "T1" | "T2" | "T3" | "T4"; volume: string; source: string; selected: boolean };

const initialKeywords: Keyword[] = [
  { word: "tote bag for women", tier: "T1", volume: "61.2K", source: "ABA / 竞品", selected: true },
  { word: "work bag for women", tier: "T1", volume: "38.4K", source: "ABA / 广告", selected: true },
  { word: "large tote bag", tier: "T2", volume: "25.7K", source: "竞品高频", selected: true },
  { word: "laptop tote bag", tier: "T2", volume: "19.8K", source: "广告转化", selected: true },
  { word: "travel shoulder bag", tier: "T3", volume: "8.6K", source: "竞品覆盖", selected: true },
  { word: "zipper closure", tier: "T4", volume: "3.1K", source: "评论卖点", selected: false },
  { word: "lightweight purse", tier: "T3", volume: "7.4K", source: "ABA", selected: false },
];

const competitors = [
  { brand: "BAGSMART", type: "头部品牌", title: "BAGSMART Tote Bag for Women, Large Lightweight Work Bag with Zipper, Laptop Shoulder Bag for Travel", score: 91 },
  { brand: "LOVEVOOK", type: "高流量竞品", title: "LOVEVOOK Laptop Tote Bag for Women, Large Work Bag Purse, Waterproof Teacher Handbag with Zipper", score: 87 },
  { brand: "TOPDesign", type: "类目畅销", title: "TOPDesign Utility Tote Bag for Women, Large Organizer Bag with 13 Pockets for Work and Travel", score: 84 },
];

const sizes = ["Classic", "Large"];
const colors = ["Black", "Beige", "Forest Green", "Navy Blue"];

function LegacyTitleStudio() {
  const [format, setFormat] = useState<Format>("split");
  const [activeStep, setActiveStep] = useState(1);
  const [keywords, setKeywords] = useState(initialKeywords);
  const [brand, setBrand] = useState("EVERYDAY");
  const [category, setCategory] = useState("Tote Bag for Women");
  const [feature, setFeature] = useState("Lightweight Work Bag");
  const [scene, setScene] = useState("Laptop Shoulder Bag for Work and Travel");
  const [size, setSize] = useState("Large");
  const [color, setColor] = useState("Black");
  const [generated, setGenerated] = useState(false);
  const [copied, setCopied] = useState("");

  const chosen = keywords.filter((item) => item.selected);
  const mainTitle = `${brand} ${category}, ${size} ${feature}`;
  const highlight = `${scene}, Zipper Closure, ${color}`;
  const classicTitle = `${brand} ${category}, ${size} ${feature}, ${scene}, Zipper Closure, ${color}`;
  const coverage = useMemo(() => chosen.filter((item) => `${mainTitle} ${highlight}`.toLowerCase().includes(item.word.toLowerCase())).length, [chosen, mainTitle, highlight]);
  const currentMax = format === "classic" ? 200 : 75;

  function toggleKeyword(word: string) {
    setKeywords((items) => items.map((item) => item.word === word ? { ...item, selected: !item.selected } : item));
  }

  function generate() {
    setGenerated(true);
    setActiveStep(4);
    window.setTimeout(() => document.getElementById("output")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  }

  async function copy(text: string, key: string) {
    await navigator.clipboard?.writeText(text);
    setCopied(key);
    window.setTimeout(() => setCopied(""), 1200);
  }

  return (
    <main className="titleApp">
      <header className="topbar">
        <a className="brand" href="/" aria-label="采数首页"><span className="brandMark">采</span><span>采数</span></a>
        <nav aria-label="主导航"><a href="/">数据采集</a><a className="active" href="/titles">标题工作台</a></nav>
        <div className="topActions"><span className="workspaceStatus"><i /> 规则已同步</span><button className="iconButton" aria-label="帮助">?</button><div className="avatar">L</div></div>
      </header>

      <section className="titleHero">
        <div>
          <span className="eyebrow"><i /> TITLE COPILOT</span>
          <h1>标题半自动化工作台</h1>
          <p>先理解市场，再决定选词与排序。AI 提供候选和检查，人负责商品真实性、品牌表达与最终判断。</p>
        </div>
        <div className="workflowBadge"><span>当前商品</span><b>B0D9W0XH2M</b><small>Everyday 多功能托特包 · 美国站</small></div>
      </section>

      <div className="studioShell">
        <aside className="studioSteps">
          <p>编写流程</p>
          {[
            ["01", "市场准备", "竞品与头部品牌"],
            ["02", "关键词分层", "流量、相关性、真实性"],
            ["03", "标题结构", "尺寸、颜色与排版"],
            ["04", "生成与编辑", "候选标题人工确认"],
            ["05", "合规检查", "字符、禁词与重复"],
          ].map(([no, title, desc], index) => <button key={no} className={activeStep === index + 1 ? "active" : activeStep > index + 1 ? "done" : ""} onClick={() => setActiveStep(index + 1)}>
            <span>{activeStep > index + 1 ? "✓" : no}</span><div><b>{title}</b><small>{desc}</small></div>
          </button>)}
          <div className="guardrail"><b>人机分工</b><p>系统统计、推荐与检查；人工确认事实、词序和最终版本。</p></div>
        </aside>

        <section className="studioContent">
          <div className="studioHeader">
            <div><span className="stepPill">STEP {String(activeStep).padStart(2, "0")}</span><h2>{activeStep === 1 ? "写标题前，先看懂市场" : activeStep === 2 ? "确定关键词优先级" : activeStep === 3 ? "搭建标题结构" : activeStep === 4 ? "生成、编辑并确认标题" : "发布前合规检查"}</h2><p>竞品告诉我们类目表达，头部品牌告诉我们成熟结构，流量词决定优先覆盖。</p></div>
            <button className="secondary">导入商品资料</button>
          </div>

          <div className="researchGrid">
            <article className="panel competitorPanel">
              <div className="panelHead"><div><h3>竞品与头部品牌标题</h3><p>已分析 24 个竞品 · 展示代表性样本</p></div><button>＋ 添加 ASIN</button></div>
              {competitors.map((item) => <div className="competitor" key={item.brand}>
                <div className="brandDot">{item.brand[0]}</div>
                <div><div className="competitorMeta"><b>{item.brand}</b><span>{item.type}</span><em>结构分 {item.score}</em></div><p>{item.title}</p><div className="wordPattern"><span>品牌</span><span>类目大词</span><span>尺寸/功能</span><span>场景</span></div></div>
              </div>)}
              <div className="patternSummary"><b>共同结构</b><p><strong>品牌 → 类目大词</strong> → 尺寸/核心功能 → 使用场景 → 颜色</p><span>类目大词平均出现在前 28 个字符内</span></div>
            </article>

            <article className="panel keywordPanel">
              <div className="panelHead"><div><h3>关键词池</h3><p>点击选择，分层可由人工调整</p></div><span className="selectedCount">已选 {chosen.length}</span></div>
              <div className="keywordLegend"><span><i className="t1" />T1 必须放</span><span><i className="t2" />T2 尽量放</span><span><i className="t3" />T3 有空间</span></div>
              <div className="keywordList">
                {keywords.map((item) => <button className={item.selected ? "selected" : ""} onClick={() => toggleKeyword(item.word)} key={item.word}>
                  <span className={`tier ${item.tier.toLowerCase()}`}>{item.tier}</span><div><b>{item.word}</b><small>{item.source}</small></div><em>{item.volume}</em><i>{item.selected ? "✓" : "+"}</i>
                </button>)}
              </div>
              <button className="textAction">查看完整关键词池 →</button>
            </article>
          </div>

          <article className="panel structurePanel">
            <div className="panelHead"><div><h3>标题格式与结构</h3><p>先选发布格式，再确认每段承担的任务</p></div><div className="formatSwitch"><button className={format === "classic" ? "active" : ""} onClick={() => setFormat("classic")}>原标题 · 200</button><button className={format === "split" ? "active" : ""} onClick={() => setFormat("split")}>二段标题 · 75 + 125</button></div></div>
            <div className="structureExplain">
              <div className="orderMap">
                <span className="brandBlock">品牌名<small>识别</small></span><b>→</b>
                <span className="categoryBlock">类目大词<small>第一流量入口</small></span><b>→</b>
                <span>尺寸 / 核心功能<small>点击与相关性</small></span><b>→</b>
                <span>场景 / 风格<small>长尾覆盖</small></span><b>→</b>
                <span className="tailBlock">颜色<small>变体尾部</small></span>
              </div>
              <div className="ruleNote"><b>前 50 字符原则</b><p>优先覆盖品牌、类目大词和最重要差异点。尺寸影响购买决策时前置；颜色通常放尾部，除非颜色本身是主要搜索意图。</p></div>
            </div>
            <div className="editorGrid">
              <label><span>品牌名</span><input value={brand} onChange={(e) => setBrand(e.target.value)} /></label>
              <label><span>类目大词 <em>T1</em></span><input value={category} onChange={(e) => setCategory(e.target.value)} /></label>
              <label><span>尺寸</span><select value={size} onChange={(e) => setSize(e.target.value)}>{sizes.map((value) => <option key={value}>{value}</option>)}</select></label>
              <label><span>颜色</span><select value={color} onChange={(e) => setColor(e.target.value)}>{colors.map((value) => <option key={value}>{value}</option>)}</select></label>
              <label className="wide"><span>核心功能 / 风格特点</span><input value={feature} onChange={(e) => setFeature(e.target.value)} /></label>
              <label className="wide"><span>使用场景 / 长尾词</span><input value={scene} onChange={(e) => setScene(e.target.value)} /></label>
            </div>
            <div className="variantHint"><span>变体选词规则</span><p><b>尺寸：</b>影响容量或使用场景时放在类目词后；仅作为规格区分时放后段。 <b>颜色：</b>默认最后，子体标题按实际颜色替换，不向父体聚合。</p></div>
            <button className="generateButton" onClick={generate}>✦ 生成标题候选 <span>人工确认后才可定稿 →</span></button>
          </article>

          <section className={`outputSection ${generated ? "visible" : ""}`} id="output">
            <div className="outputHead"><div><span className="success">AI 候选 · 待人工确认</span><h2>{format === "classic" ? "原标题候选" : "二段标题候选"}</h2></div><div className="qualityScore"><span>综合质量</span><b>92</b><small>/100</small></div></div>
            {format === "classic" ? (
              <TitleBox label="完整标题" value={classicTitle} max={200} onCopy={() => copy(classicTitle, "classic")} copied={copied === "classic"} />
            ) : (
              <>
                <TitleBox label="主标题 · 类目入口与核心卖点" value={mainTitle} max={75} onCopy={() => copy(mainTitle, "main")} copied={copied === "main"} />
                <div className="sentenceGuide"><span>分句边界</span><i /><p>主标题到此结束；Highlight 不重复类目大词，承接场景、次级功能与变体信息。</p></div>
                <TitleBox label="Highlight item · 场景与补充卖点" value={highlight} max={125} onCopy={() => copy(highlight, "highlight")} copied={copied === "highlight"} />
              </>
            )}
            <div className="checks">
              <div className="pass"><span>✓</span><div><b>字符数合规</b><small>{format === "classic" ? `${classicTitle.length}/200` : `主标题 ${mainTitle.length}/75 · Highlight ${highlight.length}/125`}</small></div></div>
              <div className="pass"><span>✓</span><div><b>关键词覆盖</b><small>已覆盖 {coverage}/{chosen.length} 个选中词，T1 词位于前部</small></div></div>
              <div className="pass"><span>✓</span><div><b>禁用词检查</b><small>未发现 Best Seller、Free Shipping、价格或促销表达</small></div></div>
              <div className="warnCheck"><span>!</span><div><b>真实性待确认</b><small>请人工确认 Large、Laptop 与 Zipper Closure 均与商品一致</small></div></div>
            </div>
            <div className="finalActions"><button className="secondary">保存为候选</button><button className="confirmButton" onClick={() => setActiveStep(5)}>确认此版本并进入合规检查 →</button></div>
          </section>
        </section>
      </div>
      <footer><span>采数 · 标题半自动化工作台</span><span>AI 负责候选与检查，最终发布须由人工确认</span></footer>
    </main>
  );
}

function TitleBox({ label, value, max, onCopy, copied }: { label: string; value: string; max: number; onCopy: () => void; copied: boolean }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  return <div className="titleBox"><div className="titleBoxHead"><label>{label}</label><span className={text.length > max ? "over" : ""}>{text.length} / {max} 字符</span></div><textarea value={text} onChange={(e) => setText(e.target.value)} /><div className="titleBoxFooter"><span>可直接编辑 · 空格计入字符</span><button onClick={onCopy}>{copied ? "✓ 已复制" : "复制标题"}</button></div></div>;
}
