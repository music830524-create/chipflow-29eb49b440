// Ported from wakin61043/tw-trading-dashboard (EquiLens-Nexus/lib/patterns.mjs)
// https://github.com/wakin61043/tw-trading-dashboard  — MIT License, Copyright (c) 2026 EquiLens contributors
// 修改：移除對原專案 engine/config/markets/i18n 的相依，改用下方的小型替代函式；detectPatterns 的型態辨識邏輯未更動。
// 授權全文見同資料夾 LICENSE。
const mean = a => a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
const clamp = (v, a = 0, b = 100) => Math.max(a, Math.min(b, v));
const round = (v, n = 1) => v == null || !Number.isFinite(v) ? null : Math.round(v * 10 ** n) / 10 ** n;
const TW_TICKS = [[10, .01], [50, .05], [100, .1], [500, .5], [1000, 1], [Infinity, 5]];
const tickSize = price => { for (const [lim, step] of TW_TICKS) if (price < lim) return step; return 5; };
const decimals = step => Math.max(0, Math.ceil(-Math.log10(step) - 1e-9));
function roundTick(value, up = true) {
  const step = tickSize(value), n = decimals(step);
  const v = (up ? Math.ceil(value / step - 1e-9) : Math.floor(value / step + 1e-9)) * step;
  return Math.round(v * 10 ** n) / 10 ** n;
}
const tr = s => s;

export const PATTERNS = [
  ['ihs','頭肩底','反轉型'],['double','雙底','反轉型'],['round','圓底','反轉型'],
  ['ascending','上升三角形','整理突破型'],['wedge','下降楔形','反轉型'],
  ['flag','旗形','延續型'],['pennant','旗竿三角形','延續型'],['cup','杯柄','延續型'],
  ['triple','三重底','反轉型'],['base','突破平台','整理突破型']
].map(([id,name,category])=>({id,name,category}));
export const EXCLUDED = ['金融','水泥','造紙','紡織','運動休閒','貿易百貨','油電燃氣','文化創意'];
const max = a=>Math.max(...a), min=a=>Math.min(...a);
const span = (p,a,b,key)=>p.slice(a,b+1).map(r=>r[key]);
function pivots(p,key,low=false) {
  const out=[];
  for(let i=3;i<p.length-3;i++){
    const v=p[i][key], neighbors=p.slice(i-3,i+4).map(x=>x[key]);
    if(v===(low?min(neighbors):max(neighbors)) && neighbors.some(x=>x!==v) && (!out.length||i-out.at(-1).i>=4))out.push({i,v});
  }
  return out;
}
function fit(points){const x=mean(points.map(p=>p.i)),y=mean(points.map(p=>p.v));const den=points.reduce((s,p)=>s+(p.i-x)**2,0);const slope=den?points.reduce((s,p)=>s+(p.i-x)*(p.v-y),0)/den:0;return {at:i=>y+slope*(i-x),slope,error:Math.sqrt(mean(points.map(p=>(p.v-y-slope*(p.i-x))**2)))};}
function slope(values){return fit(values.map((v,i)=>({i,v}))).slope;}
// 價格依市場跳動單位取整（up：無條件進位）
export function tickPrice(value,up=true){return roundTick(value,up);}

