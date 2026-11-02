/* 擴充分頁：A 起漲偵測（#/rise）、B 族群輪動 RRG（#/rrg）、C 工具箱（#/tools/<sub>）。
   全部是靜態規則運算的結果（data/*.json），不呼叫任何 LLM／付費 API。
   C 工具箱的部分演算法與型態辨識來自 tw-trading-dashboard（MIT）：https://github.com/wakin61043/tw-trading-dashboard */
const EXT=(()=>{
const X={C:{},S:{type:'all',st:'起漲',rtype:'theme',tail:5,pick:null,rk:'official',hm:{mk:'all',mode:'chg',ind:null,date:null},pt:{p:'all',s:'all',more:40},sc:{r:'all',mk:'all',q:'',more:40},rd:'all',fl:{w:5,k:'f'},hd:{mode:'big',more:40},wl:'',sub:'today'}};
const TN={theme:'主題',ext:'新增',official:'官方'};
const get=async n=>{if(X.C[n])return X.C[n];const r=await fetch('data/'+n+'.json?v='+VER);if(!r.ok)throw new Error(n+' '+r.status);return X.C[n]=await r.json()};
const num=(v,d=1)=>v==null?'–':Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const q4=v=>v==null?'–':(v*100>0?'+':'')+(v*100).toFixed(2)+'%';
const NOTE=t=>`<div class="card note">${t}</div>`;
const WL=()=>{try{return JSON.parse(localStorage.getItem('wl')||'[]')}catch(e){return[]}};
const setWL=a=>{try{localStorage.setItem('wl',JSON.stringify(a))}catch(e){}};
const stLink=(id,nm)=>`<a href="#/k/${id}" style="color:inherit;text-decoration:none">${id} ${esc(nm)}</a>`;

/* ---------- 導覽 ---------- */
function nav(h){
  const on=h.startsWith('#/rise')?'rise':h.startsWith('#/rrg')?'rrg':h.startsWith('#/tools')?'tools':'flow';
  const e=document.getElementById('nav');if(!e)return;
  e.innerHTML=[['flow','#/','籌碼'],['rise','#/rise','起漲'],['rrg','#/rrg','輪動'],['tools','#/tools','工具']].map(a=>`<a href="${a[1]}" class="${on==a[0]?'on':''}">${a[2]}</a>`).join('');
}
const SECLINK=(t,n)=>`#/s/${t}/${encodeURIComponent(n)}`;
const spark=(a,col)=>{if(!a||a.length<2)return'';const mn=Math.min(...a),mx=Math.max(...a),W=84,H=30;const pts=a.map((v,i)=>(i/(a.length-1)*W).toFixed(1)+','+(H-2-(v-mn)/((mx-mn)||1)*(H-4)).toFixed(1)).join(' ');return`<svg class="sp" viewBox="0 0 ${W} ${H}"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.6"/></svg>`};
const stCls=s=>s=='起漲'?'up':s=='轉弱'?'dn':s=='候選'?'am':'fl';
const stCol=s=>s=='起漲'?'#ff5a5f':s=='轉弱'?'#2fcf84':s=='候選'?'#f2c45a':'#8f9ab3';
const pills=(key,sub,opts,cur)=>`<div class="pills">${opts.map(o=>`<button data-x="${key}" data-v="${esc(o[0])}" class="${cur==o[0]?'on':''}">${esc(o[1])}</button>`).join('')}</div>`;

/* ---------- A 起漲偵測 ---------- */
function pageRise(R){
  const s=X.S, m=R.market;
  let h=`<div class="card"><div class="nm" style="font-size:17px;font-weight:700">起漲偵測 <span class="chip fl">規則定義，非預測</span></div>`;
  if(m.ok)h+=`<div class="sub" style="margin-top:4px">大盤背景：加權指數 <b class="${cls(m.r1)}">${num(m.twii,0)}</b>（${q4(m.r1)}）· ${m.above?'<b class="up">站上</b>':'<b class="dn">跌破</b>'}20MA（${num(m.ma20,0)}）· 20MA斜率 <b class="${cls(m.slope)}">${m.slope>0?'向上':'向下'}</b> · 5日 ${q4(m.r5)}</div>`;
  const cnt=k=>R.items.filter(x=>x.status==k).length;
  if(!s.stInit){s.stInit=1;if(!cnt('起漲'))s.st=cnt('候選')?'候選':'all'}
  h+=`<div class="sub" style="margin-top:4px">資料日 ${R.date}　起漲 ${cnt('起漲')}　候選 ${cnt('候選')}　盤整 ${cnt('盤整')}　轉弱 ${cnt('轉弱')}（共 ${R.items.length} 個族群）</div></div>`;
  h+=pills('rtypeA','',[['all','全部'],['theme','主題族群'],['ext','新增族群'],['official','官方產業']],s.type);
  h+=pills('rst','',[['起漲','起漲'],['候選','候選'],['盤整','盤整'],['轉弱','轉弱'],['all','全部']],s.st);
  const L=R.items.filter(x=>(s.type=='all'||x.type==s.type)&&(s.st=='all'||x.status==s.st));
  const CN=['站上20MA','20MA向上','RS創20日高','過半成分站上20MA','5日≥+3%'];
  h+=L.length?L.map(x=>`<a class="rcard" href="${SECLINK(x.type,x.name)}"><div class="rrow"><div><div class="nm" style="font-weight:700">${esc(x.name)} <span class="chip ${stCls(x.status)}">${x.status}</span>${x.new?'<span class="chip ac">新轉入</span>':''}</div>
   <div class="sub">${TN[x.type]}族群 · ${x.n}檔 · 條件 ${x.score}/5${x.rising_day_n>1?' · 連續起漲 '+x.rising_day_n+' 天':''}</div></div>${spark(x.spark,stCol(x.status))}</div>
   <div class="cond">${CN.map((c,i)=>`<i class="${x.conds[i]?'y':''}">${x.conds[i]?'✓':'✗'} ${c}</i>`).join('')}</div>
   <div class="stats"><div><span>5日</span><b class="${cls(x.r5)}">${q4(x.r5)}</b></div><div><span>20日</span><b class="${cls(x.r20)}">${q4(x.r20)}</b></div><div><span>站上20MA</span><b>${Math.round(x.pct_above_ma20*100)}%</b></div><div><span>創20日高</span><b>${x.n_high20}檔</b></div></div>
   ${x.lead.length?`<div class="sub" style="margin-top:5px">5日領漲：${x.lead.map(l=>esc(l[1])+' <span class="'+cls(l[2])+'">'+q4(l[2])+'</span>').join('、')}</div>`:''}</a>`).join(''):'<div class="card">目前沒有符合的族群</div>';
  h+=NOTE(`<b>怎麼判定（純規則，非預測）</b><br>族群指數＝成分股（已還原除權息）日報酬的等權連乘，起點100。五個條件各算一分：①指數在20日均線之上；②20日均線的5日斜率為正；③相對強弱（族群指數÷發行量加權股價報酬指數）創20日新高；④至少一半成分股站上自己的20日均線；⑤5日漲幅≥3%。<br><b>起漲</b>＝5分全中（≥5）；<b>候選</b>＝≥3分且①②都成立；<b>轉弱</b>＝指數跌破20日均線且未達候選；其餘為<b>盤整</b>。「新轉入」＝昨天不是起漲／候選、今天是。連續起漲天數＝近8個交易日內連續為「起漲」的天數。<br>這只描述「目前已經轉強」的狀態，不保證後續上漲；非投資建議。`);
  return h;
}

/* ---------- B RRG ---------- */
function rrgSvg(R){
  const s=X.S, L=R.items.filter(x=>s.rtype=='all'||x.type==s.rtype), T=s.tail;
  const W=360,H=360,pad=26;
  const P=L.map(x=>({x,pts:x.pts.slice(-(T+1))}));
  let xs=[],ys=[];P.forEach(p=>p.pts.forEach(a=>{xs.push(a[0]);ys.push(a[1])}));
  let dx=Math.max(1.2,...xs.map(v=>Math.abs(v-100))),dy=Math.max(1.2,...ys.map(v=>Math.abs(v-100)));
  dx*=1.12;dy*=1.12;
  const X_=v=>pad+(v-(100-dx))/(2*dx)*(W-2*pad),Y_=v=>H-pad-(v-(100-dy))/(2*dy)*(H-2*pad);
  const QC={領先:'#ff5a5f',轉弱:'#f2c45a',落後:'#2fcf84',改善:'#5aa2ff'};
  let g=`<rect x="${X_(100)}" y="${pad}" width="${W-pad-X_(100)}" height="${Y_(100)-pad}" fill="#ff5a5f" opacity=".09"/><rect x="${X_(100)}" y="${Y_(100)}" width="${W-pad-X_(100)}" height="${H-pad-Y_(100)}" fill="#f2c45a" opacity=".07"/><rect x="${pad}" y="${Y_(100)}" width="${X_(100)-pad}" height="${H-pad-Y_(100)}" fill="#2fcf84" opacity=".08"/><rect x="${pad}" y="${pad}" width="${X_(100)-pad}" height="${Y_(100)-pad}" fill="#5aa2ff" opacity=".08"/>`;
  g+=`<line x1="${X_(100)}" y1="${pad}" x2="${X_(100)}" y2="${H-pad}" stroke="#2b3550"/><line x1="${pad}" y1="${Y_(100)}" x2="${W-pad}" y2="${Y_(100)}" stroke="#2b3550"/>`;
  g+=`<text x="${W-pad-3}" y="${pad+11}" text-anchor="end" font-size="11" fill="#ff5a5f">領先</text><text x="${W-pad-3}" y="${H-pad-4}" text-anchor="end" font-size="11" fill="#f2c45a">轉弱</text><text x="${pad+3}" y="${H-pad-4}" font-size="11" fill="#2fcf84">落後</text><text x="${pad+3}" y="${pad+11}" font-size="11" fill="#5aa2ff">改善</text>`;
  g+=`<text x="${W/2}" y="${H-6}" text-anchor="middle" font-size="10" fill="#8f9ab3">RS-Ratio（相對強度，→ 越強）</text><text x="9" y="${H/2}" font-size="10" fill="#8f9ab3" transform="rotate(-90 9 ${H/2})" text-anchor="middle">RS-Momentum（動能 ↑）</text>`;
  const dist=p=>{const e=p.pts[p.pts.length-1];return Math.hypot((e[0]-100)/dx,(e[1]-100)/dy)};
  const topN=new Set(P.slice().sort((a,b)=>dist(b)-dist(a)).slice(0,L.length<=12?99:7).map(p=>p.x.type+'|'+p.x.name));
  P.forEach(p=>{const c=QC[p.x.q],sel=s.pick==p.x.type+'|'+p.x.name;
    const d=p.pts.map((a,i)=>(i?'L':'M')+X_(a[0]).toFixed(1)+' '+Y_(a[1]).toFixed(1)).join('');
    g+=`<path d="${d}" fill="none" stroke="${c}" stroke-width="${sel?2.4:.9}" opacity="${sel?1:(s.pick?.18:.4)}"/>`;
    if(sel)p.pts.slice(0,-1).forEach(a=>{g+=`<circle cx="${X_(a[0]).toFixed(1)}" cy="${Y_(a[1]).toFixed(1)}" r="1.4" fill="${c}" opacity=".5"/>`});
    const e=p.pts[p.pts.length-1],cx=X_(e[0]).toFixed(1),cy=Y_(e[1]).toFixed(1);
    g+=`<circle cx="${cx}" cy="${cy}" r="${sel?6:4.2}" fill="${c}" stroke="#0f1420" stroke-width="1"/><circle data-x="pick" data-v="${esc(p.x.type+'|'+p.x.name)}" cx="${cx}" cy="${cy}" r="13" fill="transparent"/>`;
    if(sel||topN.has(p.x.type+'|'+p.x.name))g+=`<text x="${(+cx+6).toFixed(1)}" y="${(+cy-5).toFixed(1)}" font-size="9.5" fill="#e8ecf4" stroke="#0f1420" stroke-width="2.4" paint-order="stroke">${esc(p.x.name)}</text>`;
  });
  return `<svg class="xc" viewBox="0 0 ${W} ${H}" role="img" aria-label="族群輪動圖">${g}</svg>`;
}
function pageRrg(R){
  const s=X.S;
  let h=`<div class="card"><div class="nm" style="font-size:17px;font-weight:700">族群輪動 RRG <span class="chip fl">相對強弱</span></div><div class="sub">基準：${esc(R.bench)}　資料日 ${R.date}</div></div>`;
  h+=pills('rrt','',[['theme','主題族群'],['ext','新增族群'],['official','官方產業'],['all','全部']],s.rtype);
  h+=`<div class="card"><div class="row sub"><span>尾巴長度（交易日）</span><b id="tailv">${s.tail}</b></div><input type="range" min="3" max="20" value="${s.tail}" id="tail" aria-label="尾巴長度"><div id="rrgbox">${rrgSvg(R)}</div><div class="sub" id="pickbox">${pickInfo(R)}</div></div>`;
  const QO=['領先','改善','轉弱','落後'],QC={領先:'up',轉弱:'am',落後:'dn',改善:'ac'};
  const L=R.items.filter(x=>s.rtype=='all'||x.type==s.rtype);
  QO.forEach(q=>{const a=L.filter(x=>x.q==q).sort((a,b)=>b.pts[b.pts.length-1][0]-a.pts[a.pts.length-1][0]);if(!a.length)return;
    h+=`<div class="card"><div class="nm" style="font-weight:700"><span class="chip ${QC[q]}" style="margin:0">${q}</span> ${a.length}個</div>${a.map(x=>{const e=x.pts[x.pts.length-1];return`<a class="tr" style="grid-template-columns:1fr auto auto" href="${SECLINK(x.type,x.name)}"><span class="n">${esc(x.name)} <span class="mut xs">${TN[x.type]}</span></span><span class="xs mut">${e[0].toFixed(1)} / ${e[1].toFixed(1)}</span><span class="${cls(x.r5)}">${q4(x.r5)}</span></a>`}).join('')}</div>`});
  h+=NOTE(`<b>怎麼看</b>：橫軸 RS-Ratio＝「族群等權指數÷基準」的相對強弱，用近20日標準化（z分數）再加100，&gt;100 表示比基準強；縱軸 RS-Momentum＝RS-Ratio 與5日前的差再加100，&gt;100 表示相對強度在變強。順時針輪動：<b class="ac">改善</b>→<b class="up">領先</b>→<b style="color:#f2c45a">轉弱</b>→<b class="dn">落後</b>。尾巴＝最近 N 日軌跡，圓點＝最新。點圓點看詳情，列表可進入族群頁。<br>基準使用<b>發行量加權股價報酬指數</b>（證交所公布，含股利再投入），比價格指數更能代表「大盤實際報酬」；這是 RRG 的一種簡化算法，與 StockCharts 的 JdK RS-Ratio 數值不同，僅供輪動觀察，非投資建議。`);
  return h;
}
function pickInfo(R){const k=X.S.pick;if(!k)return'點圖上的圓點查看族群';const [t,n]=k.split('|'),x=R.items.find(a=>a.type==t&&a.name==n);if(!x)return'';const e=x.pts[x.pts.length-1];return`<a href="${SECLINK(t,n)}"><b>${esc(n)}</b></a>（${TN[t]}）· ${x.q} · RS-Ratio ${e[0].toFixed(1)} / 動能 ${e[1].toFixed(1)} · 5日 <span class="${cls(x.r5)}">${q4(x.r5)}</span> · <a href="${SECLINK(t,n)}">進入族群頁 ›</a>`}

/* ---------- C 工具箱 ---------- */
const SUBS=[['today','今日焦點'],['rank','族群排名'],['heat','資金熱浪'],['pat','型態選股'],['score','研究評分'],['radar','異動雷達'],['flow','法人期貨'],['hold','大戶集中'],['watch','自選']];
function subnav(cur){return`<div class="subnav">${SUBS.map(a=>`<a href="#/tools/${a[0]}" class="${cur==a[0]?'on':''}">${a[1]}</a>`).join('')}</div>`}

function tToday(N){
  let h=`<div class="card"><div class="nm" style="font-weight:700">盤後日報 <span class="chip fl">規則版・非 AI</span></div><div class="sub">資料日 ${N.date}（依當日數據套固定模板產生，沒有語言模型）</div>${N.brief.map(b=>`<div style="margin-top:8px"><span class="chip ${b[2]}" style="margin:0 6px 0 0">${esc(b[0])}</span>${esc(b[1])}</div>`).join('')}</div>`;
  if(N.cal&&N.cal.length)h+=`<div class="card"><div class="nm" style="font-weight:700">本週重要經濟數據（高重要性）</div><div class="sub">來源：Forex Factory；時間為台北時間</div>${N.cal.map(e=>`<div class="tr" style="grid-template-columns:78px 36px 1fr"><span class="xs mut">${esc(e.t)}</span><span class="chip fl" style="margin:0">${esc(e.c)}</span><span>${esc(e.n)}${e.f?`<span class="xs mut"> 預期 ${esc(e.f)}${e.p?' 前值 '+esc(e.p):''}</span>`:''}</span></div>`).join('')}</div>`;
  h+=`<div class="card"><div class="nm" style="font-weight:700">台股頭條（鉅亨網）</div>${(N.news||[]).map(n=>`<a class="nl" href="${safeUrl(n.u)}" target="_blank" rel="noopener"><div>${esc(n.t)}</div><div class="xs mut">${esc(n.ts)} · 鉅亨網</div></a>`).join('')||'<div class="sub">暫無新聞</div>'}</div>`;
  return h;
}
function tRank(R){
  const s=X.S,L=R.rows[s.rk]||[];
  let h=pills('rkt','',[['theme','主題族群'],['ext','新增族群'],['official','官方產業']],s.rk);
  h+=`<div class="card"><div class="sub">依「強度」排序　資料日 ${R.date}</div>`;
  h+=L.map(r=>`<a class="tr" style="grid-template-columns:34px 1fr 62px 58px" href="${SECLINK(s.rk,r.name)}"><span class="mut xs">${r.rank}${r.move?`<br><b class="${r.move>0?'up':'dn'}">${r.move>0?'▲':'▼'}${Math.abs(r.move)}</b>`:''}</span>
   <span><span class="n" style="display:block">${esc(r.name)}</span><span class="xs mut">${r.n}檔 · 漲${r.up}/跌${r.dn} · ${esc(r.top[1])} <span class="${cls(r.top[2])}">${q4(r.top[2])}</span></span></span>
   <span style="text-align:right"><b class="${cls(r.score)}">${q4(r.score)}</b><br><span class="xs mut">${num(r.amt,0)}億</span></span><span style="text-align:right" class="xs mut">廣度<br>${Math.round(r.breadth*100)}%</span></a>`).join('')+`</div>`;
  h+=NOTE(`<b>強度</b>＝成員漲跌幅以 √成交金額 加權平均（避免單一爆量股主導，也不讓小型股雜訊失真）；成交金額占族群不到0.5%或不到1,000萬者不計入。廣度＝上漲家數÷成員數。排名變化對比前一交易日。演算法移植自 tw-trading-dashboard（MIT）。`);
  return h;
}
/* treemap */
function squarify(items,x,y,w,h){
  const tot=items.reduce((a,b)=>a+b.v,0),out=[];if(!tot||w<=0||h<=0)return out;
  let rest=items.map(i=>Object.assign({},i,{a:i.v*w*h/tot})),rx=x,ry=y,rw=w,rh=h;
  const worst=(row,side)=>{const s=row.reduce((a,b)=>a+b.a,0),mx=Math.max(...row.map(r=>r.a)),mn=Math.min(...row.map(r=>r.a));return Math.max(side*side*mx/(s*s),s*s/(side*side*mn))};
  while(rest.length){
    const side=Math.min(rw,rh);let row=[rest[0]],i=1;
    while(i<rest.length){const nr=row.concat(rest[i]);if(worst(nr,side)<=worst(row,side)){row=nr;i++}else break}
    rest=rest.slice(row.length);const s=row.reduce((a,b)=>a+b.a,0);
    if(rw>=rh){const cw=s/rh;let cy=ry;row.forEach(r=>{const hh=r.a/cw;out.push(Object.assign({},r,{x:rx,y:cy,w:cw,h:hh}));cy+=hh});rx+=cw;rw-=cw}
    else{const rhh=s/rw;let cx=rx;row.forEach(r=>{const ww=r.a/rhh;out.push(Object.assign({},r,{x:cx,y:ry,w:ww,h:rhh}));cx+=ww});ry+=rhh;rh-=rhh}
  }
  return out;
}
const heatCol=(v,mode)=>{if(v==null||isNaN(v))return'#3a4560';const k=mode=='chg'?7:80,a=Math.min(1,Math.abs(v)/k);if(Math.abs(v)<(mode=='chg'?.05:1))return'#3a4560';return v>0?`rgba(255,90,95,${(.3+.7*a).toFixed(2)})`:`rgba(47,207,132,${(.3+.7*a).toFixed(2)})`};
function heatSvg(Hd){
  const s=X.S.hm,rows=Hd.rows.filter(r=>s.mk=='all'||(s.mk=='twse'?r[2]==0:r[2]==1));
  const W=360,Ht=430,mode=s.mode;
  let inds={};rows.forEach(r=>{const k=Hd.ind[r[3]];(inds[k]=inds[k]||{k,v:0,cw:0,pm:0,rows:[]});const o=inds[k];o.v+=r[4];o.cw+=r[4]*r[5];o.rows.push(r);if(r[6]!=null)o.pm+=r[6]});
  let g='';
  const colOf=(chg,m,pm)=>mode=='chg'?heatCol(chg,'chg'):heatCol(pm?(m-pm):null,'money');
  if(s.ind&&inds[s.ind]){
    const o=inds[s.ind],list=o.rows.slice().sort((a,b)=>b[4]-a[4]).slice(0,48);
    squarify(list.map(r=>({v:r[4],r})),0,0,W,Ht).forEach(t=>{const r=t.r,fs=Math.max(8,Math.min(13,t.w/4.2));
      g+=`<g data-x="hst" data-v="${r[0]}"><rect x="${t.x.toFixed(1)}" y="${t.y.toFixed(1)}" width="${Math.max(0,t.w-1).toFixed(1)}" height="${Math.max(0,t.h-1).toFixed(1)}" fill="${colOf(r[5],r[4],r[6])}"/>`;
      if(t.w>34&&t.h>20)g+=`<text x="${(t.x+3).toFixed(1)}" y="${(t.y+fs+2).toFixed(1)}" font-size="${fs}" fill="#fff" font-weight="600">${esc(r[1])}</text>`;
      if(t.w>34&&t.h>34)g+=`<text x="${(t.x+3).toFixed(1)}" y="${(t.y+fs*2+4).toFixed(1)}" font-size="${(fs-1).toFixed(1)}" fill="#fff">${r[5]>0?'+':''}${r[5].toFixed(2)}%</text>`;g+='</g>'});
  }else{
    const L=Object.values(inds).sort((a,b)=>b.v-a.v);
    squarify(L.map(o=>({v:o.v,o})),0,0,W,Ht).forEach(t=>{const o=t.o,hd=t.h>40&&t.w>56?13:0;
      g+=`<g data-x="hind" data-v="${esc(o.k)}"><rect x="${t.x.toFixed(1)}" y="${t.y.toFixed(1)}" width="${Math.max(0,t.w).toFixed(1)}" height="${Math.max(0,t.h).toFixed(1)}" fill="#101828" stroke="#0f1420"/>`;
      const top=o.rows.slice().sort((a,b)=>b[4]-a[4]).slice(0,12);
      squarify(top.map(r=>({v:r[4],r})),t.x+1,t.y+hd+1,t.w-2,t.h-hd-2).forEach(c=>{const r=c.r;
        g+=`<rect x="${c.x.toFixed(1)}" y="${c.y.toFixed(1)}" width="${Math.max(0,c.w-.8).toFixed(1)}" height="${Math.max(0,c.h-.8).toFixed(1)}" fill="${colOf(r[5],r[4],r[6])}"/>`;
        if(c.w>30&&c.h>15)g+=`<text x="${(c.x+2).toFixed(1)}" y="${(c.y+10).toFixed(1)}" font-size="${c.w>46?9.5:8.5}" fill="#fff">${esc(r[1])}</text>`;
        if(c.w>30&&c.h>26)g+=`<text x="${(c.x+2).toFixed(1)}" y="${(c.y+20).toFixed(1)}" font-size="8.5" fill="#fff" opacity=".9">${r[5]>0?'+':''}${r[5].toFixed(1)}%</text>`});
      if(hd)g+=`<text x="${(t.x+3).toFixed(1)}" y="${(t.y+10).toFixed(1)}" font-size="10" fill="#e8ecf4" font-weight="700">${esc(o.k)}</text>`;g+='</g>'});
  }
  return`<svg class="xc tm" viewBox="0 0 ${W} ${Ht}" role="img" aria-label="資金熱浪">${g}</svg>`;
}
async function tHeat(M){
  const s=X.S.hm;s.date=s.date||M.dates[M.dates.length-1];
  const Hd=await get('heat/'+s.date);
  const rows=Hd.rows.filter(r=>s.mk=='all'||(s.mk=='twse'?r[2]==0:r[2]==1));
  const tot=rows.reduce((a,r)=>a+r[4],0),pm=rows.reduce((a,r)=>a+(r[6]||0),0),up=rows.filter(r=>r[5]>0).length,dn=rows.filter(r=>r[5]<0).length,lu=rows.filter(r=>r[5]>=9.5).length,ld=rows.filter(r=>r[5]<=-9.5).length;
  const ind={};rows.forEach(r=>{const k=Hd.ind[r[3]];const o=ind[k]=ind[k]||{k,v:0,p:0};o.v+=r[4];o.p+=r[6]||0});
  const dm=Object.values(ind).map(o=>({k:o.k,d:o.v-o.p})).sort((a,b)=>b.d-a.d);
  let h=`<div class="card"><div class="row"><div><div class="sub">成交金額</div><div class="big">${num(tot/100,0)}<small>億</small></div></div><div style="text-align:right"><div class="sub">較前日</div><div class="${cls(tot-pm)}" style="font-weight:700">${pm?q4(tot/pm-1):'–'}</div></div></div><div class="sub">上漲 <b class="up">${up}</b>・下跌 <b class="dn">${dn}</b>・漲停 <b class="up">${lu}</b>・跌停 <b class="dn">${ld}</b></div></div>`;
  h+=`<select class="in" data-x="hdate" aria-label="日期">${M.dates.slice().reverse().map(d=>`<option ${d==s.date?'selected':''}>${d}</option>`).join('')}</select>`;
  h+=pills('hmk','',[['all','上市＋上櫃'],['twse','上市'],['tpex','上櫃']],s.mk)+pills('hmode','',[['chg','顏色＝漲跌幅'],['money','顏色＝資金增減']],s.mode);
  h+=`<div class="legend"><span>面積＝成交金額</span><span><i style="background:rgba(255,90,95,.9)"></i>${s.mode=='chg'?'上漲':'資金流入'}</span><span><i style="background:rgba(47,207,132,.9)"></i>${s.mode=='chg'?'下跌':'資金流出'}</span></div>`;
  if(s.ind)h+=`<div class="rrow" style="margin-bottom:6px"><b>${esc(s.ind)}</b><button class="more" style="width:auto;padding:0 14px;min-height:40px" data-x="hind" data-v="">‹ 回全部產業</button></div>`;
  h+=`<div class="card" style="padding:6px">${heatSvg(Hd)}</div><div class="sub" style="margin-bottom:8px">${s.ind?'點股票進入個股頁':'點產業放大，再點個股進入個股頁'}</div>`;
  h+=`<div class="card"><div class="nm" style="font-weight:700">資金增減（較前日成交金額）</div><div class="sub">流入前5</div>${dm.slice(0,5).map(o=>`<div class="row"><span>${esc(o.k)}</span><b class="up">${sgn(o.d/100,0)}億</b></div>`).join('')}<div class="sub" style="margin-top:6px">流出前5</div>${dm.slice(-5).reverse().map(o=>`<div class="row"><span>${esc(o.k)}</span><b class="dn">${sgn(o.d/100,0)}億</b></div>`).join('')}</div>`;
  h+=NOTE('面積＝當日成交金額（證交所／櫃買中心收盤行情），顏色＝漲跌幅（紅漲綠跌）或較前一交易日的成交金額增減；產業別為官方分類，每個產業只畫成交金額前12檔。只有盤後資料，沒有盤中即時。概念移植自 tw-trading-dashboard（MIT）。');
  return h;
}
const PCOL=c=>c=='breakout'||c=='bullish'?'#ff5a5f':'#f2c45a';
function patSvg(x){
  const c=x.c,W=300,H=96,mn=Math.min(...c),mx=Math.max(...c,x.res),m2=Math.min(mn,x.sup),Y=v=>H-4-(v-m2)/((mx-m2)||1)*(H-10),Xp=i=>i/(c.length-1)*W;
  let g=`<polyline points="${c.map((v,i)=>Xp(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')}" fill="none" stroke="#8fb4ff" stroke-width="1.4"/>`;
  (x.lines||[]).forEach((l,i)=>{g+=`<line x1="${Xp(l[1]).toFixed(1)}" y1="${Y(l[3]).toFixed(1)}" x2="${Xp(l[2]).toFixed(1)}" y2="${Y(l[4]).toFixed(1)}" stroke="${i?'#2fcf84':'#ff5a5f'}" stroke-width="1.2" stroke-dasharray="4 3"/>`});
  return`<svg class="xc" viewBox="0 0 ${W} ${H}" style="margin-top:6px"><rect width="${W}" height="${H}" fill="#141b2b" rx="6"/>${g}</svg>`;
}
function tPat(P){
  const s=X.S.pt;
  let h=`<div class="card"><div class="sub">資料日 ${P.date}　掃描 ${P.scanned} 檔（近90日型態，5日均量≥300張，排除金融／水泥／造紙／紡織等）　命中 ${P.hits.length} 組</div></div>`;
  h+=pills('ptp','',[['all','全部型態']].concat(P.types.map(t=>[t.id,t.name])),s.p)+pills('pts','',[['all','全部'],['量價確認','量價確認'],['突破待量確認','突破待量'],['接近突破','接近突破']],s.s);
  const L=P.hits.filter(x=>(s.p=='all'||x.pid==s.p)&&(s.s=='all'||x.status==s.s||(s.s=='突破待量確認'&&x.status=='突破待次日確認')));
  h+=L.slice(0,s.more).map(x=>`<div class="rcard"><div class="rrow"><div><div class="nm" style="font-weight:700">${stLink(x.sid,x.name)} <span class="chip ac">${esc(x.pname)}</span></div><div class="sub">${esc(x.ind)} · 收 ${num(x.close,2)} <span class="${cls(x.r1)}">${q4(x.r1)}</span></div></div><div style="text-align:right"><div class="big up" style="font-size:22px">${x.score}</div><span class="chip ${x.status=='量價確認'?'up':'fl'}" style="margin:0">${esc(x.status)}</span></div></div>
   ${patSvg(x)}<div class="sub" style="margin-top:4px">壓力 ${num(x.res,2)}（紅）· 支撐 ${num(x.sup,2)}（綠）· 突破量比 ${num(x.vr,1)}倍${x.bdate?' · 突破日 '+x.bdate.slice(5):''}</div>
   <div class="stats" style="grid-template-columns:repeat(4,1fr)"><div><span>進場帶</span><b>${num(x.plan.entry,2)}</b></div><div><span>停損參考</span><b class="dn">${num(x.plan.stop,2)}</b></div><div><span>量度目標</span><b class="up">${num(x.plan.target,2)}</b></div><div><span>報酬/風險</span><b>${num(x.plan.rr,2)}</b></div></div>
   <div class="xs mut" style="margin-top:4px">${esc(x.plan.action)}</div></div>`).join('')||'<div class="card">沒有符合的型態</div>';
  if(L.length>s.more)h+=`<button class="more" data-x="ptmore">再顯示更多（${L.length-s.more}）</button>`;
  h+=NOTE('型態由 tw-trading-dashboard（MIT）的偵測程式以數值規則辨識（頭肩底、W底、圓弧底、上升三角、收斂楔形、旗型、三角旗、杯柄、三重底、盤整突破等10種，90個交易日、高低點需後續3根確認，不使用未來資料）。分數＝幾何品質＋突破確認＋量能＋趨勢。進場帶／停損／目標是「條件式技術計畫」的機械化數字，不含法說、財報、除權息等事件，亦不是買賣建議。');
  return h;
}
function tScore(Sc){
  const s=X.S.sc;
  let h=`<div class="card"><div class="sub">資料日 ${Sc.date}　權重：技術30・籌碼30・產業25（「話題」15%屬人工判斷、無公開資料，已剔除並重新配權；各檔「有效權重」見卡片）</div></div>`;
  h+=`<input class="in" data-x="scq" placeholder="輸入代號或名稱，例如 2330" value="${esc(s.q)}" inputmode="search" aria-label="搜尋">`;
  h+=pills('scr','',[['all','全部'],['強勢','強勢≥75'],['中性偏強','中性偏強'],['中性偏弱','中性偏弱'],['弱勢','弱勢<40']],s.r)+pills('scm','',[['all','上市＋上櫃'],['0','上市'],['1','上櫃']],s.mk);
  const w=WL(),q=s.q.trim();
  const L=Sc.rows.filter(r=>(s.r=='all'||r[5].replace('暫評・','')==s.r)&&(s.mk=='all'||String(r[2])==s.mk)&&(!q||r[0].startsWith(q)||r[1].includes(q)));
  h+=`<div class="sub" style="margin-bottom:6px">共 ${L.length} 檔，依分數排序</div>`;
  h+=L.slice(0,s.more).map(r=>scCard(r,w)).join('')||'<div class="card">沒有符合的股票</div>';
  if(L.length>s.more)h+=`<button class="more" data-x="scmore">再顯示更多（${L.length-s.more}）</button>`;
  h+=NOTE('<b>研究評分</b>（移植 tw-trading-dashboard 的規則，不是 AI）：<b>技術</b>＝趨勢（收盤>20MA、20MA>60MA、60MA>120MA）×0.4＋60日動能×0.25＋60MA斜率×0.2＋穩定度（距60日高回落與乖離）×0.15，需140根以上還原K線；<b>籌碼</b>＝外資＋投信20日淨買賣÷20日成交量、與買超天數占比；<b>產業</b>＝所屬官方產業的站上60MA比例、月營收年增率中位數、60日報酬中位數。缺少的因子會剔除並把權重按比例重配，評等前面標「暫評」代表不是三因子都齊全。≥75強勢、55–74中性偏強、40–54中性偏弱、&lt;40弱勢。PE／PB／殖利率取自證交所與櫃買中心，營收年增／月增取自公開資訊觀測站（政府開放資料）。僅為規則評分，非投資建議。');
  return h;
}
const scCard=(r,w)=>{const c=r[5].includes('強勢')&&!r[5].includes('弱')?'up':r[5].includes('偏強')?'up':r[5].includes('弱')?'dn':'fl';
  return`<div class="rcard"><div class="rrow"><div><div class="nm" style="font-weight:700">${stLink(r[0],r[1])} <span class="chip fl">${r[2]?'櫃':'市'}</span></div><div class="sub">${esc(r[3])} · 收 ${num(r[16],2)} <span class="${cls(r[15])}">${q4(r[15])}</span></div></div><div style="display:flex;align-items:center;gap:4px"><div style="text-align:right"><div class="big ${c}" style="font-size:24px">${r[4]}</div><span class="chip ${c}" style="margin:0">${esc(r[5])}</span></div><button class="wl ${w.includes(r[0])?'on':''}" data-x="wl" data-v="${r[0]}" aria-label="加入自選">${w.includes(r[0])?'★':'☆'}</button></div></div>
  <div class="fac"><div>技術 <b>${r[6]==null?'–':r[6]}</b><div class="bar"><b style="width:${r[6]||0}%"></b></div></div><div>籌碼 <b>${r[7]==null?'–':r[7]}</b><div class="bar"><b style="width:${r[7]||0}%"></b></div></div><div>產業 <b>${r[8]==null?'–':r[8]}</b><div class="bar"><b style="width:${r[8]||0}%"></b></div></div></div>
  <div class="stats"><div><span>PE</span><b>${num(r[10],1)}</b></div><div><span>PB</span><b>${num(r[11],2)}</b></div><div><span>殖利率</span><b>${r[12]==null?'–':num(r[12],2)+'%'}</b></div><div><span>營收年增</span><b class="${cls(r[13])}">${r[13]==null?'–':sgn(r[13],1)+'%'}</b></div></div><div class="xs mut" style="margin-top:3px">有效權重 ${r[9]}%</div></div>`};
function tRadar(Rd){
  const s=X.S.rd;
  const F_={all:()=>true,漲停:e=>e.tags.some(t=>t[0]=='漲停'),跌停:e=>e.tags.some(t=>t[0]=='跌停'),急漲:e=>e.tags.some(t=>t[0].startsWith('急漲')),急跌:e=>e.tags.some(t=>t[0].startsWith('急跌')),爆量:e=>e.tags.some(t=>t[0].startsWith('爆量')),型態:e=>e.tags.some(t=>t[0].startsWith('型態'))};
  let h=`<div class="card"><div class="sub">收盤後規則版異動（非盤中即時）　資料日 ${Rd.date}　共 ${Rd.total} 檔，列前 ${Rd.items.length}</div></div>`;
  h+=pills('rd','',[['all','全部'],['漲停','漲停'],['跌停','跌停'],['急漲','急漲'],['急跌','急跌'],['爆量','爆量'],['型態','型態突破']],s);
  const L=Rd.items.filter(F_[s]);
  h+=L.slice(0,80).map(e=>`<a class="rcard" href="#/k/${e.sid}"><div class="rrow"><div><div class="nm" style="font-weight:700">${e.sid} ${esc(e.name)} <span class="chip fl">${e.mk=='上市'?'市':'櫃'}</span></div><div class="sub">${esc(e.ind)} · 成交 ${num(e.amt,1)}億${e.vr?' · 量比 '+e.vr+'倍':''}</div></div><div style="text-align:right"><b class="${cls(e.r1)}" style="font-size:17px">${q4(e.r1)}</b><div class="xs mut">${num(e.close,2)}</div></div></div><div class="cond">${e.tags.map(t=>`<i class="${t[1]=='up'?'y':''}" style="${t[1]=='dn'?'background:#12392b;color:var(--dn)':''}">${esc(t[0])}</i>`).join('')}</div></a>`).join('')||'<div class="card">今天沒有符合的異動</div>';
  h+=NOTE('規則：漲停／跌停＝漲跌幅達±9.5%；急漲／急跌＝±7%且成交≥1億；爆量＝量≥前20日均量2倍且成交≥1億；型態突破＝今日量價確認的型態選股。原版的盤中即時雷達、自訂停損提醒需要即時資料與推播，這裡沒有搬。');
  return h;
}
function bars(a,w=340,h=70){const mx=Math.max(1,...a.map(v=>Math.abs(v||0)));const bw=w/a.length;return`<svg class="xc" viewBox="0 0 ${w} ${h}">${a.map((v,i)=>{const hh=Math.abs(v||0)/mx*(h/2-2);return`<rect x="${(i*bw+1).toFixed(1)}" y="${((v||0)>=0?h/2-hh:h/2).toFixed(1)}" width="${(bw-2).toFixed(1)}" height="${Math.max(1,hh).toFixed(1)}" fill="${(v||0)>=0?'#ff5a5f':'#2fcf84'}"/>`}).join('')}<line x1="0" y1="${h/2}" x2="${w}" y2="${h/2}" stroke="#2b3550"/></svg>`}
function tFlow(Fl){
  const s=X.S.fl,m=Fl.mkt;let h='';
  const last=m[m.length-1];
  h+=`<div class="card"><div class="nm" style="font-weight:700">三大法人買賣超（上市，億元）</div><div class="sub">${last?last.d:''}　外資 <b class="${cls(last.f)}">${sgn(last.f,0)}</b>・投信 <b class="${cls(last.t)}">${sgn(last.t,0)}</b>・自營商 <b class="${cls(last.dl)}">${sgn(last.dl,0)}</b></div>
  <div class="sub" style="margin-top:6px">外資（近${m.length}日）</div>${bars(m.map(x=>x.f))}<div class="sub">投信</div>${bars(m.map(x=>x.t))}<div class="sub">近5日合計：外資 <b class="${cls(m.slice(-5).reduce((a,x)=>a+x.f,0))}">${sgn(m.slice(-5).reduce((a,x)=>a+x.f,0),0)}</b> 投信 <b class="${cls(m.slice(-5).reduce((a,x)=>a+x.t,0))}">${sgn(m.slice(-5).reduce((a,x)=>a+x.t,0),0)}</b> 億</div></div>`;
  if(Fl.fut.length){const lf=Fl.fut[Fl.fut.length-1];const oi=Fl.fut.map(x=>x[1]);
    h+=`<div class="card"><div class="nm" style="font-weight:700">臺股期貨 法人未平倉淨口數</div><div class="sub">${lf[0]}　外資 <b class="${cls(lf[1])}">${i0(lf[1])}</b>・投信 <b class="${cls(lf[2])}">${i0(lf[2])}</b>・自營商 <b class="${cls(lf[3])}">${i0(lf[3])}</b> 口</div><div class="sub" style="margin-top:6px">外資淨未平倉（近${oi.length}日；負＝淨空）</div>${bars(oi)}`;
    const lo=Fl.opt[Fl.opt.length-1];if(lo)h+=`<div class="sub">臺指選擇權外資未平倉淨口數（${lo[0]}）：Call <b class="${cls(lo[1])}">${i0(lo[1])}</b>・Put <b class="${cls(lo[2])}">${i0(lo[2])}</b></div>`;
    h+=`</div>`}
  h+=`<div class="card"><div class="nm" style="font-weight:700">個股買賣超排行</div>`+pills('flk','',[['f','外資'],['t','投信']],s.k)+pills('flw','',[['1','1日'],['5','5日'],['20','20日']],String(s.w));
  const row=(r,i,buy)=>`<a class="tr" style="grid-template-columns:22px 1fr 70px 60px" href="#/k/${r[0]}"><span class="xs mut">${i+1}</span><span class="n">${r[0]} ${esc(r[1])}</span><b class="${buy?'up':'dn'}" style="text-align:right">${sgn(r[3],2)}億</b><span class="${cls(r[4])}" style="text-align:right">${q4(r[4])}</span></a>`;
  h+=`<div class="sub">買超前20（億元＝張數×收盤價；右欄＝近5日漲跌）</div>${Fl.stocks[s.k+s.w+'_buy'].map((r,i)=>row(r,i,1)).join('')}<div class="sub" style="margin-top:8px">賣超前20</div>${Fl.stocks[s.k+s.w+'_sell'].map((r,i)=>row(r,i,0)).join('')}</div>`;
  h+=NOTE('大盤三大法人金額＝證交所 BFI82U（上市）；期貨／選擇權＝臺灣期貨交易所公開統計（法人別未平倉）；個股買賣超＝證交所 T86／櫃買中心法人買賣超（外資＝外陸資＋外資自營商）。盤後資料。');
  return h;
}
function tHold(Hd){
  const s=X.S.hd;
  const M={big:['千張大戶占比最高',r=>-r[4]],up:['千張大戶本週增加',r=>-(r[6]==null?-99:r[6])],dn:['千張大戶本週減少',r=>(r[6]==null?99:r[6])],hl:['股東人數減少最多',r=>(r[8]==null?99:r[8])]};
  let h=`<div class="card"><div class="sub">集保週資料 ${Hd.week}${Hd.prev?'（對比 '+Hd.prev+'）':'（目前只累積到 '+Hd.weeks+' 週，週增減要等下週才有）'}</div></div>`;
  h+=pills('hdm','',Object.keys(M).map(k=>[k,M[k][0]]),s.mode);
  const L=Hd.rows.filter(r=>r[11]>=30&&(s.mode=='big'||r[6]!=null)).sort((a,b)=>M[s.mode][1](a)-M[s.mode][1](b));
  h+=L.slice(0,s.more).map(r=>`<a class="rcard" href="#/k/${r[0]}"><div class="rrow"><div><div class="nm" style="font-weight:700">${r[0]} ${esc(r[1])} <span class="chip fl">${r[2]?'櫃':'市'}</span></div><div class="sub">收 ${num(r[9],2)} · 5日 <span class="${cls(r[10])}">${q4(r[10])}</span></div></div><div style="text-align:right"><div class="big" style="font-size:22px">${num(r[4],1)}<small>%</small></div><div class="xs mut">千張大戶</div></div></div>
  <div class="stats"><div><span>400張以上</span><b>${num(r[3],1)}%</b></div><div><span>千張週增減</span><b class="${cls(r[6])}">${r[6]==null?'–':sgn(r[6],2)+'pp'}</b></div><div><span>股東人數</span><b>${i0(r[5]).replace('+','')}</b></div><div><span>人數週變</span><b class="${cls(r[8]==null?null:-r[8])}">${r[8]==null?'–':sgn(r[8],2)+'%'}</b></div></div></a>`).join('')||'<div class="card">尚無資料</div>';
  if(L.length>s.more)h+=`<button class="more" data-x="hdmore">再顯示更多（${L.length-s.more}）</button>`;
  h+=NOTE('資料＝臺灣集中保管結算所「集保戶股權分散表」（政府開放資料，每週公布）。千張大戶＝持股1,000張以上占集保庫存比例；400張以上＝級距12–15。只列近5日均成交≥3,000萬的股票以免雜訊。集保官方只提供最新一週，歷史由本站每週累積，所以「週增減」要累積兩週後才有。');
  return h;
}
async function tWatch(){
  const w=WL(),s=X.S;
  const [Sc,Pt,Rd,Hd]=await Promise.all([get('c_score'),get('c_pat').catch(()=>null),get('c_radar').catch(()=>null),get('c_hold').catch(()=>null)]);
  let h=`<div class="card"><div class="sub">自選清單只存在這支手機的瀏覽器裡（localStorage），不會上傳。</div></div><div style="display:flex;gap:8px"><input class="in" id="wlq" placeholder="輸入代號加入，例如 2330" inputmode="numeric" style="margin-bottom:0"><button class="more" style="width:92px;border-style:solid" data-x="wladd">加入</button></div><div style="height:8px"></div>`;
  if(!w.length)return h+'<div class="card">還沒有自選股。到「研究評分」按 ☆，或在上面輸入代號。</div>';
  h+=w.map(id=>{const r=Sc.rows.find(x=>x[0]==id);
    const pt=(Pt?Pt.hits:[]).filter(x=>x.sid==id),ev=Rd?Rd.items.find(x=>x.sid==id):null,hd=Hd?Hd.rows.find(x=>x[0]==id):null;
    return r?scCard(r,w)+(pt.length||ev||hd?`<div class="card note" style="margin-top:-4px">${pt.map(x=>`型態：${esc(x.pname)}（${esc(x.status)}・${x.score}分）`).join('；')}${ev?'<br>異動：'+ev.tags.map(t=>esc(t[0])).join('、'):''}${hd?`<br>千張大戶 ${num(hd[4],1)}%${hd[6]!=null?'（週 '+sgn(hd[6],2)+'pp）':''}`:''}</div>`:''):`<div class="rcard"><div class="rrow"><div>${esc(id)}（無資料）</div><button class="wl on" data-x="wl" data-v="${id}">★</button></div></div>`}).join('');
  return h;
}

/* ---------- 路由 ---------- */
async function render(){
  const h=location.hash||'#/',p=h.split('/');const app=document.getElementById('app');const mine=h;
  nav(h);
  app.innerHTML='<div class="card">載入中…</div>';
  try{
    let html='';
    if(p[1]=='rise')html=pageRise(await get('rise'));
    else if(p[1]=='rrg')html=pageRrg(await get('rrg'));
    else{
      const sub=p[2]||X.S.sub;X.S.sub=sub;
      html=subnav(sub);
      const d={today:()=>get('c_news').then(tToday),rank:()=>get('c_rank').then(tRank),heat:()=>get('c_heat').then(tHeat),pat:()=>get('c_pat').then(tPat),score:()=>get('c_score').then(tScore),radar:()=>get('c_radar').then(tRadar),flow:()=>get('c_flow').then(tFlow),hold:()=>get('c_hold').then(tHold),watch:tWatch}[sub];
      html+=d?await d():'<div class="card">找不到此功能</div>';
    }
    if(location.hash!==mine)return;
    const y=X.keep||0;X.keep=0;
    app.innerHTML=html;window.scrollTo(0,y);
    const t=document.getElementById('tail');if(t)t.oninput=e=>{X.S.tail=+e.target.value;document.getElementById('tailv').textContent=X.S.tail;document.getElementById('rrgbox').innerHTML=rrgSvg(X.C.rrg)};
  }catch(e){if(location.hash===mine)app.innerHTML=(p[1]=='tools'?subnav(p[2]||X.S.sub):'')+`<div class="card">這個分頁的資料目前沒有產生（${esc(e.message)}）：可能是歷史資料還不夠長，或當日抓取失敗。下次每日更新會再試。</div>`}
}
function redo(){X.keep=window.scrollY;render()}
document.addEventListener('click',e=>{
  const t=e.target.closest('[data-x]');if(!t)return;const k=t.dataset.x,v=t.dataset.v,S=X.S;
  if(k=='rtypeA'){S.type=v}else if(k=='rst'){S.st=v}else if(k=='rrt'){S.rtype=v;S.pick=null}
  else if(k=='pick'){S.pick=S.pick==v?null:v;const R=X.C.rrg;document.getElementById('rrgbox').innerHTML=rrgSvg(R);document.getElementById('pickbox').innerHTML=pickInfo(R);return}
  else if(k=='rkt'){S.rk=v}else if(k=='hmk'){S.hm.mk=v}else if(k=='hmode'){S.hm.mode=v}else if(k=='hind'){S.hm.ind=v||null}
  else if(k=='hst'){location.hash='#/k/'+v;return}
  else if(k=='ptp'){S.pt.p=v;S.pt.more=40}else if(k=='pts'){S.pt.s=v;S.pt.more=40}else if(k=='ptmore'){S.pt.more+=60}
  else if(k=='scr'){S.sc.r=v;S.sc.more=40}else if(k=='scm'){S.sc.mk=v;S.sc.more=40}else if(k=='scmore'){S.sc.more+=60}
  else if(k=='rd'){S.rd=v}else if(k=='flk'){S.fl.k=v}else if(k=='flw'){S.fl.w=+v}
  else if(k=='hdm'){S.hd.mode=v;S.hd.more=40}else if(k=='hdmore'){S.hd.more+=60}
  else if(k=='wl'){const w=WL(),i=w.indexOf(v);if(i<0)w.push(v);else w.splice(i,1);setWL(w)}
  else if(k=='wladd'){const q=(document.getElementById('wlq').value||'').trim();if(/^\d{4}$/.test(q)){const w=WL();if(!w.includes(q)){w.push(q);setWL(w)}}}
  else return;
  redo();
});
document.addEventListener('change',e=>{const t=e.target;if(t.dataset&&t.dataset.x=='hdate'){X.S.hm.date=t.value;redo()}});
document.addEventListener('input',e=>{const t=e.target;if(t.dataset&&t.dataset.x=='scq'){X.S.sc.q=t.value;X.S.sc.more=40;clearTimeout(X.tm);X.tm=setTimeout(()=>{const pos=t.selectionStart;render().then(()=>{const n=document.querySelector('[data-x=scq]');if(n){n.focus();try{n.setSelectionRange(pos,pos)}catch(_){}}})},350)}});
return{render,nav,mine:h=>/^#\/(rise|rrg|tools)/.test(h)};
})();
