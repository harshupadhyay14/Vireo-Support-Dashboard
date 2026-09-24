"""python run.py [--data data] [--out out]  ->  out/dashboard.html + CSVs. No API calls, no network."""
import argparse, html, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from vireo import *

ap = argparse.ArgumentParser(); ap.add_argument("--data", default="data"); ap.add_argument("--out", default="out")
args = ap.parse_args(); os.makedirs(args.out, exist_ok=True)

t, o, a, p = load(args.data)
t, log = clean(t, o, a)
alerts = lot_alerts(t)
t, base_rate, mon = money(t, p, alerts)
ag, cov = scorecard(t)
ag = ag.sort_values("raw_csat").reset_index(drop=True)
ag["raw_rank"] = ag.raw_csat.rank().astype(int)
ag.to_csv(f"{args.out}/agent_scorecard.csv", index=False)
alerts.to_csv(f"{args.out}/lot_alerts.csv", index=False)
mon.to_csv(f"{args.out}/defect_lot_cost_by_quarter.csv", index=False)

# monthly CSAT: all vs excluding flagged lots
t["month"] = t.created_at.dt.to_period("M").astype(str)
m_all = t.groupby("month").csat.mean()
m_ex = t[~t.badlot].groupby("month").csat.mean()
m_rep = t.groupby("month").repl.mean()
q1 = t[(t.created_at >= "2026-01-01") & (t.created_at < "2026-04-01")]
headline = dict(
    csat_q1_all=round(q1.csat.mean(), 2), csat_q1_excl_flagged=round(q1[~q1.badlot].csat.mean(), 2),
    csat_flagged_lots=round(t[t.badlot].csat.mean(), 2), repl_rate_flagged=round(t[t.badlot].repl.mean(), 3),
    repl_rate_baseline=round(base_rate, 3), excess_cost_total=int(mon.excess_cost_inr.sum()),
    excess_cost_q1_2026=int(mon[mon.quarter == "2026Q1"].excess_cost_inr.sum()),
    excess_cost_latest_q=int(mon.iloc[-1].excess_cost_inr), flagged_tickets=int(t.badlot.sum()),
    reviewed_agents=int(ag.verdict.str.startswith("REVIEW").sum()), cleaning=log)
json.dump(headline, open(f"{args.out}/headline.json", "w"), indent=2, default=str)

def esc(x): return html.escape(str(x))
def line_svg(series, w=760, h=200):
    keys = list(series[0][1].index); lo, hi = 2.6, 3.9
    def X(i): return 40 + i * (w - 60) / (len(keys) - 1)
    def Y(v): return h - 25 - (v - lo) / (hi - lo) * (h - 45)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%">']
    for g in [2.8, 3.2, 3.6]:
        out.append(f'<line x1="40" x2="{w-20}" y1="{Y(g)}" y2="{Y(g)}" stroke="#ddd"/><text x="4" y="{Y(g)+4}" font-size="11" fill="#666">{g}</text>')
    for i, k in enumerate(keys):
        if i % 3 == 0: out.append(f'<text x="{X(i)-16}" y="{h-6}" font-size="10" fill="#666">{k}</text>')
    for name, s, col in series:
        pts = " ".join(f"{X(i):.0f},{Y(s.get(k, np.nan)):.0f}" for i, k in enumerate(keys) if not np.isnan(s.get(k, np.nan)))
        out.append(f'<polyline fill="none" stroke="{col}" stroke-width="2.5" points="{pts}"/>')
    lx = 50
    for name, s, col in series:
        out.append(f'<rect x="{lx}" y="6" width="12" height="4" fill="{col}"/><text x="{lx+16}" y="12" font-size="11">{esc(name)}</text>'); lx += 260
    return "".join(out) + "</svg>"

def tbl(df, cols, heads, fmt=None, cls=None):
    fmt = fmt or {}
    r = ["<table><tr>" + "".join(f"<th>{h}</th>" for h in heads) + "</tr>"]
    for _, row in df.iterrows():
        c = ' class="rev"' if str(row.get("verdict", "")).startswith("REVIEW") else ""
        r.append(f"<tr{c}>" + "".join(f"<td>{fmt[k](row[k]) if k in fmt else esc(row[k])}</td>" for k in cols) + "</tr>")
    return "".join(r) + "</table>"

def vlabel(v):
    if v.startswith("REVIEW"): return "WATCH: lowest Tier-1 adjusted score (see note)"
    if v.startswith("Raw"): return "Low because of the queue, not distinguishable from peers"
    return "ok"
ag["verdict_txt"] = ag.verdict.map(vlabel)
ag["who"] = ag.agent_id + " " + ag["name"]
f1 = lambda v: f"{v:.2f}"; f2 = lambda v: f"{v:+.2f}"
bottom = ag.head(10)
fmtA = {"raw_csat": f1, "adj_vs_avg": f2, "se": lambda v: f"±{1.645*v:.2f}", "defect_lot_share": lambda v: f"{v:.0%}",
        "ht_vs_team_pct": lambda v: f"{v:+.0f}%", "handle_med_min": lambda v: f"{v:,.0f}", "breach_rate": lambda v: f"{v:.0%}",
        "repl_rate": lambda v: f"{v:.0%}"}