// A setup must finish before the signal bars. Every pivot is confirmed by three
// subsequent bars inside the same 90-session window; no future rows are consulted.
export function detectPatterns(p, raw, meta={}) {
  if(p.length!==90||raw.length!==90)return [];
  const closes=p.map(x=>x.close), last=p.at(-1), lows=pivots(p,'min',true), highs=pivots(p,'max');
  const atr=mean(p.slice(-14).map((r,j)=>{const prev=p[75+j].close;return max([r.max-r.min,Math.abs(r.max-prev),Math.abs(r.min-prev)]);}));
  if(!(atr>0))return [];
  const scale=raw.at(-1).close/last.close, candidates=[];
  const add=(id,start,end,resistance,support,height,quality,description,anchors=[],line=null,lowerLine=null)=>{
    if(p[end].close>(line?line(end):resistance)+atr*.15)return;
    if(!(resistance>support&&height>0)||start<0||end>=89||end-start<10)return;
    const threshold=resistance+atr*.15;
    const future=p.slice(end+1);
    if(future.some(r=>r.close<support-atr*.25))return;
    if(last.close<resistance-atr*2.5||last.close>resistance+atr*4)return;
    const cross=p.findIndex((r,i)=>i>end&&r.close>(line?line(i):resistance)+atr*.15);
    if(cross>=0 && p.slice(cross).some((r,j)=>r.close<(line?line(cross+j):resistance)-atr*.35))return;
    const baseVol=mean(raw.slice(Math.max(0,(cross>=0?cross:89)-20),cross>=0?cross:89).map(r=>r.Trading_Volume));
    const ratio=baseVol>0?raw[cross>=0?cross:89].Trading_Volume/baseVol:0;
    const confirmed=cross>=0&&cross<89&&ratio>=1.3&&last.close>threshold;
    const pendingNext=cross===89&&ratio>=1.3&&last.close>threshold;
    const status=confirmed?'量價確認':pendingNext?'突破待次日確認':cross>=0?'突破待量確認':'接近突破';
    const volumePoints=clamp((ratio-.5)/1.5*20,0,20), trendPoints=last.close>mean(closes.slice(-20))?10:0;
    const score=Math.round(clamp(quality,0,40)+(confirmed?30:cross>=0?18:8)+volumePoints+trendPoints);
    const entry=tickPrice((resistance+atr*.2)*scale), entryMax=tickPrice((resistance+atr*.75)*scale);
    const stop=tickPrice((support-atr*.25)*scale,false), target=tickPrice((resistance+height)*scale,false);
    const costs=entryMax*.006, rr=(target-entryMax-costs)/(entryMax-stop+costs);
    const chased=raw.at(-1).close>entryMax;
    const kind=PATTERNS.find(x=>x.id===id);
    candidates.push({...kind,score,status,start:p[start].date,end:p[end].date,breakoutDate:cross<0?null:p[cross].date,
      description,anchors:anchors.map(a=>({date:p[a.i].date,label:a.label,price:round(a.v*scale,2),index:a.i})),
      resistance:round(resistance*scale,2),support:round(support*scale,2),atr:round(atr*scale,2),volumeRatio:round(ratio,2),
      scoreParts:{geometry:round(quality),confirmation:confirmed?30:cross>=0?18:8,volume:round(volumePoints),trend:trendPoints},
      lines:[{label:'壓力／頸線',from:start,to:89,a:(line?line(start):resistance)*scale,b:resistance*scale},{label:lowerLine?'支撐趨勢線':'結構支撐',from:start,to:89,a:(lowerLine?lowerLine(start):support)*scale,b:support*scale}],
      plan:{entry,entryMax,stop,target,rr:round(rr,2),riskPercent:round((entryMax-stop)/entryMax*100,2),chased,
        action:chased?'已超過進場帶，等待回測':pendingNext?'等待次日守穩頸線':!confirmed?'等待收盤突破與量能確認':rr<1.5?'報酬風險比不足，暫不進場':'量價已確認，仍需事件檢查',
        confirmation:`收盤高於 ${round(threshold*scale,2)}，突破日成交量至少為前 20 日均量 1.3 倍；次日須守住頸線。`,
        defense:`收盤跌回頸線下方 0.35 ATR 視為假突破；結構防守 ${stop} 為支撐下方 0.25 ATR。跳空可能超過預設損失。`,
        timing:'確認後先觀察首筆條件；回測不破再評估第二筆，總風險不增加。進場後 10 個交易日未延伸則重新評估，20 日仍盤整退出此計畫。',
        targetBasis:'頸線加型態高度的量度觀察位，非合理價或報酬保證；先核對前高賣壓，再考慮分段減碼。',
        missing:'尚未核對法說、財報、除權息及重大事件；上述是條件式技術計畫。未提供帳戶風險額度，因此不推算適合張數。'},
      warnings:[ratio<1.3?'突破量未達 1.3 倍，存在假突破風險':'量能確認不保證延續',chased?'價格已離開進場帶，不追價':'進場需等條件成立',id==='round'?'90 日只能辨識局部圓弧，不代表數月以上完整長底':'型態由數值規則辨識，請覆核圖形', '大盤趨勢、重大事件與缺口可能使型態失效'],...meta});
  };
  for(const end of [84,86,88]) {
    const ls=lows.filter(x=>x.i>=8&&x.i<=end-3), hs=highs.filter(x=>x.i<=end-3);
    for(const count of [2,3]) for(let j=0;j<=ls.length-count;j++){
      const pts=ls.slice(j,j+count),first=pts[0],lastLow=pts.at(-1);
      if(pts.some((x,k)=>k&&x.i-pts[k-1].i<10)||lastLow.i-first.i<15||end-lastLow.i>20)continue;
      const necks=pts.slice(1).map((x,k)=>max(span(p,pts[k].i,x.i,'max'))),neck=mean(necks);
      const depth=neck-min(pts.map(x=>x.v)),similar=(max(pts.map(x=>x.v))-min(pts.map(x=>x.v)))/neck;
      const prior=max(span(p,Math.max(0,first.i-15),first.i,'close'));
      if(depth<atr*2||depth/neck>.45||prior<first.v*1.04||necks.some(x=>x-min(pts.map(y=>y.v))<atr*2))continue;
      if(similar<=.035&&Math.abs(necks[0]-necks.at(-1))/neck<.04){add(count===2?'double':'triple',first.i-5,end,neck,min(pts.map(x=>x.v)),depth,40-similar*200,
        `${count} 個相隔至少 10 日的低點差距 ${round(similar*100,1)}%；中間反彈形成頸線，底部深度 ${round(depth/neck*100,1)}%。`,pts.map((x,k)=>({...x,label:`底 ${k+1}`})));}
      if(count===3){const [a,b,c]=pts,shoulder=Math.abs(a.v-c.v)/neck,head=(Math.min(a.v,c.v)-b.v)/neck;
        if(shoulder<.045&&head>.025&&head<.22&&Math.abs((b.i-a.i)-(c.i-b.i))<20&&Math.abs(necks[0]-necks[1])/neck<.05)
          add('ihs',a.i-5,end,neck,c.v,neck-b.v,38-shoulder*100,'左肩、較低的頭部及右肩依序形成；兩次反彈高點近似頸線，右肩低點作為結構防守。',pts.map((x,k)=>({...x,label:['左肩','頭','右肩'][k]})));
      }
    }
    for(const length of [20,30,45,60,80]){
      const start=end-length+1;if(start<0)continue;
      const hp=hs.filter(x=>x.i>=start),lp=ls.filter(x=>x.i>=start);
      if(hp.length>=2&&lp.length>=2&&hp.at(-1).i-hp[0].i>=length*.4&&lp.at(-1).i-lp[0].i>=length*.4){
        const upper=fit(hp),lower=fit(lp),u=upper.at(89),l=lower.at(89),width=upper.at(start)-lower.at(start),ending=upper.at(end)-lower.at(end),n=mean(span(p,start,end,'close'));
        const us=upper.slope*length/n,lslope=lower.slope*length/n;
        const contained=p.slice(start,end+1).filter((r,k)=>r.close<=upper.at(start+k)+atr*.5&&r.close>=lower.at(start+k)-atr*.5).length/length;
        if(width>atr*2&&ending>atr*.7&&u>l&&contained>=.85&&upper.error<atr&&lower.error<atr){
          const anchors=[...hp.map(x=>({...x,label:'壓力觸點'})),...lp.map(x=>({...x,label:'支撐觸點'}))];
          const common=`${length} 日整理，上緣變化 ${round(us*100,1)}%、下緣變化 ${round(lslope*100,1)}%；${Math.round(contained*100)}% 收盤落在通道內。`;
          if(Math.abs(us)<.025&&lslope>.03&&ending/width<.8)add('ascending',start,end,u,l,width,36,common+'水平壓力與抬高低點構成上升三角形。',anchors,upper.at,lower.at);
          if(us<-.035&&lslope<-.008&&upper.slope<lower.slope&&ending/width<.8)add('wedge',start,end,u,l,width,35,common+'上下緣均下移，上緣下降較快，通道收斂。',anchors,upper.at,lower.at);
          const poleStart=Math.max(0,start-15),pole=p[start].close-p[poleStart].close,poleReturn=pole/p[poleStart].close;
          if(length<=30&&start>=12&&poleReturn>=.12&&pole>atr*4&&(max(span(p,start,end,'max'))-min(span(p,start,end,'min')))<pole*.65){
            if(us<-.008&&lslope<0&&Math.abs(us-lslope)<.035&&ending/width>.65)add('flag',start,end,u,l,pole,37,common+`前段旗竿上漲 ${round(poleReturn*100,1)}%，回撤小於旗竿 65%，近似平行下降整理。`,anchors,upper.at,lower.at);
            if(us<-.01&&lslope>.01&&ending/width<.75)add('pennant',start,end,u,l,pole,37,common+`前段旗竿上漲 ${round(poleReturn*100,1)}%，上下緣向內收斂。`,anchors,upper.at,lower.at);
          }
          if(length>=30&&Math.abs(us)<.025&&Math.abs(lslope)<.025&&width/n<.18)add('base',start,end,u,l,width,34,common+'上下緣近似水平，至少 30 日箱型整理。',anchors,upper.at,lower.at);
        }
      }
      if(length>=45){
        // Five segment means enforce a broad bowl instead of a one-day V reversal.
        const segment=Math.floor(length/5),means=Array.from({length:5},(_,k)=>mean(span(p,start+k*segment,k===4?end:start+(k+1)*segment-1,'close')));
        const bottom=min(span(p,start,end,'min')),bottomIndex=p.findIndex((r,i)=>i>=start&&i<=end&&r.min===bottom);
        const rim=Math.max(means[0],means[4]),depth=rim-bottom;
        const bowl=means[0]>means[1]&&means[1]>means[2]&&means[2]<means[3]&&means[3]<means[4]&&Math.abs(means[0]-means[4])/rim<.07&&depth/rim>=.07&&depth/rim<=.4&&bottomIndex>=start+length*.25&&bottomIndex<=start+length*.7;
        if(bowl&&slope(span(p,start,start+segment,'close'))<0&&slope(span(p,end-segment,end,'close'))>0){
          const resistance=max([...span(p,start,start+segment,'max'),...span(p,end-segment,end,'max')]);
          add('round',start,end,resistance,min(span(p,end-segment,end,'min')),resistance-bottom,35,`${length} 日分成五段，均價先降後升；底部位於區間中段，深度 ${round(depth/rim*100,1)}%，排除短促 V 形。`,[{i:bottomIndex,v:bottom,label:'圓弧底'}]);
        }
      }
    }
    // Cup ends before a separate 5–15-session shallow handle.
    for(const handle of [7,12])for(const cupLength of [45,60]){
      const rimIndex=end-handle,start=rimIndex-cupLength;if(start<0)continue;
      const rim=mean([p[start].close,p[rimIndex].close]),bottom=min(span(p,start,rimIndex,'min')),depth=rim-bottom;
      const q=Math.floor(cupLength/4),means=Array.from({length:4},(_,k)=>mean(span(p,start+k*q,start+(k+1)*q-1,'close')));
      const handleLow=min(span(p,rimIndex+1,end,'min')),handleHigh=max(span(p,rimIndex+1,end,'max'));
      if(Math.abs(p[start].close-p[rimIndex].close)/rim<.06&&depth/rim>.08&&depth/rim<.4&&means[0]>means[1]&&means[3]>means[2]&&Math.abs(means[1]-means[2])<depth*.4&&handleLow>bottom+depth*.5&&rim-handleLow>atr*.4&&rim-handleLow<depth*.45&&handleHigh<rim*1.04&&slope(span(p,rimIndex+1,end,'close'))<0)
        add('cup',start,end,handleHigh,handleLow,depth,38,`${cupLength} 日杯身兩端價差小於 6%；其後 ${handle} 日把手回檔不超過杯深 45%，且位於杯身上半部。`,[{i:start,v:p[start].close,label:'左杯緣'},{i:rimIndex,v:p[rimIndex].close,label:'右杯緣'},{i:end,v:handleLow,label:'把手支撐'}]);
    }
  }
  return PATTERNS.flatMap(k=>{const list=candidates.filter(x=>x.id===k.id).sort((a,b)=>b.score-a.score||b.start.localeCompare(a.start));return list.length?[list[0]]:[];}).sort((a,b)=>b.score-a.score);
}

