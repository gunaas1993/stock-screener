"""Self-contained HTML dashboard + CSV export."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import MAG7, OUTPUT_DIR, TOP_N, WEIGHTS

COLS = [
    "ticker", "name", "sector", "price", "target_avg", "upside", "n_analysts", "pe", "fwd_pe", "eps", "fwd_eps",
    "rev_growth", "eps_growth", "ret_12_1", "ret_3m", "rec_mean", "zacks", "smart_score", "beat_rate",
    "s_momentum", "s_value", "s_growth", "s_upside", "s_consensus", "buy_score", "signal", "next_earnings", "score_rank",
]


def _records(df: pd.DataFrame) -> list[dict]:
    d = df.copy()
    for c in COLS:
        if c not in d:
            d[c] = np.nan
    d = d[COLS]
    out = []
    for rec in d.to_dict("records"):
        clean = {}
        for k, v in rec.items():
            if isinstance(v, (pd.Timestamp, datetime)):
                clean[k] = None if pd.isna(v) else v.strftime("%Y-%m-%d")
            elif isinstance(v, (float, np.floating)):
                clean[k] = None if not np.isfinite(v) else round(float(v), 4)
            elif isinstance(v, (np.integer,)):
                clean[k] = int(v)
            else:
                clean[k] = v
        out.append(clean)
    return out


def write_outputs(df: pd.DataFrame) -> tuple[str, str]:
    mag = df[df["ticker"].isin(MAG7)].sort_values("upside", ascending=False)
    top = df[df["in_top"]].sort_values("upside", ascending=False)

    csv_path = OUTPUT_DIR / "ranked.csv"
    pd.concat([mag.assign(section="MAG7"), top.assign(section="TOP")])[[c for c in ["section"] + COLS if c in df.columns or c == "section"]].to_csv(csv_path, index=False)

    s2 = df[df.get("stage2", False) == True] if "stage2" in df else df.iloc[0:0]  # noqa: E712
    health = {
        "stage2": int(len(s2)),
        "zacks": int(s2["zacks"].notna().sum()) if "zacks" in s2 else 0,
        "finviz": int(s2["fv_target"].notna().sum()) if "fv_target" in s2 else 0,
        "yahoo_extras": int((s2["eps_rev"].notna() | s2["surprise_avg"].notna()).sum()) if "eps_rev" in s2 else 0,
        "tipranks": int(s2["smart_score"].notna().sum()) if "smart_score" in s2 else 0,
    }
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "health": health,
        "top_n": TOP_N,
        "weights": WEIGHTS,
        "mag7": _records(mag),
        "top": _records(top),
        "universe": int(len(df)),
    }
    html = _TEMPLATE.replace("__DATA__", json.dumps(payload))
    html_path = OUTPUT_DIR / "report.html"
    html_path.write_text(html, encoding="utf-8")
    return str(html_path), str(csv_path)


_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>S&amp;P 500 Opportunity Screener</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#0e1116;--card:#161b22;--line:#262d38;--txt:#e6edf3;--mut:#8b96a5;--g:#2ea043;--r:#f85149;--y:#d29922;--b:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:13px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:18px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:flex-start;gap:20px}h1{margin:0 0 4px;font-size:20px}
#fresh{text-align:right;white-space:nowrap}#fresh .t{font-weight:700}#fresh .ok{color:var(--g)}#fresh .warn{color:var(--y)}#fresh .bad{color:var(--r)}#fresh .h{color:var(--mut);font-size:11px;margin-top:2px}
.sub{color:var(--mut)} main{padding:16px 24px 60px}
h2{font-size:15px;margin:26px 0 8px}h2 small{color:var(--mut);font-weight:400}
.wrap{overflow:auto;border:1px solid var(--line);border-radius:8px;background:var(--card)}
table{border-collapse:collapse;width:100%;white-space:nowrap}
th,td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--line)}
th{position:sticky;top:0;background:#1c232d;cursor:pointer;color:var(--mut);font-weight:600;user-select:none}
th:hover{color:var(--txt)} th.sorted::after{content:attr(data-dir);color:var(--b)}
td.l,th.l{text-align:left} tr:hover td{background:#1a212b}
.tk{font-weight:700;color:var(--b)} .pos{color:var(--g)} .neg{color:var(--r)} .mut{color:var(--mut)}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-weight:700;font-size:11px}
.s-STRONG{background:#12361d;color:#56d364}.s-BUY{background:#17301f;color:#3fb950}.s-WATCH{background:#3a2f0b;color:#e3b341}.s-AVOID{background:#3b1517;color:#ff7b72}
.bar{display:inline-block;width:54px;height:8px;background:#232b36;border-radius:4px;vertical-align:middle;overflow:hidden}
.bar i{display:block;height:100%;background:var(--b)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin-top:14px}
.row{display:flex;gap:14px;flex-wrap:wrap;align-items:end}label{display:flex;flex-direction:column;gap:3px;color:var(--mut);font-size:11px}
input{background:#0e1116;color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:6px 8px;width:110px}
button{background:var(--b);color:#04121f;border:0;border-radius:6px;padding:8px 14px;font-weight:700;cursor:pointer}
.note{color:var(--mut);font-size:12px;margin-top:10px;max-width:980px}
</style></head><body>
<header><div><h1>S&amp;P 500 Opportunity Screener</h1>
<div class="sub" id="meta"></div></div>
<div id="fresh"></div></header>
<main>
<div class="card"><b>Where could my next money go?</b>
<div class="row" style="margin-top:8px">
<label>Amount ($)<input id="amt" type="number" value="25000" step="1000"></label>
<label>Positions<input id="npos" type="number" value="8" min="1" max="25"></label>
<label>Max per stock (%)<input id="cap" type="number" value="20" min="5" max="100"></label>
<label>Include Mag 7<select id="incmag" style="background:#0e1116;color:#e6edf3;border:1px solid #262d38;border-radius:6px;padding:6px"><option>yes</option><option>no</option></select></label>
<button onclick="alloc()">Suggest split</button></div>
<div id="allocout"></div></div>

<h2>1 &middot; Magnificent 7 <small>sorted by analyst upside</small></h2>
<div class="wrap"><table id="t1"></table></div>
<h2>2 &middot; Best <span id="topn"></span> other S&amp;P 500 stocks <small>chosen by Buy Score, displayed by analyst upside</small></h2>
<div class="wrap"><table id="t2"></table></div>
<div class="note" id="method"></div>
</main>
<script>
const D = __DATA__;
const fmt = {
 usd:v=>v==null?'–':'$'+v.toFixed(2), pct:v=>v==null?'–':(v*100).toFixed(1)+'%', num:v=>v==null?'–':v.toFixed(1),
 int:v=>v==null?'–':Math.round(v), txt:v=>v==null?'–':v
};
const colorPct = v => v==null?'':(v>0?'pos':'neg');
const bar = v => v==null?'<span class="mut">–</span>':`<span class="bar"><i style="width:${v}%"></i></span> ${Math.round(v)}`;
const COLS = [
 ['#', r=>r._i, 'int', 'l'],
 ['Ticker', r=>r.ticker, 'tk', 'l'], ['Company', r=>r.name, 'txt', 'l'],
 ['Price', r=>r.price, 'usd'], ['Avg Target', r=>r.target_avg, 'usd'], ['Upside', r=>r.upside, 'pct', '', true],
 ['BUY SCORE', r=>r.buy_score, 'score'], ['Signal', r=>r.signal, 'sig'],
 ['Analysts', r=>r.n_analysts, 'int'], ['P/E', r=>r.pe, 'num'], ['Fwd P/E', r=>r.fwd_pe, 'num'],
 ['Rev growth', r=>r.rev_growth, 'pct', '', true], ['EPS growth', r=>r.eps_growth, 'pct', '', true],
 ['12-1m ret', r=>r.ret_12_1, 'pct', '', true], ['3m ret', r=>r.ret_3m, 'pct', '', true],
 ['Rating (1=best)', r=>r.rec_mean, 'num'], ['Zacks', r=>r.zacks, 'int'], ['TipRanks', r=>r.smart_score, 'int'],
 ['Momentum', r=>r.s_momentum, 'bar'], ['Value', r=>r.s_value, 'bar'], ['Growth', r=>r.s_growth, 'bar'], ['Consensus', r=>r.s_consensus, 'bar'],
 ['Sector', r=>r.sector, 'txt', 'l'], ['Next earnings', r=>r.next_earnings, 'txt']
];
function cell(c, r){
  const v = c[1](r), t = c[2];
  let h;
  if(t==='tk') h=`<span class="tk">${v}</span>`;
  else if(t==='bar') h=bar(v);
  else if(t==='score') h=`<b>${v==null?'–':v.toFixed(1)}</b>`;
  else if(t==='sig') h=`<span class="badge s-${(v||'').split(' ')[0]}">${v||'–'}</span>`;
  else h=fmt[t](v);
  const cls=[c[3]==='l'?'l':'', c[4]?colorPct(v):''].join(' ');
  return `<td class="${cls}">${h}</td>`;
}
function render(id, rows){
  const el=document.getElementById(id); el._rows=rows;
  rows.forEach((r,i)=>r._i=i+1);
  el.innerHTML = '<thead><tr>'+COLS.map((c,i)=>`<th data-i="${i}" class="${c[3]==='l'?'l':''}">${c[0]}</th>`).join('')+'</tr></thead><tbody>'+
    rows.map(r=>'<tr>'+COLS.map(c=>cell(c,r)).join('')+'</tr>').join('')+'</tbody>';
  el.querySelectorAll('th').forEach(th=>th.onclick=()=>{
    const i=+th.dataset.i, c=COLS[i], dir=th.dataset.dir==='▼'?1:-1;
    const s=[...el._rows].sort((a,b)=>{const x=c[1](a),y=c[1](b); if(x==null)return 1; if(y==null)return -1; return (x>y?1:x<y?-1:0)*dir});
    render(id,s);
    const nt=el.querySelectorAll('th')[i]; nt.classList.add('sorted'); nt.dataset.dir=dir===1?'▲':'▼';
  });
}
function alloc(){
  const amt=+document.getElementById('amt').value, n=+document.getElementById('npos').value, cap=+document.getElementById('cap').value/100;
  const pool=[...(document.getElementById('incmag').value==='yes'?D.mag7:[]),...D.top].filter(r=>r.buy_score!=null&&r.signal!=='AVOID'&&r.price)
    .sort((a,b)=>b.buy_score-a.buy_score).slice(0,n);
  if(!pool.length){document.getElementById('allocout').innerHTML='<p class="mut">No eligible stocks.</p>';return}
  let w=pool.map(r=>Math.max(r.buy_score-40,1)); let fixed=new Set();
  for(let k=0;k<6;k++){ // proportional to score, capped, excess redistributed
    const free=w.map((x,i)=>fixed.has(i)?0:x), fs=free.reduce((a,b)=>a+b,0), left=1-[...fixed].length*cap;
    w=w.map((x,i)=>fixed.has(i)?cap:(fs?x/fs*left:0));
    let again=false; w.forEach((x,i)=>{if(x>cap+1e-9&&!fixed.has(i)){fixed.add(i);again=true}}); if(!again)break;
  }
  const tot=w.reduce((a,b)=>a+b,0); w=w.map(x=>x/tot);
  document.getElementById('allocout').innerHTML='<table style="margin-top:10px"><thead><tr><th class="l">Ticker</th><th>Weight</th><th>Dollars</th><th>Shares</th><th>Price</th><th>Upside</th><th>Score</th></tr></thead><tbody>'+
   pool.map((r,i)=>`<tr><td class="l tk">${r.ticker}</td><td>${(w[i]*100).toFixed(1)}%</td><td>$${(w[i]*amt).toFixed(0)}</td><td>${Math.floor(w[i]*amt/r.price)}</td><td>${fmt.usd(r.price)}</td><td class="${colorPct(r.upside)}">${fmt.pct(r.upside)}</td><td>${r.buy_score.toFixed(1)}</td></tr>`).join('')+'</tbody></table>';
}
document.getElementById('meta').textContent=`${D.universe} S&P 500 stocks scanned · Yahoo Finance + Zacks + Finviz (+TipRanks via Perplexity if configured)`;
function fresh(){
  const g=new Date(D.generated), mins=Math.max(0,Math.round((Date.now()-g)/60000));
  const ago=mins<1?'just now':mins<60?mins+' min ago':mins<2880?Math.round(mins/60)+' h ago':Math.round(mins/1440)+' days ago';
  const cls=mins<=90?'ok':mins<=360?'warn':'bad';
  const h=D.health, s=h.stage2||0, pc=n=>s?Math.round(100*n/s)+'%':'–';
  const tip=h.tipranks?` · TipRanks ${pc(h.tipranks)}`:'';
  document.getElementById('fresh').innerHTML=`<div class="t">Last refreshed: <span class="${cls}">${g.toLocaleString([], {dateStyle:'medium', timeStyle:'short'})}</span></div>`+
   `<div class="h"><span class="${cls}">${ago}</span> · data health: Yahoo ${pc(h.yahoo_extras)} · Zacks ${pc(h.zacks)} · Finviz ${pc(h.finviz)}${tip}</div>`;
}
fresh(); setInterval(fresh,60000);
setTimeout(()=>location.reload(), 15*60000); // pick up each new hourly build while the tab is open
document.getElementById('topn').textContent=D.top_n;
document.getElementById('method').innerHTML=`<b>How the Buy Score works (0-100):</b> `+Object.entries(D.weights).map(([k,v])=>`${k} ${Math.round(v*100)}%`).join(' · ')+
 `. <i>Upside</i> = average analyst target vs price, shrunk when few analysts cover it or they disagree, capped at +60%. <i>Momentum</i> = 12-1m / 6m / 3m returns, strength vs S&amp;P, trend vs 200-day average. `+
 `<i>Value</i> = forward earnings yield, PEG, FCF yield (vs sector). <i>Growth</i> = revenue &amp; EPS growth. <i>Consensus</i> = ratings, Zacks Rank, estimate revisions, upgrades, earnings beats. `+
 `Scores are relative to the S&amp;P 500, not absolute. This is a research tool, not financial advice.`;
render('t1', D.mag7); render('t2', D.top);
</script></body></html>
"""
