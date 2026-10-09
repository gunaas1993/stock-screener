"""Self-contained HTML dashboard + CSV export."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import MAG7, OUTPUT_DIR, TOP_N, WEIGHTS

COLS = [
    "ticker", "name", "sector", "price", "target_avg", "upside", "n_analysts", "pe", "fwd_pe", "pe_vs_sector",
    "rev_growth", "eps_growth", "ret_12_1", "ret_3m", "rec_mean", "zacks", "smart_score",
    "q_rev_yoy", "q_rev_qoq", "surprise_last", "net_margin", "fcf_margin", "margin_chg", "beats_4",
    "s_momentum", "s_value", "s_growth", "s_upside", "s_quality", "s_consensus", "buy_score", "signal",
    "next_earnings", "score_rank", "chk", "chk_pass", "chk_total", "qdata", "list_rank",
]


def _records(df: pd.DataFrame) -> list[dict]:
    d = df.copy()
    for c in COLS:
        if c not in d:
            d[c] = np.nan
    out = []
    for rec in d[COLS].to_dict("records"):
        clean = {}
        for k, v in rec.items():
            if isinstance(v, (list, dict)):
                clean[k] = v
            elif isinstance(v, (pd.Timestamp, datetime)):
                clean[k] = None if pd.isna(v) else v.strftime("%Y-%m-%d")
            elif isinstance(v, (float, np.floating)):
                clean[k] = None if not np.isfinite(v) else round(float(v), 4)
            elif isinstance(v, np.integer):
                clean[k] = int(v)
            else:
                clean[k] = v
        out.append(clean)
    return out


def write_outputs(df: pd.DataFrame) -> tuple[str, str]:
    # Both lists default to "highest Buy Score first".
    mag = df[df["ticker"].isin(MAG7)].sort_values("buy_score", ascending=False).copy()
    top = df[df["in_top"]].sort_values("buy_score", ascending=False).copy()
    mag["list_rank"] = range(1, len(mag) + 1)
    top["list_rank"] = range(1, len(top) + 1)

    csv_cols = [c for c in COLS if c not in ("chk", "qdata")]
    csv_path = OUTPUT_DIR / "ranked.csv"
    pd.concat([mag.assign(section="MAG7"), top.assign(section="TOP")])[["section"] + [c for c in csv_cols if c in df.columns or c == "list_rank"]].to_csv(csv_path, index=False)

    s2 = df[df["stage2"] == True] if "stage2" in df else df.iloc[0:0]  # noqa: E712
    health = {
        "stage2": int(len(s2)),
        "zacks": int(s2["zacks"].notna().sum()) if "zacks" in s2 else 0,
        "finviz": int(s2["fv_target"].notna().sum()) if "fv_target" in s2 else 0,
        "yahoo_extras": int((s2["eps_rev"].notna() | s2["surprise_avg"].notna()).sum()) if "eps_rev" in s2 else 0,
        "quarterly": int(s2["qdata"].map(lambda x: isinstance(x, dict)).sum()) if "qdata" in s2 else 0,
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
:root{
  --bg:#f3f5fb;--card:#ffffff;--ink:#17203a;--mut:#6a7590;--line:#e5e9f4;--soft:#f7f9fe;
  --indigo:#4f46e5;--violet:#7c3aed;--teal:#0d9488;--green:#16a34a;--red:#dc2626;--amber:#d97706;--sky:#0284c7;
  --shadow:0 1px 2px rgba(23,32,58,.05),0 8px 24px rgba(23,32,58,.06);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
/* ---------- hero ---------- */
.hero{position:relative;overflow:hidden;color:#fff;padding:26px 0 74px;
  background:radial-gradient(1200px 400px at 85% -20%,rgba(45,212,191,.55),transparent 60%),
             radial-gradient(900px 380px at 5% 0%,rgba(236,72,153,.35),transparent 55%),
             linear-gradient(120deg,#3730a3 0%,#6d28d9 52%,#0f766e 100%)}
.hero .in{max-width:1900px;margin:0 auto;padding:0 24px}
.hero .top{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;flex-wrap:wrap}
.hero h1{margin:0;font-size:28px;letter-spacing:-.5px;font-weight:800}
.hero .tag{margin-top:6px;font-size:14px;opacity:.92;max-width:640px}
.hero .tag b{color:#fde68a}
#fresh{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);backdrop-filter:blur(6px);border-radius:14px;padding:10px 14px;text-align:right;min-width:290px}
#fresh .t{font-weight:700;font-size:13px}#fresh .h{font-size:11px;opacity:.9;margin-top:3px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:#4ade80;box-shadow:0 0 0 3px rgba(74,222,128,.3)}
.dot.warn{background:#facc15;box-shadow:0 0 0 3px rgba(250,204,21,.3)}.dot.bad{background:#f87171;box-shadow:0 0 0 3px rgba(248,113,113,.3)}
.kpis{display:flex;gap:12px;margin-top:20px;flex-wrap:wrap}
.kpi{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);border-radius:12px;padding:8px 14px;min-width:120px}
.kpi b{display:block;font-size:20px;font-weight:800}.kpi span{font-size:11px;opacity:.85;text-transform:uppercase;letter-spacing:.6px}
main{max-width:1900px;margin:-48px auto 0;padding:0 24px 60px;position:relative}
/* ---------- cards ---------- */
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:16px 18px;margin-bottom:18px}
.card h3{margin:0 0 4px;font-size:15px}
.legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin-top:10px}
.lg{display:flex;gap:10px;align-items:flex-start;background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:9px 11px}
.lg p{margin:0;color:var(--mut);font-size:12px}.lg b{display:block;color:var(--ink);font-size:12.5px}
.row{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end}
label{display:flex;flex-direction:column;gap:4px;color:var(--mut);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
input,select{background:#fff;color:var(--ink);border:1px solid #d5dbec;border-radius:9px;padding:8px 10px;width:120px;font:inherit}
button{background:linear-gradient(120deg,var(--indigo),var(--violet));color:#fff;border:0;border-radius:9px;padding:10px 18px;font-weight:700;cursor:pointer;box-shadow:0 4px 12px rgba(79,70,229,.3)}
button:hover{filter:brightness(1.08)}
.sec{display:flex;align-items:center;gap:12px;margin:26px 2px 10px}
.sec .bar{width:6px;height:34px;border-radius:4px;background:linear-gradient(var(--indigo),var(--teal))}
.sec h2{margin:0;font-size:18px;letter-spacing:-.2px}.sec p{margin:2px 0 0;color:var(--mut);font-size:12.5px}
.sec .cnt{margin-left:auto;background:#eef0ff;color:var(--indigo);font-weight:700;border-radius:20px;padding:4px 12px;font-size:12px}
/* ---------- tables ---------- */
.wrap{overflow:auto;border:1px solid var(--line);border-radius:16px;background:var(--card);box-shadow:var(--shadow);max-height:78vh}
table{border-collapse:separate;border-spacing:0;width:100%;white-space:nowrap}
th,td{padding:8px 11px;text-align:right;border-bottom:1px solid var(--line);background:#fff}
thead tr.g th{position:sticky;top:0;z-index:3;text-align:center;font-size:10.5px;letter-spacing:.8px;text-transform:uppercase;font-weight:800;color:#fff;border-bottom:0;padding:6px}
thead tr.c th{position:sticky;top:27px;z-index:3;background:#f5f7fd;color:var(--mut);font-weight:700;font-size:11.5px;cursor:pointer;user-select:none;border-bottom:1px solid #d9dff0}
thead tr.c th:hover{color:var(--indigo)} thead tr.c th.sorted{color:var(--indigo);background:#eceeff}
thead tr.c th.sorted::after{content:attr(data-dir);margin-left:4px}
.g0{background:#475569}.g1{background:#4f46e5}.g2{background:#7c3aed}.g3{background:#0d9488}.g4{background:#0284c7}.g5{background:#c2410c}.g6{background:#be185d}.g7{background:#64748b}
.l{text-align:left}
.stk{position:sticky;left:0;z-index:2;background:#fff;box-shadow:2px 0 0 var(--line);min-width:210px}
thead .stk{z-index:4}
tbody tr.m{cursor:pointer}tbody tr.m:hover td{background:#f4f6ff}tbody tr.m:hover td.stk{background:#f4f6ff}
.rk{display:inline-block;width:24px;height:24px;line-height:24px;text-align:center;border-radius:8px;background:#eef0ff;color:var(--indigo);font-weight:800;font-size:11px;margin-right:8px;vertical-align:top}
.tkc{display:inline-block;vertical-align:top}.tk{font-weight:800;font-size:14px;color:var(--ink)}.nm{display:block;color:var(--mut);font-size:11px;max-width:150px;overflow:hidden;text-overflow:ellipsis}
.pos{color:var(--green);font-weight:600}.neg{color:var(--red);font-weight:600}.mut{color:var(--mut)}
.pill{display:inline-block;min-width:46px;text-align:center;padding:4px 10px;border-radius:20px;font-weight:800;font-size:13px;border:1px solid}
.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-weight:800;font-size:10.5px;letter-spacing:.4px}
.s-STRONG{background:#dcfce7;color:#166534}.s-BUY{background:#ecfccb;color:#3f6212}.s-WATCH{background:#fef3c7;color:#92400e}.s-AVOID{background:#fee2e2;color:#991b1b}
.chk{display:inline-flex;gap:3px;vertical-align:middle}.chk i{width:17px;height:17px;border-radius:5px;font-style:normal;font-size:9.5px;font-weight:800;display:flex;align-items:center;justify-content:center}
.chk .y{background:#16a34a;color:#fff}.chk .n{background:#fee2e2;color:#b91c1c}.chk .u{background:#f1f5f9;color:#94a3b8;border:1px dashed #cbd5e1}
.chkn{font-weight:800;margin-left:7px;font-size:12px}
.mini{display:inline-block;width:58px;height:7px;background:#e9edf8;border-radius:4px;vertical-align:middle;overflow:hidden;margin-right:6px}.mini i{display:block;height:100%;border-radius:4px}
.sp{vertical-align:middle;margin-right:6px}
.beats{display:inline-flex;gap:2px;align-items:flex-end;height:16px;vertical-align:middle;margin-left:6px}.beats i{width:5px;border-radius:2px;display:block}
.zk{display:inline-block;width:22px;text-align:center;border-radius:6px;font-weight:800;padding:2px 0}.z1,.z2{background:#dcfce7;color:#166534}.z3{background:#f1f5f9;color:#475569}.z4,.z5{background:#fee2e2;color:#991b1b}
.vs{display:inline-block;padding:2px 8px;border-radius:20px;font-weight:700;font-size:11px}.vs.c{background:#dcfce7;color:#166534}.vs.f{background:#f1f5f9;color:#475569}.vs.r{background:#fee2e2;color:#991b1b}
tr.d td{background:linear-gradient(#f8f9ff,#fff);padding:14px 20px;text-align:left;white-space:normal}
.dt{border-collapse:collapse;width:auto;min-width:640px}.dt th,.dt td{padding:5px 14px;text-align:right;border-bottom:1px solid var(--line);background:transparent;position:static}
.dt th{color:var(--mut);font-size:11px;cursor:default;background:transparent}.dt td:first-child,.dt th:first-child{text-align:left;color:var(--mut);font-weight:700}
.dwrap{display:flex;gap:28px;flex-wrap:wrap;align-items:flex-start;position:sticky;left:18px;width:max-content;max-width:calc(100vw - 110px)}.dnote{max-width:340px;color:var(--mut);font-size:12px}
.note{color:var(--mut);font-size:12.5px;line-height:1.6}.note b{color:var(--ink)}
.w{display:inline-block;background:#eef0ff;color:var(--indigo);border-radius:6px;padding:1px 7px;font-weight:700;margin:0 2px}
</style></head><body>
<section class="hero"><div class="in">
  <div class="top">
    <div>
      <h1>S&amp;P 500 Opportunity Screener</h1>
      <div class="tag">Find stocks that are <b>cheap</b>, <b>growing</b>, <b>beating earnings</b> and <b>generating cash</b> &mdash; all folded into one Buy Score, refreshed every hour.</div>
    </div>
    <div id="fresh"></div>
  </div>
  <div class="kpis" id="kpis"></div>
</div></section>
<main>
<div class="card">
  <h3>The 5-point checklist <span class="mut" style="font-weight:400">&mdash; a stock that passes most of these is cheap <i>and</i> performing</span></h3>
  <div class="legend" id="legend"></div>
</div>

<div class="card"><h3>Where could my next money go?</h3>
<div class="row" style="margin-top:8px">
<label>Amount ($)<input id="amt" type="number" value="25000" step="1000"></label>
<label>Positions<input id="npos" type="number" value="8" min="1" max="25"></label>
<label>Max per stock (%)<input id="cap" type="number" value="20" min="5" max="100"></label>
<label>Include Mag 7<select id="incmag"><option>yes</option><option>no</option></select></label>
<button onclick="alloc()">Suggest split</button></div>
<div id="allocout"></div></div>

<div class="sec"><div class="bar"></div><div><h2>Magnificent 7</h2><p>Highest Buy Score first &middot; click any row for the quarter-by-quarter breakdown</p></div><div class="cnt" id="c1"></div></div>
<div class="wrap"><table id="t1"></table></div>

<div class="sec"><div class="bar"></div><div><h2>Top <span id="topn"></span> other S&amp;P 500 stocks</h2><p>Picked and ranked by Buy Score &middot; click any column to re-sort, any row to expand</p></div><div class="cnt" id="c2"></div></div>
<div class="wrap"><table id="t2"></table></div>

<div class="card" style="margin-top:22px"><h3>How the Buy Score works</h3><div class="note" id="method"></div></div>
</main>
<script>
const D = __DATA__;
const CHECKS = [
 ['P','Cheap vs sector','Forward P/E at or below the median of its sector (profitable companies only).'],
 ['R','Revenue growing','Latest quarter revenue up at least 10% vs the same quarter last year.'],
 ['E','EPS beat','Beat the analysts\u2019 EPS estimate by at least 2% in the latest report.'],
 ['C','Cash flow','Positive free-cash-flow margin and positive operating cash flow in 3 of the last 4 quarters. N/A for banks.'],
 ['M','Net margin','Net profit margin of at least 10% in the latest quarter.']];
const $ = id => document.getElementById(id);
const hue = v => Math.max(0,Math.min(1,(v-35)/45))*125;
const money = v => v==null?'–':(Math.abs(v)>=1e9?(v/1e9).toFixed(1)+'B':Math.abs(v)>=1e6?(v/1e6).toFixed(0)+'M':v.toFixed(0));
const usd = v => v==null?'–':'$'+v.toFixed(2);
const pct = (v,d=1) => v==null?'–':(v*100).toFixed(d)+'%';
const sgn = v => v==null?'':(v>0?'pos':v<0?'neg':'');
const spark = (vals,w=64,h=22) => {
  const p=vals.filter(x=>x!=null); if(p.length<2) return '<span class="mut">–</span>';
  const mn=Math.min(...p), mx=Math.max(...p), rg=(mx-mn)||1, n=vals.length;
  const pts=vals.map((x,i)=>x==null?null:[2+i*(w-4)/(n-1), h-3-(x-mn)/rg*(h-6)]).filter(Boolean);
  const up=p[p.length-1]>=p[0], c=up?'#16a34a':'#dc2626', l=pts[pts.length-1];
  return `<svg class="sp" width="${w}" height="${h}"><polyline fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" points="${pts.map(q=>q.join(',')).join(' ')}"/><circle cx="${l[0]}" cy="${l[1]}" r="2.6" fill="${c}"/></svg>`;
};
const revYoY = r => r.q_rev_yoy!=null ? r.q_rev_yoy : r.rev_growth;
const lastRev = r => r.qdata ? r.qdata.rev[r.qdata.rev.length-1] : null;
const isFin = r => r.sector==='Financials';

const COLS = [
 {h:'Stock', g:0, v:r=>r.ticker, k:'stock'},
 {h:'Price', g:1, v:r=>r.price, k:'usd'}, {h:'Avg target', g:1, v:r=>r.target_avg, k:'usd'}, {h:'Upside', g:1, v:r=>r.upside, k:'pctc'},
 {h:'BUY SCORE', g:2, v:r=>r.buy_score, k:'score'}, {h:'Signal', g:2, v:r=>r.signal, k:'sig'}, {h:'Checklist', g:2, v:r=>r.chk_pass, k:'chk'},
 {h:'Revenue, last 5 quarters', g:3, v:lastRev, k:'rev'}, {h:'Rev YoY', g:3, v:revYoY, k:'pctc'},
 {h:'Last EPS beat', g:3, v:r=>r.surprise_last, k:'beat'}, {h:'Net margin', g:3, v:r=>r.net_margin, k:'pctp'}, {h:'FCF margin', g:3, v:r=>r.fcf_margin, k:'fcf'},
 {h:'P/E', g:4, v:r=>r.pe, k:'num'}, {h:'Fwd P/E', g:4, v:r=>r.fwd_pe, k:'num'}, {h:'vs sector', g:4, v:r=>r.pe_vs_sector, k:'vs'},
 {h:'12-1m ret', g:5, v:r=>r.ret_12_1, k:'pctc'}, {h:'Zacks', g:5, v:r=>r.zacks, k:'zk'}, {h:'Analysts', g:5, v:r=>r.n_analysts, k:'int'}, {h:'Rating (1=best)', g:5, v:r=>r.rec_mean, k:'num'},
 {h:'Upside', g:6, v:r=>r.s_upside, k:'bar'}, {h:'Momentum', g:6, v:r=>r.s_momentum, k:'bar'}, {h:'Value', g:6, v:r=>r.s_value, k:'bar'},
 {h:'Growth', g:6, v:r=>r.s_growth, k:'bar'}, {h:'Quality', g:6, v:r=>r.s_quality, k:'bar'}, {h:'Consensus', g:6, v:r=>r.s_consensus, k:'bar'},
 {h:'Next earnings', g:7, v:r=>r.next_earnings, k:'txt'}
];
const GROUPS = ['Stock','Price & upside','Score','Quarterly performance','Valuation','Momentum & analysts','Score breakdown','Calendar'];

function cell(c, r, i){
  const v=c.v(r);
  switch(c.k){
   case 'stock': return `<td class="l stk"><span class="rk">${r.list_rank}</span><span class="tkc"><span class="tk">${r.ticker}</span><span class="nm" title="${r.name} · ${r.sector}">${r.name}</span></span></td>`;
   case 'usd': return `<td>${usd(v)}</td>`;
   case 'num': return `<td>${v==null?'–':v.toFixed(1)}</td>`;
   case 'int': return `<td>${v==null?'–':Math.round(v)}</td>`;
   case 'txt': return `<td class="mut">${v==null?'–':v}</td>`;
   case 'pctc': return `<td class="${sgn(v)}">${v==null?'–':(v>0?'+':'')+pct(v)}</td>`;
   case 'pctp': return `<td class="${v==null?'':v>=0.10?'pos':v<0?'neg':''}">${pct(v)}</td>`;
   case 'fcf': return isFin(r)?'<td class="mut" title="Cash flow is not meaningful for banks">n/a</td>':`<td class="${v==null?'':v>0.05?'pos':v<0?'neg':''}">${pct(v)}</td>`;
   case 'score': return v==null?'<td>–</td>':`<td><span class="pill" style="background:hsl(${hue(v)},75%,93%);color:hsl(${hue(v)},65%,26%);border-color:hsl(${hue(v)},60%,78%)">${v.toFixed(1)}</span></td>`;
   case 'sig': return `<td><span class="badge s-${(v||'').split(' ')[0]}">${v||'–'}</span></td>`;
   case 'chk': {
     const tot=r.chk_total, ok=r.chk_pass;
     const dots=(r.chk||[]).map((x,j)=>`<i class="${x==null?'u':x?'y':'n'}" title="${CHECKS[j][1]}: ${x==null?'n/a':x?'pass':'fail'} — ${CHECKS[j][2]}">${CHECKS[j][0]}</i>`).join('');
     return `<td><span class="chk">${dots}</span><span class="chkn" style="color:${ok>=4?'#16a34a':ok>=3?'#ca8a04':'#94a3b8'}">${ok}/${tot}</span></td>`;
   }
   case 'rev': return `<td>${r.qdata?spark(r.qdata.rev):''}<span class="mut">${r.qdata?'$'+money(lastRev(r)):'–'}</span></td>`;
   case 'beat': {
     if(v==null) return '<td class="mut">–</td>';
     const sur=r.qdata?r.qdata.sur.filter(x=>x!=null).slice(-4):[];
     const bars=sur.map(x=>`<i title="${x>0?'+':''}${x.toFixed(1)}%" style="height:${Math.max(4,Math.min(16,Math.abs(x)*1.1+4))}px;background:${x>=0?'#16a34a':'#dc2626'}"></i>`).join('');
     return `<td class="${sgn(v)}">${v>0?'+':''}${pct(v)}<span class="beats">${bars}</span></td>`;
   }
   case 'vs': {
     if(v==null) return '<td class="mut">–</td>';
     const c2=v<=-0.10?'c':v>=0.25?'r':'f', lab=v<=-0.10?'cheap':v>=0.25?'rich':'fair';
     return `<td><span class="vs ${c2}" title="Forward P/E vs the sector median">${v>0?'+':''}${(v*100).toFixed(0)}% · ${lab}</span></td>`;
   }
   case 'zk': return `<td>${v==null?'<span class="mut">–</span>':`<span class="zk z${Math.round(v)}">${Math.round(v)}</span>`}</td>`;
   case 'bar': return v==null?'<td class="mut">–</td>':`<td><span class="mini"><i style="width:${v}%;background:hsl(${hue(v)},65%,48%)"></i></span>${Math.round(v)}</td>`;
  }
  return `<td>${v??'–'}</td>`;
}

function detail(r){
  const q=r.qdata;
  if(!q) return '<tr class="d"><td colspan="99">No quarterly statements available for this stock.</td></tr>';
  const rev=q.rev, n=rev.length;
  const rows=[
   ['Revenue', q.rev.map(v=>v==null?'–':'$'+money(v))],
   ['Growth vs prior quarter', rev.map((v,i)=>i&&v!=null&&rev[i-1]?`<span class="${sgn(v/rev[i-1]-1)}">${pct(v/rev[i-1]-1)}</span>`:'–')],
   ['Net income', q.ni.map(v=>v==null?'–':'$'+money(v))],
   ['Net margin', q.ni.map((v,i)=>v==null||!rev[i]?'–':pct(v/rev[i]))],
   ['EPS reported', q.eps.map(v=>v==null?'–':v.toFixed(2))],
   ['EPS estimate', q.est.map(v=>v==null?'–':v.toFixed(2))],
   ['EPS surprise', q.sur.map(v=>v==null?'–':`<b class="${sgn(v)}">${v>0?'+':''}${v.toFixed(1)}%</b>`)],
   ['Operating cash flow', isFin(r)?q.ocf.map(()=>'n/a'):q.ocf.map(v=>v==null?'–':`<span class="${sgn(v)}">$${money(v)}</span>`)],
   ['Free cash flow', isFin(r)?q.fcf.map(()=>'n/a'):q.fcf.map(v=>v==null?'–':`<span class="${sgn(v)}">$${money(v)}</span>`)],
  ];
  const head='<tr><th></th>'+q.q.map(x=>`<th>${x}</th>`).join('')+'</tr>';
  const body=rows.map(([l,vals])=>`<tr><td>${l}</td>${vals.map(x=>`<td>${x}</td>`).join('')}</tr>`).join('');
  const beats=r.beats_4!=null?`Beat EPS estimates in <b>${r.beats_4}</b> of the last 4 reports. `:'';
  const note=`<div class="dnote"><b style="color:var(--ink)">${r.ticker} &middot; ${r.name}</b><br>${r.sector}<br><br>${beats}Forward P/E ${r.fwd_pe==null?'–':r.fwd_pe.toFixed(1)}`+
    `${r.pe_vs_sector==null?'':` (${r.pe_vs_sector>0?'+':''}${(r.pe_vs_sector*100).toFixed(0)}% vs sector)`}. Analysts see <b class="${sgn(r.upside)}">${r.upside==null?'–':(r.upside>0?'+':'')+pct(r.upside)}</b> upside to $${r.target_avg==null?'–':r.target_avg.toFixed(2)}.</div>`;
  return `<tr class="d"><td colspan="99"><div class="dwrap"><table class="dt"><thead>${head}</thead><tbody>${body}</tbody></table>${note}</div></td></tr>`;
}

const STATE = {};
function render(id, rows){
  const el=$(id), st=STATE[id]||(STATE[id]={col:4, dir:-1, open:new Set()});  // default: BUY SCORE, high -> low
  const col=COLS[st.col];
  const sorted=[...rows].sort((a,b)=>{const x=col.v(a),y=col.v(b); if(x==null&&y==null)return 0; if(x==null)return 1; if(y==null)return -1; return (x>y?1:x<y?-1:0)*st.dir});
  let spans=[]; COLS.forEach(c=>{ if(spans.length&&spans[spans.length-1][0]===c.g) spans[spans.length-1][1]++; else spans.push([c.g,1]); });
  const g='<tr class="g">'+spans.map(([gi,n])=>`<th class="g${gi}${gi===0?' stk':''}" colspan="${n}">${GROUPS[gi]}</th>`).join('')+'</tr>';
  const h='<tr class="c">'+COLS.map((c,i)=>`<th data-i="${i}" class="${i===0?'l stk':''} ${i===st.col?'sorted':''}" data-dir="${st.dir===-1?'▼':'▲'}">${c.h}</th>`).join('')+'</tr>';
  el.innerHTML=`<thead>${g}${h}</thead><tbody>`+sorted.map(r=>`<tr class="m" data-t="${r.ticker}">${COLS.map((c,i)=>cell(c,r,i)).join('')}</tr>${st.open.has(r.ticker)?detail(r):''}`).join('')+'</tbody>';
  el.querySelectorAll('thead tr.c th').forEach(th=>th.onclick=()=>{
    const i=+th.dataset.i; if(st.col===i) st.dir*=-1; else {st.col=i; st.dir=(COLS[i].k==='stock'||COLS[i].k==='txt')?1:-1;}
    render(id,rows);
  });
  el.querySelectorAll('tbody tr.m').forEach(tr=>tr.onclick=()=>{const t=tr.dataset.t; st.open.has(t)?st.open.delete(t):st.open.add(t); render(id,rows);});
}

function alloc(){
  const amt=+$('amt').value, n=+$('npos').value, cap=+$('cap').value/100;
  const pool=[...($('incmag').value==='yes'?D.mag7:[]),...D.top].filter(r=>r.buy_score!=null&&r.signal!=='AVOID'&&r.price)
    .sort((a,b)=>b.buy_score-a.buy_score).slice(0,n);
  if(!pool.length){$('allocout').innerHTML='<p class="mut">No eligible stocks.</p>';return}
  let w=pool.map(r=>Math.max(r.buy_score-40,1)); let fixed=new Set();
  for(let k=0;k<6;k++){
    const free=w.map((x,i)=>fixed.has(i)?0:x), fs=free.reduce((a,b)=>a+b,0), left=1-[...fixed].length*cap;
    w=w.map((x,i)=>fixed.has(i)?cap:(fs?x/fs*left:0));
    let again=false; w.forEach((x,i)=>{if(x>cap+1e-9&&!fixed.has(i)){fixed.add(i);again=true}}); if(!again)break;
  }
  const tot=w.reduce((a,b)=>a+b,0); w=w.map(x=>x/tot);
  $('allocout').innerHTML='<div class="wrap" style="margin-top:12px;max-height:none"><table><thead><tr class="c"><th class="l">Ticker</th><th>Weight</th><th>Dollars</th><th>Shares</th><th>Price</th><th>Upside</th><th>Checklist</th><th>Score</th></tr></thead><tbody>'+
   pool.map((r,i)=>`<tr><td class="l"><b>${r.ticker}</b> <span class="mut">${r.name}</span></td><td>${(w[i]*100).toFixed(1)}%</td><td>$${(w[i]*amt).toFixed(0)}</td><td>${Math.floor(w[i]*amt/r.price)}</td><td>${usd(r.price)}</td><td class="${sgn(r.upside)}">${pct(r.upside)}</td><td>${r.chk_pass}/${r.chk_total}</td><td><b>${r.buy_score.toFixed(1)}</b></td></tr>`).join('')+'</tbody></table></div>';
}

function fresh(){
  const g=new Date(D.generated), mins=Math.max(0,Math.round((Date.now()-g)/60000));
  const ago=mins<1?'just now':mins<60?mins+' min ago':mins<2880?Math.round(mins/60)+' h ago':Math.round(mins/1440)+' days ago';
  const cls=mins<=90?'':mins<=360?'warn':'bad';
  const h=D.health, s=h.stage2||0, pc=n=>s?Math.round(100*n/s)+'%':'–';
  $('fresh').innerHTML=`<div class="t"><span class="dot ${cls}"></span>Last refreshed ${g.toLocaleString([], {dateStyle:'medium', timeStyle:'short'})} &middot; ${ago}</div>`+
   `<div class="h">Data health &mdash; Yahoo ${pc(h.yahoo_extras)} &middot; Quarterly ${pc(h.quarterly)} &middot; Zacks ${pc(h.zacks)} &middot; Finviz ${pc(h.finviz)}${h.tipranks?` &middot; TipRanks ${pc(h.tipranks)}`:''}</div>`;
}

const all=[...D.mag7,...D.top];
const sb=all.filter(r=>r.signal==='STRONG BUY').length, best=all.filter(r=>r.chk_total>=4&&r.chk_pass===r.chk_total).length;
const avgUp=D.top.reduce((a,r)=>a+(r.upside||0),0)/Math.max(1,D.top.length);
$('kpis').innerHTML=[[D.universe,'stocks scanned'],[sb,'strong buys'],[best,'pass every check'],['+'+(avgUp*100).toFixed(0)+'%','avg analyst upside, top '+D.top_n]].map(([b,l])=>`<div class="kpi"><b>${b}</b><span>${l}</span></div>`).join('');
$('legend').innerHTML=CHECKS.map(c=>`<div class="lg"><span class="chk"><i class="y">${c[0]}</i></span><div><b>${c[1]}</b><p>${c[2]}</p></div></div>`).join('');
$('topn').textContent=D.top_n; $('c1').textContent=D.mag7.length+' stocks'; $('c2').textContent=D.top.length+' stocks';
$('method').innerHTML=`Each stock gets a <b>Buy Score from 0 to 100</b>, built from six parts: `+Object.entries(D.weights).map(([k,v])=>`<span class="w">${k} ${Math.round(v*100)}%</span>`).join('')+
 `<br><b>Upside</b> &ndash; average analyst target vs price, shrunk when few analysts cover the stock or they disagree, capped at +60%. `+
 `<b>Momentum</b> &ndash; 12-1 month, 6 and 3 month returns, strength vs the S&amp;P 500, trend vs the 200-day average. `+
 `<b>Value</b> &ndash; forward earnings yield, PEG and free-cash-flow yield, partly judged against the stock&rsquo;s own sector. `+
 `<b>Growth</b> &ndash; revenue and EPS growth plus sequential quarterly revenue momentum. `+
 `<b>Quality</b> &ndash; net margin, free-cash-flow margin, margin trend and how big the latest EPS beat was. `+
 `<b>Consensus</b> &ndash; analyst ratings, Zacks Rank, estimate revisions, upgrades and beat history.<br>`+
 `Scores are relative to the S&amp;P 500, not absolute, and are a research aid &mdash; not financial advice.`;
fresh(); setInterval(fresh,60000);
render('t1', D.mag7); render('t2', D.top);
setTimeout(()=>location.reload(), 15*60000);  // pick up each new hourly build while the tab stays open
</script></body></html>
"""
