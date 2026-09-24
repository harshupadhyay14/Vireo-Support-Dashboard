"""Vireo support analytics: cleaning, lot-defect detection, fair agent scorecard, money.
No model/API calls. Runs on pandas + numpy only."""
import re
import numpy as np, pandas as pd

IST_SHIFT_MIN = 330          # legacy resolved_at was reconstructed from a UTC log
SLA = {"chat": 15, "voice": 120, "social": 240, "email": 480}   # minutes, policy s3
LOGISTICS_PER_REPL = 340     # policy s5
SLA_CREDIT = 350             # policy s3
TRANSFER_COST = 305          # policy s4

DEFECT_RE = re.compile(
    r"((left|lft|l bud|l earbud|one side|one bud|right is fine).{0,40}(charg|bud|earbud|audio|dead|not work|paperweight|no sound))"
    r"|((charg).{0,25}(left|case))")

def load(d="data"):
    t = pd.read_csv(f"{d}/tickets.csv", parse_dates=["created_at", "first_response_at", "resolved_at"])
    o = pd.read_csv(f"{d}/orders.csv", parse_dates=["order_date"])
    a = pd.read_csv(f"{d}/agents.csv")
    p = pd.read_csv(f"{d}/products.csv")
    return t, o, a, p

def clean(t, o, a):
    t = t.copy()
    log = {}
    leg = t.source_system == "legacy_fd"
    log["legacy_rows"] = int(leg.sum())
    log["negative_handle_before_fix"] = int(((t.resolved_at - t.first_response_at).dt.total_seconds() < 0).sum())
    t.loc[leg, "resolved_at"] += pd.Timedelta(minutes=IST_SHIFT_MIN)
    t["wait_min"] = (t.first_response_at - t.created_at).dt.total_seconds() / 60
    t["handle_min"] = (t.resolved_at - t.first_response_at).dt.total_seconds() / 60
    log["negative_handle_after_fix"] = int((t.handle_min < 0).sum())
    t["breach"] = t.wait_min > t.channel.map(SLA)
    t["repl"] = t.replacement_issued.eq("Y")
    ok = t.status.isin(["resolved", "closed"])
    log["csat_on_open_or_pending_dropped"] = int((t.csat_score.notna() & ~ok).sum())
    t["csat"] = t.csat_score.where(ok)          # blank stays NaN, never 0
    t = t.merge(o[["order_id", "lot_code"]], on="order_id", how="left")
    miss = t.lot_code.isna()
    fb = t.loc[miss, ["ticket_id", "customer_id", "product_sku", "created_at"]].merge(
        o, left_on=["customer_id", "product_sku"], right_on=["customer_id", "sku"])
    fb = fb[fb.order_date <= fb.created_at.dt.normalize()].sort_values("order_date").groupby("ticket_id").tail(1)
    t = t.set_index("ticket_id")
    t.loc[fb.ticket_id.values, "lot_code"] = fb.set_index("ticket_id").lot_code
    t = t.reset_index()
    log["lot_join_rate"] = round(float(t.lot_code.notna().mean()), 4)
    t["lot_month"] = t.lot_code.str.split("-").str[1]
    t["text"] = (t.customer_message.fillna("") + " " + t.agent_notes.fillna("")).str.lower()
    t["defect_text"] = t.text.apply(lambda s: bool(DEFECT_RE.search(s)))
    t = t.merge(a[["agent_id", "name", "team", "site", "shift", "tier"]], on="agent_id", how="left")
    log["tickets_without_agent_row"] = int(t.team.isna().sum())
    return t, log

def lot_alerts(t, min_n=30, z_min=4.0, lift_min=0.10):
    """Flag (sku, lot_month) cells whose replacement rate is far above the SKU's typical cell."""
    g = t.dropna(subset=["lot_month"]).groupby(["product_sku", "lot_month"]).agg(
        n=("repl", "size"), k=("repl", "sum")).reset_index()
    g = g[g.n >= min_n].copy()
    g["rate"] = g.k / g.n
    med = g.groupby("product_sku").rate.median().rename("sku_med")
    g = g.join(med, on="product_sku")
    p0 = g.sku_med
    g["z"] = (g.rate - p0) / np.sqrt(p0 * (1 - p0) / g.n)
    g["flag"] = (g.z >= z_min) & (g.rate - p0 >= lift_min)
    return g.sort_values(["product_sku", "lot_month"])

