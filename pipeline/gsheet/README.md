# WFR live Google Sheet ("WFR Breakdown")

Rebuilt from git (public repo, no token) twice a day. **Nothing is ever deleted** - raw tabs are an append/upsert cache.

| # | Tab | Source (`pipeline/`) | What |
|---|---|---|---|
| 1 | Summary | `cmp_summary.json` | max 8 rows x 3 columns (WFR / Damage / Swap), last 30 days |
| 2 | WFR funnel | `cmp_wfr_export.json` + `cmp_wfr_view_spec.json` | complaints = UNION of ClickHouse return requests and Zoho tickets, day-wise 60 days, with the root-cause cascade |
| 3 | Order damage | `cmp_damage_export.json` + spec | physical damage by photo bucket, temperature complaints separate |
| 4 | Order Swap | `swap_export.json` + spec | swap cases attributed Warehouse vs Logistics |
| 5-7 | WFR raw data / Damage raw data / Swap raw data | the exports + `archive/*_archive.json` | the detailed breakdown: one row per complaint (order x type) / swap case |
| 8 | Info | all | data-through date per layer (red = stale), refresh errors, latest `sanity_report.json` |

Hidden `... spec` tabs hold the layouts. **Any other tab (e.g. `sreeniketh`) is never touched** and stays after these.

## One-time setup (re-paste after every change of `Code.gs`)

1. Open the sheet > **Extensions > Apps Script**, replace all of `Code.gs` with `pipeline/gsheet/Code.gs`, Save.
2. Run **`refreshAll`** once (approve "connect to an external service" + sheet edit).
3. Run **`installDailyTrigger`** once: two daily refreshes, **07:00 and 21:00 IST** (the 7 pm routine pushes about 20:00 IST).
4. A **WFR** menu appears after reload (Refresh now / Install daily refresh / Re-order tabs).

## How old data is kept

* Raw tabs = what is already in the tab U `archive/<export>_archive.json` (rows added only if missing) U the latest export (rows refreshed in place by key). Keys: `Order ID + Complaint type` (WFR, damage), `Order ID + Ticket ID` (swap). Rows leaving the 60-day window stay; new columns are appended at the right.
* The same rows live in git (`pipeline/archive_exports.py`, append-only), so the sheet can always be rebuilt and `refresh_all.py gates` fails if the archive ever shrinks.
* Views are recomputed from the whole raw tab but only show the trailing 60 days (same evaluator as the website, checked cell-by-cell by `node pipeline/test_view_js.js wfr|damage|swap`).

## Staleness is visible, never silent

Row 1 of every view (and the Summary) says "Data through D" and turns red **STALE** when D is more than 2 days behind today (IST). The Info tab lists every layer plus the failing items of the last sanity check and any refresh error (a failing layer never stops the others).

## Notes

* **Public data.** The repo is public: the exports hold only IDs, dates, warehouse and bucket labels - no names, phones, addresses or WH comment text.
* `raw.githubusercontent.com` caches ~5 minutes, so "Refresh now" right after a push can show the previous version.
