"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Stage = "idle" | "running" | "done";

const variants = [
  { asin: "B0D9W21KQ6", attr: "黑色 · 经典款", price: "US$29.99", stock: "有货", image: "黑", tone: "dark" },
  { asin: "B0D9W4L5J8", attr: "米白 · 经典款", price: "US$31.99", stock: "有货", image: "米", tone: "cream" },
  { asin: "B0D9W5N2P3", attr: "森林绿 · 加大款", price: "US$34.99", stock: "有货", image: "绿", tone: "green" },
  { asin: "B0D9W7R8T1", attr: "海军蓝 · 加大款", price: "US$34.99", stock: "库存紧张", image: "蓝", tone: "blue" },
];

const steps = [
  ["识别商品关系", "已定位父体与 4 个可售子体"],
  ["采集商品信息", "标题、价格、图片与五点描述"],
  ["分析评论洞察", "聚合近期高相关评论"],
];

export default function Home() {
  const [asin, setAsin] = useState("B0D9W0XH2M");
  const [market, setMarket] = useState("美国站");
  const [stage, setStage] = useState<Stage>("idle");
  const [step, setStep] = useState(0);
  const [notice, setNotice] = useState("");

  const isValid = useMemo(() => /^[A-Z0-9]{10}$/i.test(asin.trim()), [asin]);

  useEffect(() => {
    if (stage !== "running") return;
    const timer = window.setInterval(() => {
      setStep((current) => {
        if (current >= 2) {
          window.clearInterval(timer);
          window.setTimeout(() => setStage("done"), 380);
          return current;
        }
        return current + 1;
      });
    }, 620);
    return () => window.clearInterval(timer);
  }, [stage]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!isValid) {
      setNotice("请输入 10 位有效 ASIN");
      return;
    }
    setNotice("");
    setStep(0);
    setStage("running");
  }

  function exportData() {
    const data = { parentAsin: asin.toUpperCase(), market, variants, insights: { strengths: ["面料柔软舒适", "收纳空间实用", "做工超出预期"], pains: ["肩带容易滑落", "浅色款不耐脏", "拉链顺滑度一般"] } };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${asin.toUpperCase()}-商品数据.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const hasResult = stage === "done";

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#" aria-label="采数首页">
          <span className="brandMark">采</span>
          <span>采数</span>
        </a>
        <nav aria-label="主导航">
          <a className="active" href="#workspace">数据采集</a>
          <a href="#history">采集记录</a>
        </nav>
        <div className="topActions">
          <button className="iconButton" aria-label="帮助">?</button>
          <div className="avatar">L</div>
        </div>
      </header>

      <section className="hero" id="workspace">
        <div className="heroCopy">
          <span className="eyebrow"><i /> AMAZON 商品洞察</span>
          <h1>输入一个 ASIN，<br />看见完整商品脉络</h1>
          <p>自动识别父子变体，整理商品信息，并从真实评论中提炼用户认可的优点与尚未解决的痛点。</p>
        </div>

        <form className="searchCard" onSubmit={submit}>
          <div className="fieldLabel">
            <label htmlFor="asin">商品 ASIN</label>
            <span>支持父体或子体</span>
          </div>
          <div className={`inputShell ${notice ? "invalid" : ""}`}>
            <span className="searchIcon">⌕</span>
            <input id="asin" value={asin} onChange={(e) => setAsin(e.target.value.toUpperCase().replace(/\s/g, ""))} maxLength={10} placeholder="例如 B0D9W0XH2M" />
            <span className="count">{asin.length}/10</span>
          </div>
          {notice && <p className="error">{notice}</p>}
          <div className="formRow">
            <div className="selectWrap">
              <label htmlFor="market">目标站点</label>
              <select id="market" value={market} onChange={(e) => setMarket(e.target.value)}>
                <option>美国站</option><option>英国站</option><option>德国站</option><option>日本站</option>
              </select>
            </div>
            <button className="primary" type="submit" disabled={stage === "running"}>
              {stage === "running" ? <><span className="spinner" /> 正在采集</> : <>开始采集 <span>→</span></>}
            </button>
          </div>
          <div className="privacy"><span>✓</span> 数据仅用于本次分析，不会公开或共享</div>
        </form>
      </section>

      {stage === "idle" && (
        <section className="emptyState">
          <div className="orbit"><div className="cube">▦</div></div>
          <h2>准备好开始了吗？</h2>
          <p>输入 ASIN 后，商品数据与评论洞察将在这里呈现。</p>
          <div className="featureRow">
            <span>◎ 父子体识别</span><span>◇ 商品信息采集</span><span>✦ 评论洞察分析</span>
          </div>
        </section>
      )}

      {stage === "running" && (
        <section className="progressCard" aria-live="polite">
          <div className="progressHead">
            <div><span className="pulse" /><b>正在采集商品数据</b><small>{asin.toUpperCase()} · Amazon {market}</small></div>
            <strong>{Math.min(92, 28 + step * 31)}%</strong>
          </div>
          <div className="progressTrack"><i style={{ width: `${Math.min(92, 28 + step * 31)}%` }} /></div>
          <div className="stepList">
            {steps.map(([title, desc], index) => (
              <div className={index <= step ? "step ready" : "step"} key={title}>
                <span>{index < step ? "✓" : index === step ? <i className="miniSpinner" /> : index + 1}</span>
                <div><b>{title}</b><small>{index <= step ? desc : "等待处理"}</small></div>
              </div>
            ))}
          </div>
        </section>
      )}

      {hasResult && (
        <section className="results">
          <div className="resultTop">
            <div><span className="success">✓ 采集完成</span><h2>商品数据总览</h2><p>更新于刚刚 · Amazon {market}</p></div>
            <button className="secondary" onClick={exportData}>↓ 导出数据</button>
          </div>

          <article className="productCard">
            <div className="productVisual"><div className="bagShape"><span>EVERYDAY</span></div><em>图片预览</em></div>
            <div className="productInfo">
              <div className="meta"><span>父体 ASIN</span><code>{asin.toUpperCase()}</code><button onClick={() => navigator.clipboard?.writeText(asin.toUpperCase())}>复制</button></div>
              <h3>Everyday 多功能轻量托特包，大容量通勤旅行单肩包</h3>
              <div className="rating"><b>4.6</b> <span>★★★★★</span> <small>2,418 条评分</small></div>
              <div className="tags"><span>Amazon&apos;s Choice</span><span>近 1 个月 1K+ 人购买</span><span>促销中</span></div>
              <div className="bullets"><p>✓ 轻量耐用面料，适合通勤与短途旅行</p><p>✓ 多分区收纳设计，可容纳 15.6 英寸电脑</p><p>✓ 可调节肩带，支持手提与单肩两种方式</p></div>
            </div>
          </article>

          <div className="sectionTitle"><div><h2>商品变体</h2><p>共识别到 4 个可售子体，价格与库存基于当前站点展示。</p></div><span className="chip">4 个子体</span></div>
          <div className="tableWrap">
            <table>
              <thead><tr><th>商品</th><th>子体 ASIN</th><th>变体属性</th><th>当前价格</th><th>库存状态</th><th>操作</th></tr></thead>
              <tbody>{variants.map((item) => <tr key={item.asin}>
                <td><div className={`swatch ${item.tone}`}>{item.image}</div></td>
                <td><code>{item.asin}</code></td><td>{item.attr}</td><td><b>{item.price}</b></td>
                <td><span className={item.stock === "有货" ? "stock" : "stock warn"}><i />{item.stock}</span></td>
                <td><button className="linkButton">查看详情 →</button></td>
              </tr>)}</tbody>
            </table>
          </div>

          <div className="sectionTitle insightsTitle"><div><h2>评论洞察</h2><p>基于高相关评论聚合分析，仅展示用户认可的优点与集中痛点。</p></div><span className="chip">分析 186 条评论</span></div>
          <div className="insightGrid">
            <article className="insight good">
              <div className="insightHead"><span>↗</span><div><h3>用户认可的优点</h3><p>高频正向反馈 · 适合强化卖点</p></div><b>78%</b></div>
              <InsightItem rank="01" title="面料柔软，背负舒适" text="包身轻且触感好，长时间通勤肩部压力小。" count="提及 62 次" width="86%" />
              <InsightItem rank="02" title="收纳空间比预期实用" text="分区清晰，电脑、水杯和日常用品各有位置。" count="提及 47 次" width="68%" />
              <InsightItem rank="03" title="做工与质感超出价格预期" text="走线整齐，整体外观简洁，日常搭配自然。" count="提及 36 次" width="52%" />
            </article>
            <article className="insight pain">
              <div className="insightHead"><span>!</span><div><h3>用户集中的痛点</h3><p>高频负向反馈 · 值得优先改善</p></div><b>22%</b></div>
              <InsightItem rank="01" title="肩带容易从肩上滑落" text="穿光滑面料外套时尤为明显，需要频繁调整。" count="提及 28 次" width="74%" />
              <InsightItem rank="02" title="浅色款不耐脏" text="底部和包角容易留下污渍，清洁频率较高。" count="提及 19 次" width="51%" />
              <InsightItem rank="03" title="主拉链顺滑度一般" text="少数用户反馈转角位置偶尔出现卡顿。" count="提及 12 次" width="34%" />
            </article>
          </div>
        </section>
      )}

      <footer><span>采数 · 商品数据获取工具</span><span>页面价格与库存因站点、配送地址及登录状态而异</span></footer>
    </main>
  );
}

function InsightItem({ rank, title, text, count, width }: { rank: string; title: string; text: string; count: string; width: string }) {
  return <div className="insightItem"><span className="rank">{rank}</span><div className="insightCopy"><div><b>{title}</b><small>{count}</small></div><p>{text}</p><i><em style={{ width }} /></i></div></div>;
}
