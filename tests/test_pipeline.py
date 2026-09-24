"""Run: python -m pytest -q   (or: python tests/test_pipeline.py). Needs the CSVs in data/."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
from vireo import *

t0, o, a, p = load(os.path.join(os.path.dirname(__file__), "..", "data"))
t, log = clean(t0, o, a)

def test_no_negative_handle_time_after_utc_fix():
    assert log["negative_handle_before_fix"] > 1000 and log["negative_handle_after_fix"] == 0

def test_agent_join_is_by_id_and_keeps_the_two_kavyas_apart():
    k = a[a.name == "Kavya Pandey"].agent_id.tolist()
    assert len(k) == 2 and t[t.agent_id.isin(k)].groupby("agent_id").team.nunique().eq(1).all()
    assert log["tickets_without_agent_row"] == 0

def test_blank_csat_is_not_zero():
    assert t.csat.min() == 1 and t.csat.notna().sum() < t.csat_score.notna().sum() + 1

def test_lot_join_coverage():
    assert log["lot_join_rate"] > 0.98

def test_lot_alert_finds_exactly_pulse2_2510_to_2512_and_is_threshold_stable():
    for z in (3, 4, 6):
        f = lot_alerts(t, z_min=z)
        got = set(map(tuple, f[f.flag][["product_sku", "lot_month"]].values))
        assert got == {("VA-EB-PL2", "2510"), ("VA-EB-PL2", "2511"), ("VA-EB-PL2", "2512")}, (z, got)

def test_defect_text_rule_on_hand_labelled_sample():
    lab = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "validation", "defect_text_labels.csv"))
    s = lab.merge(t[["ticket_id", "defect_text"]], on="ticket_id")
    tp = (s.label & s.defect_text).sum(); fp = (~s.label & s.defect_text).sum(); fn = (s.label & ~s.defect_text).sum()
    assert tp / (tp + fp) >= 0.9 and tp / (tp + fn) >= 0.8

def test_tier2_never_ranked_against_tier1():
    tt, base, mon = money(t, p, lot_alerts(t)); ag, _ = scorecard(tt)
    assert abs(ag[ag.tier == 1].adj_vs_avg.mean()) < 1e-9 and abs(ag[ag.tier == 2].adj_vs_avg.mean()) < 1e-9

if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"): v(); print("ok", k)
