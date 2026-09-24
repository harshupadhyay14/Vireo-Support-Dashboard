# Vireo support dashboard (Set B)

Per-agent CSAT and handle time, with the bottom ten flagged, plus the thing that turned out to matter more:
three faulty Pulse 2 manufacturing lots explain the CSAT slide and the replacement spike.

## Run (clean machine, ~10 seconds, no API keys, no network)
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# put the client exports in ./data/ named: tickets.csv agents.csv orders.csv customers.csv products.csv
python run.py            # writes out/dashboard.html + out/*.csv + out/headline.json
python tests/test_pipeline.py   # or: python -m pytest -q
```
Open `out/dashboard.html`. Client CSVs are not committed (customer data); customers.csv and the PDF are not used.

## What it does
1. **Cleans**: legacy (Freshdesk) `resolved_at` was stored in UTC, so 2,309 rows had negative handle time; shifted +5h30, now 0 negatives.
   Blank CSAT stays blank (never 0); CSAT on open/pending tickets (249) dropped; agents joined on `agent_id` only.
2. **Finds faulty lots automatically**: joins tickets to orders (order_id, else the customer's most recent earlier order of that SKU; 99.2% joined),
   then flags SKU x lot-month cells whose replacement rate is far above the SKU's normal (z>=4 and +10 points). It flags exactly Pulse 2 lots 2510, 2511, 2512.
3. **Scores agents fairly**: OLS of CSAT on issue category, channel, priority, transfers, SLA breach, faulty-lot, faulty-lot-earbud-fault (free-text rule), plus agent fixed effects.
   Agents are compared within tier (policy s6). Reports a 90% band. Handle time is compared with the agent's own team median (Logistics/Returns are ~24h by design; Tier 2 is days).
4. **Costs it** with policy numbers: replacement = unit cost + Rs 340.

## Files
`run.py` entry point - `src/vireo.py` logic - `tests/` - `validation/defect_text_labels.csv` (60 hand-labelled tickets) - `MEMO.md` - `SUBMISSION.md`

## Decisions I made (nobody to ask)
- Did not rank all 44 on one scale; Tier 2 vs Tier 2, Tier 1 vs Tier 1.
- "Handle time" = first response to resolution, per policy s10.
- Bottom ten is still printed (raw), next to the adjusted read, because that is what was asked.
- No LLM calls at all: Finance said no per-ticket calls, and rules + statistics were enough.
- Ignored customers.csv, the IVR-junk tickets are left in (they affect the message text only, not CSAT or times).
