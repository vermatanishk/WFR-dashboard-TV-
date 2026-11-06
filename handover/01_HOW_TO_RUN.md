# How to run

## Prerequisites
- Python 3 (scripts use stdlib + requests-style Zoho REST via `pipeline/zoho_auth.py`), Node (only for `test_view_js.js`).
- `pipeline/.zoho.env` present. Zoho Desk + ClickHouse MCP connected in Claude Code.
- Work from repo root. Run `git log --oneline | grep -i refresh` first to see how stale the data is.

## Just rebuild the site from existing JSON (no data pull)
```bash
python3 pipeline/build_html.py     # fills __X_JSON__ placeholders in pipeline/dashboard.html
                                   # -> pipeline/dashboard_built.html, copied to ./index.html
open index.html                    # preview locally
```
Edit UI in `pipeline/dashboard.html`, never in `index.html` (overwritten).

## Daily refresh (ask Claude Code: "run the daily refresh")
**Start with `python3 pipeline/refresh_all.py plan`, finish with `python3 pipeline/refresh_all.py gates` (must be all green). It covers every layer, incrementally.**
Commit checkpoints as `WIP: ...` after each stage (pulls are rate-limited); finish with `Refresh <date> <time> IST`.

**A. Core data**
1. Pull raw data into `pipeline/zoho_raw90/` (Zoho tickets; ClickHouse returns / pickers / QC chunks, cold-chain flags,
   user-warehouse map, `ch_delivered_daily.json`).
2. `python3 pipeline/recheck_wh_comments.py` - re-reads provisional WH verdicts (`no_wh_comment`/`unrecognized`) and uncached tickets.
3. `python3 pipeline/build_full_dataset.py` -> `data.json`, `personnel.json`, `trend.json`
4. `python3 pipeline/build_report.py` -> `aggregates.json`, `wfr_daily_report.csv` (check `reconciles` is True)
5. `python3 pipeline/build_eod.py` -> `data_eod.json`; then sync its verdicts into `zoho_raw90/wh_text_check.json`
6. `python3 pipeline/build_macro_trend.py` -> `macro_trend.json` (T-2 capped)
7. RFD weekly (Sundays) -> `rfd_weekly.json` (see `RFD_Adherence_Logic_Documentation.md`)

**B. RCA layer** - follow "RCA daily refresh checklist" in `CLAUDE.md` (Zoho REST pulls, ClickHouse pulls for new orders,
image read via vision, item-missing tags, then `build_rca_wrongmed` -> `build_rca_inputs` -> `build_rca_extra` -> `build_rca`
-> `build_item_missing_tags` -> `build_rca_export` -> `build_rca_trend`).
Pass check: `rca_trend.json` `t2_cutoff` == pull date - 2; photo-not-read and tags-pending are 0 in the T-2 window.

**C. Complaint baseline (WFR funnel / Damage / Swap / Summary tabs)** - see CLAUDE.md "Complaint baseline layer":
`pull_complaint_tickets.py` -> `build_complaints.py` -> `recheck_wh_comments.py --extra zoho_raw90/cmp_tickets_to_read.json`
-> `build_complaints.py` -> `damage_images.py` -> `cmp_view_spec.py`.
Swap tab: `pull_swap_tickets.py`, `pull_swap_routing.py`, `read_swap_wh.py`, `build_swap.py`, `swap_view_spec.py`.

**D. Ship**
```bash
python3 pipeline/build_html.py
# run tests (below), then:
git add -A pipeline index.html && git commit -m "Refresh <date> <time> IST"
git fetch && git merge origin/main && git push origin main     # Vercel deploys on push
```
Commit the export/trend/spec JSONs too - the Google Sheet reads them from GitHub.

## Tests (all must pass before pushing)
```bash
python3 pipeline/test_wh_comment_classifier.py
python3 pipeline/test_rca.py
python3 pipeline/test_rca_trend.py
python3 pipeline/check_view_from_export.py
python3 pipeline/test_complaints.py
node pipeline/test_view_js.js wfr   # also: damage, swap
python3 pipeline/check_complaints_live.py   # live check, needs access
```

## Google Sheet
First time: new Sheet -> Extensions > Apps Script -> paste `pipeline/gsheet/Code.gs` -> run `refreshAll`, then
`installDailyTrigger` (daily 07:00 IST). Re-paste `Code.gs` whenever it changes in the repo. Details: `pipeline/gsheet/README.md`.
GitHub raw caches ~5 min after a push.
