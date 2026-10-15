# WFR RCA live Google Sheet

Two tabs, rebuilt from git on every refresh:

| Tab | Source file | What |
|---|---|---|
| Raw data | `pipeline/rca_export.json` | One row per **order** (first ticket wins), trailing 60 days: Order ID, Ticket ID, Created date, Warehouse, Issue, Investigation bucket 1 (Accepted / Rejected / No decision), Investigation bucket 2 (no-decision reason), Return request, Dependency, Raised bucket 1-3 (the issue tree), Evidence basis, Confidence, Photos read, In T-2 scope |
| RCA view | computed in the sheet from the Raw data tab, layout from `pipeline/rca_view_spec.json` | The day-wise table from the website's Tab 7 (3 month / last month / last 2 weeks, then one column per day, T-2 capped). Same spec as the website, verified cell-by-cell |
| Info | export + view | Data timestamp, T-2 date, row counts, how to read |

## One-time setup (about 2 minutes)

1. Create a new Google Sheet.
2. **Extensions > Apps Script**, delete the default `Code.gs` content and paste `pipeline/gsheet/Code.gs`.
3. Save, then select **`refreshAll`** and press Run. Approve the permissions
   (it needs "connect to an external service" to read the GitHub raw URL, and edit access to this sheet).
4. Select **`installDailyTrigger`** and Run once. The sheet then refreshes itself daily at 07:00 IST.
5. A **WFR RCA** menu appears in the sheet ("Refresh now") after reload.

The repo is public, so no token is needed. If the repo is ever made private, switch `BASE` in `Code.gs` to a
raw URL with a read-only token, or serve the two JSONs from the Vercel domain instead.

## Keeping it live

`build_rca_export.py` and `build_rca_trend.py` run in the daily refresh session (see CLAUDE.md, RCA layer);
pushing to `main` updates the two JSON files, and the sheet picks them up on its next refresh.
`raw.githubusercontent.com` caches for about 5 minutes, so "Refresh now" immediately after a push can show the
previous version.

## Notes

- **Public data.** The repo is public, so the order and ticket IDs in `rca_export.json` are world-readable.
  The export has no names, phones, addresses or WH comment text - only IDs, dates, warehouse and bucket labels.
- Column meanings and the bucket vocabulary are documented in the header of `build_rca_export.py`.
