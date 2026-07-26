const form=document.querySelector("#form"),statusBox=document.querySelector("#status"),summaryBox=document.querySelector("#batchSummary"),resultBox=document.querySelector("#result"),button=document.querySelector("#submit"),asinsBox=document.querySelector("#asins"),countBox=document.querySelector("#asinCount");
let latestBatch=null;
const MAX_BATCH_ASINS=100;
const esc=(v="")=>String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const parseAsins=()=>[...new Set(asinsBox.value.toUpperCase().split(/[\s,;]+/).map(x=>x.trim()).filter(Boolean))];
asinsBox.addEventListener("input",()=>{const count=parseAsins().length;countBox.textContent=`${count} / ${MAX_BATCH_ASINS} 个 ASIN`;countBox.style.color=count>MAX_BATCH_ASINS?"#c94432":""});
form.addEventListener("submit",async e=>{
  e.preventDefault();const asins=parseAsins();if(!asins.length)return;if(asins.length>MAX_BATCH_ASINS){statusBox.className="status error";statusBox.innerHTML=`<b>超过批量上限</b><span>一次最多 ${MAX_BATCH_ASINS} 个 ASIN，请拆成多批采集。</span>`;return}
  statusBox.className="status loading";statusBox.innerHTML=`<b>正在逐个访问 Amazon…</b><span>共 ${asins.length} 个 ASIN；父体会继续采集全部子体，请留意 Chrome 登录窗口。</span>`;
  resultBox.className="hidden";summaryBox.className="hidden";button.disabled=true;
  try{
    const r=await fetch("/api/scrape/batch",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({asins,marketplace:document.querySelector("#market").value,max_review_pages:Number(document.querySelector("#pages").value),headless:false,variant_mode:document.querySelector("#variantMode").value})});
    const p=await r.json();if(!r.ok)throw new Error(p.detail||"采集失败");latestBatch=p;renderBatch(p);
    statusBox.className="status success";statusBox.innerHTML=`<b>✓ 批量采集完成</b><span>成功 ${p.succeeded} · 失败 ${p.failed} · 所有展示字段均来自本次真实页面</span>`;
  }catch(err){statusBox.className="status error";statusBox.innerHTML=`<b>采集未成功</b><span>${esc(err.message)}</span>`}finally{button.disabled=false}
});
function renderBatch(batch){
  summaryBox.innerHTML=`<div><b>本批次结果</b><span>${batch.total} 个输入 · ${batch.succeeded} 成功 · ${batch.failed} 失败</span></div><div><button onclick="exportExcel(this)">导出 XLSX（内嵌图片）</button><button onclick="exportJSON()">导出 JSON</button></div>`;
  summaryBox.className="batchSummary";
  resultBox.innerHTML=batch.items.map(item=>item.success?renderProduct(item.result):`<article class="failed"><b>${esc(item.requested_asin)}</b><span>${esc(item.error)}</span></article>`).join("");
  resultBox.className="";
}
function renderProduct(d){
  const advantages=d.insights.advantages.map(insight).join("")||"<p class='empty'>真实评论不足，暂时无法形成优点分析。</p>",pains=d.insights.pains.map(insight).join("")||"<p class='empty'>真实低星评论不足，暂时无法形成痛点分析。</p>";
  const main=d.is_parent_request?(d.variants.find(v=>v.is_suspected_main)||d.variants.find(v=>v.asin===d.suspected_main_asin)||null):null;
  const hero=main||{asin:d.asin,url:d.canonical_url||d.source_url,title:d.title,price:d.price,list_price:d.list_price,rating:d.rating,rating_count:d.rating_count,recent_sales_signal:d.recent_sales_signal,image:d.images[0],bullets:d.bullets};
  return `<section class="productResult"><div class="resultLabel"><span>${d.is_parent_request?`父体任务 · 计划 ${d.expected_child_count??d.variants.length} 个，完成 ${d.variants.length} 个`:"子体任务 · 仅采集当前子体"}</span><b>${esc(d.requested_asin)}</b></div>
  ${d.suspected_main_asin?`<div class="mainCandidate"><b>疑似主销：${esc(d.suspected_main_asin)}</b><span>置信度：${d.suspected_main_confidence==="high"?"高":d.suspected_main_confidence==="medium"?"中":"低"} · ${esc(d.suspected_main_reason||"")}</span></div>`:""}
  <article class="product"><div class="image">${hero.image?`<img src="${esc(hero.image)}" alt="">`:"<span>暂无图片</span>"}</div><div><div class="source"><span>${main?"主推链接":"真实来源"}</span><a target="_blank" rel="noreferrer" href="${esc(hero.url)}">${esc(hero.asin)} ↗</a></div><h2>${esc(hero.title)}</h2><div class="facts"><b>${esc(hero.price||"价格未展示")}</b>${hero.list_price?`<del>Typical price: ${esc(hero.list_price)}</del>`:""}<span>★ ${esc(hero.rating??"—")} · ${esc(hero.rating_count??"—")} 条评分</span><span>${esc(hero.recent_sales_signal||"月销量信号未展示")}</span></div><ul>${(hero.bullets||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div></article>
  ${d.warnings.length?`<div class="warnings">${d.warnings.map(x=>`<span>! ${esc(x)}</span>`).join("")}</div>`:""}
  <div class="sectionHead"><div><h2>${d.is_parent_request?"全部真实子体":"当前子体信息"}</h2><p>每条数据均来自对应子体详情页</p></div><b>${d.variants.length} 个</b></div>
  <div class="variantTable"><table><thead><tr><th>图片</th><th>ASIN / 标题</th><th>颜色 / 尺寸</th><th>价格</th><th>月销量信号</th><th>状态</th></tr></thead><tbody>${d.variants.map(v=>`<tr class="${v.is_suspected_main?"suspectedMain":""}"><td><a target="_blank" href="${esc(v.url)}">${v.image?`<img src="${esc(v.image)}" alt="">`:"无图"}</a></td><td><a target="_blank" href="${esc(v.url)}"><b>${v.is_suspected_main?'<em class="mainBadge">疑似主销</em> ':""}${esc(v.asin)} ↗</b></a><span>${esc(v.title||"标题未读取")}</span></td><td><b>${esc(v.color||"颜色未展示")}</b><span>${esc(v.size||"尺寸未展示")}</span></td><td><b>${esc(v.price||"未展示")}</b>${v.list_price?`<del>Typical: ${esc(v.list_price)}</del>`:""}</td><td><span>${esc(v.recent_sales_signal||"未展示")}</span></td><td><i class="${v.data_quality}">${v.data_quality==="complete"?"完整":"部分"}</i></td></tr>`).join("")}</tbody></table></div>
  <div class="sectionHead"><div><h2>评论洞察</h2><p>分析 ${d.insights.analyzed_reviews} 条本次实际读取的评论</p></div></div><div class="insights"><article><h3>↗ 用户认可的优点</h3>${advantages}</article><article class="pain"><h3>! 用户集中的痛点</h3>${pains}</article></div>
  <details><summary>查看本次原始评论证据（${d.reviews.length}）</summary>${d.reviews.map(r=>`<blockquote><b>${esc(r.rating??"—")} 星 · ${esc(r.title||"")}</b><p>${esc(r.body)}</p><small>${esc(r.date||"")}${r.verified?" · Verified Purchase":""}</small></blockquote>`).join("")}</details></section>`;
}
function insight(x){return `<div class="insight"><div><b>${esc(x.phrase)}</b><span>${x.mentions} 次</span></div>${x.evidence.map(e=>`<p>“${esc(e)}”</p>`).join("")}</div>`}
function exportJSON(){download(JSON.stringify(latestBatch,null,2),"amazon-products.json","application/json")}
async function exportExcel(button){const original=button.textContent;button.disabled=true;button.textContent="正在下载并嵌入图片…";try{const response=await fetch("/api/export/xlsx",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(latestBatch)});if(!response.ok){const error=await response.json();throw new Error(error.detail||"Excel 导出失败")}const url=URL.createObjectURL(await response.blob()),a=document.createElement("a"),stamp=new Date().toISOString().replaceAll(/[-:]/g,"").slice(0,15);a.href=url;a.download=`amazon-products-with-images-${stamp}.xlsx`;a.click();URL.revokeObjectURL(url)}catch(error){alert(error.message)}finally{button.disabled=false;button.textContent=original}}
function download(content,name,type){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement("a");a.href=url;a.download=name;a.click();URL.revokeObjectURL(url)}