cols = ["raw_rank", "who", "team", "tier", "surveyed", "raw_csat", "defect_lot_share", "adj_vs_avg", "se", "verdict_txt"]
heads = ["Raw rank", "Agent", "Team", "Tier", "Surveyed", "Raw CSAT", "Share of tickets on faulty lots", "Adjusted vs peers", "90% band", "Read"]
full_cols = ["raw_rank", "who", "team", "tier", "shift", "surveyed", "raw_csat", "adj_vs_avg", "se", "handle_med_min", "ht_vs_team_pct", "breach_rate", "verdict_txt"]
full_heads = ["Raw rank", "Agent", "Team", "Tier", "Shift", "Surveyed", "Raw CSAT", "Adjusted vs peers", "90% band", "Median handle (min)", "Handle vs own team", "SLA breach", "Read"]
top5raw = ag.tail(5)[::-1]; top5adj = ag[ag.tier == 1].sort_values("adj_vs_avg", ascending=False).head(5)
flag = alerts[alerts.flag]
H = f"""<!doctype html><meta charset=utf-8><title>Vireo support dashboard</title>
<style>body{{font:14px/1.45 system-ui,sans-serif;max-width:1100px;margin:20px auto;padding:0 14px;color:#222}}
table{{border-collapse:collapse;width:100%;margin:8px 0 18px;font-size:12.5px}}th,td{{border:1px solid #ddd;padding:4px 6px;text-align:left}}th{{background:#f3f3f3}}
.rev{{background:#fff3cd}}.k{{display:flex;gap:12px;flex-wrap:wrap}}.k div{{background:#f6f8fa;padding:10px 14px;border-radius:8px;min-width:170px}}.k b{{font-size:22px;display:block}}
h2{{margin-top:26px}}small{{color:#666}}</style>
<h1>Vireo Audio support: CSAT and handle time per agent</h1>
<div class=k>
<div><b>{headline['csat_q1_all']}</b>CSAT Jan-Mar 2026</div>
<div><b>{headline['csat_q1_excl_flagged']}</b>same quarter, excluding {headline['flagged_tickets']:,} tickets on faulty Pulse 2 lots</div>
<div><b>{headline['repl_rate_flagged']:.0%} vs {headline['repl_rate_baseline']:.0%}</b>replacement rate: faulty lots vs everything else</div>
<div><b>Rs {headline['excess_cost_total']/1e5:.1f} lakh</b>excess replacement cost so far (Rs {headline['excess_cost_q1_2026']/1e5:.1f} lakh in Q1 2026)</div></div>
<h2>1. Why CSAT slid</h2>
{line_svg([("All tickets", m_all, "#c0392b"), ("Excluding faulty Pulse 2 lots", m_ex, "#2c7fb8")])}
<p>Outside three Pulse 2 manufacturing lots the CSAT line is flat. Tickets on those lots (left earbud not charging) score {headline['csat_flagged_lots']} and get a replacement {headline['repl_rate_flagged']:.0%} of the time.</p>
{tbl(flag.assign(rate=flag.rate), ["product_sku","lot_month","n","k","rate","sku_med","z"], ["SKU","Lot month (YYMM)","Tickets","Replacements","Replacement rate","Typical rate for SKU","z-score"], {"rate": lambda v: f"{v:.0%}", "sku_med": lambda v: f"{v:.0%}", "z": lambda v: f"{v:.0f}"})}
{tbl(mon, ["quarter","tickets","replacements","expected_at_baseline","excess_replacements","excess_cost_inr"], ["Quarter","Tickets on flagged lots","Replacements","Expected at baseline rate","Excess replacements","Excess cost (Rs)"], {"excess_cost_inr": lambda v: f"{v:,.0f}"})}
<small>Replacement cost = unit cost + Rs 340 (policy s5): Pulse 2 = Rs 1,820, not Rs 2,500.</small>
<h2>2. The bottom ten, as asked, and what they really are</h2>
{tbl(bottom, cols, heads, fmtA)}
<p><b>How to read:</b> "Adjusted" removes what the queue does to CSAT (issue category, channel, priority, transfers, SLA breach, and whether the ticket is a faulty-lot earbud fault), then compares agents only with peers in the same tier (policy s6: Tier 2 is not compared with Tier 1). The band is a 90% interval; if it spans zero the person is not distinguishable from peers.</p>
<p><b>Note on the one WATCH:</b> with 44 agents, about two would fall below the 90% line by chance alone. One agent doing so is what noise looks like. It is a reason to listen to some of their chats, not a reason to spend training budget.</p>
<h2>3. Top five (Diwali bonus)</h2>
<p>By raw CSAT: {", ".join(esc(x) for x in top5raw.who)}. By adjusted Tier-1 score: {", ".join(esc(x) for x in top5adj.who)}. The gaps at the top are 0.1 to 0.3 with a band of about ±0.2, so this is a weak basis for a bonus.</p>
<h2>4. Everyone</h2>
{tbl(ag, full_cols, full_heads, {**fmtA})}
<small>Handle time = first response to resolution (helpdesk definition); legacy resolution times shifted +5h30 (they were stored in UTC). Logistics and Returns show ~24h by design; compare within team only. Tier 2 is measured in days.</small>
<h2>5. Data handling</h2><pre>{esc(json.dumps(log, indent=1))}</pre>
"""
open(f"{args.out}/dashboard.html", "w").write(H)
print(json.dumps(headline, indent=1, default=str))
print(ag[["agent_id","name","tier","raw_rank","raw_csat","adj_vs_avg","se","verdict"]].head(10).round(2).to_string())