def money(t, prod, alerts):
    cost = (prod.set_index("sku").unit_cost_inr + LOGISTICS_PER_REPL).to_dict()
    flagged = set(map(tuple, alerts[alerts.flag][["product_sku", "lot_month"]].values))
    t = t.copy()
    t["badlot"] = [(s, l) in flagged for s, l in zip(t.product_sku, t.lot_month)]
    base_rate = t[~t.badlot].repl.mean()
    t["unit_repl_cost"] = t.product_sku.map(cost)
    rows = []
    for q, d in t[t.badlot].groupby(t.created_at.dt.to_period("Q")):
        act = (d.repl * d.unit_repl_cost).sum(); exp = (base_rate * d.unit_repl_cost).sum()
        rows.append(dict(quarter=str(q), tickets=len(d), replacements=int(d.repl.sum()),
                         expected_at_baseline=round(base_rate * len(d), 1),
                         excess_replacements=round(d.repl.sum() - base_rate * len(d), 1),
                         excess_cost_inr=round(act - exp)))
    return t, base_rate, pd.DataFrame(rows)

def ols(y, X):
    inv = np.linalg.pinv(X.T @ X)
    b = inv @ X.T @ y
    r = y - X @ b
    s2 = (r @ r) / (len(y) - np.linalg.matrix_rank(X))
    return b, np.sqrt(np.diag(inv) * s2)

def scorecard(t):
    d = t[t.csat.notna()].copy()
    d["defect"] = d.badlot & d.defect_text
    X = pd.get_dummies(d[["category", "channel", "priority"]], drop_first=True).astype(float)
    for c in ["badlot", "defect", "breach"]:
        X[c] = d[c].astype(float)
    X["transfers"] = d.transfers.astype(float)
    A = pd.get_dummies(d.agent_id).astype(float)
    Z = pd.concat([X, A], axis=1)
    b, se = ols(d.csat.values, Z.values.astype(float))
    b = pd.Series(b, Z.columns); se = pd.Series(se, Z.columns)
    ag = pd.DataFrame({"adj": b[A.columns], "se": se[A.columns]})
    cov = b[X.columns].round(3)
    info = t.groupby("agent_id").agg(
        name=("name", "first"), team=("team", "first"), tier=("tier", "first"), shift=("shift", "first"),
        site=("site", "first"), tickets=("ticket_id", "size"), surveyed=("csat", "count"),
        raw_csat=("csat", "mean"), breach_rate=("breach", "mean"),
        defect_lot_share=("badlot", "mean"), repl_rate=("repl", "mean"))
    ag = info.join(ag)
    # compare like with like: Tier 1 with Tier 1, Tier 2 with Tier 2 (policy s6)
    ag["adj_vs_avg"] = ag.adj - ag.groupby("tier").adj.transform("mean")
    h = t[t.status.isin(["resolved", "closed"]) & (t.handle_min > 0)].copy()
    h["lh"] = np.log(h.handle_min)
    tm = h.groupby("team").lh.median().rename("team_lh")
    h = h.join(tm, on="team")
    ht = h.groupby("agent_id").agg(handle_med_min=("handle_min", "median"), lh=("lh", "median"), team_lh=("team_lh", "first"))
    ag = ag.join(ht)
    ag["ht_vs_team_pct"] = (np.exp(ag.lh - ag.team_lh) - 1) * 100
    ag["z"] = ag.adj_vs_avg / ag.se
    ag["verdict"] = np.where((ag.z <= -1.645) & (ag.surveyed >= 40), "REVIEW: below peers beyond noise",
                     np.where(ag.raw_csat.rank() <= 10, "Raw bottom-10, but within noise once queue is adjusted", "ok"))
    return ag.reset_index(), cov
