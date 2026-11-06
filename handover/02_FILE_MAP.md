# File map (all under `pipeline/` unless noted)

## Repo root
| File | Purpose |
|---|---|
| `index.html` | Built, deployed dashboard (generated - do not hand-edit) |
| `CLAUDE.md` | Authoritative project brief + refresh procedure |
| `RCA_Learnings_and_Decisions.md` | Owner decisions and data traps for RCA / complaint baseline |
| `RFD_Adherence_Logic_Documentation.md` | RFD breach logic, two legacy pipelines |
| `Mis-shipment_Dashboard_Requirements.md` | Original spec (stale in places) |
| `deliverables_private/` | One-off leadership docs |

## Build / UI
| File | Purpose |
|---|---|
| `dashboard.html` | UI source template with `__X_JSON__` placeholders |
| `build_html.py` | Substitutes JSONs into template -> `dashboard_built.html` -> `../index.html` |
| `assets/` | Static images |

## Core classification (Tab 1)
| File | Purpose |
|---|---|
| `category_mapping.py` | `CATEGORY_MAP`: Zoho sub-disposition text -> 5 canonical categories (extend for new variants) |
| `wh_comment_classifier.py` | Warehouse Zoho comment -> admitted / denied / no_wh_comment / unrecognized |
| `recheck_wh_comments.py` | Live re-read of provisional verdicts; writes `zoho_raw90/wh_text_check.json` |
| `build_full_dataset.py` | `classify()`; writes `data.json`, `personnel.json`, `trend.json` |
| `build_report.py` | `aggregates.json`, `wfr_daily_report.csv` |
| `build_eod.py` | T-2 EOD tab -> `data_eod.json` |
| `build_macro_trend.py` | `macro_trend.json` |
| `rfd_weekly.json` | RFD adherence weekly output |

## RCA layer
`pull_dependency.py`, `pull_ticket_routing.py`, `zoho_auth.py` (Zoho REST) | `rca_images.py`/`image_reads.py`/`merge_reads.py`
(image download + vision-read merge) | `build_rca_wrongmed.py`, `build_rca_inputs.py`, `build_rca_extra.py`, `build_rca.py`,
`build_item_missing_tags.py`, `damaged_buckets.py`, `update_pickcheck.py` | `build_rca_export.py` -> `rca_export.json` |
`build_rca_trend.py` + `rca_view_spec.py` -> `rca_trend.json`, `rca_view_spec.json`.

## Complaint baseline + swap + damage
`pull_complaint_tickets.py`, `build_complaints.py` -> `complaints_export.json`, `cmp_{wfr,damage,swap_baseline}_export.json` |
`cmp_view_spec.py` -> `cmp_*_trend.json`, `cmp_*_view_spec.json`, `cmp_summary.json` | `damage_images.py`, `build_damage30.py`,
`scan_damage_video.py` | `pull_swap_tickets.py`, `pull_swap_routing.py`, `read_swap_wh.py`, `build_swap.py`, `swap_view_spec.py`
-> `swap_export.json`, `swap_trend.json`.

## Google Sheet
`gsheet/Code.gs` (Apps Script, evaluates the same view specs in-sheet) and `gsheet/README.md`.

## Tests
`test_wh_comment_classifier.py`, `test_rca.py`, `test_rca_trend.py`, `test_complaints.py`, `check_view_from_export.py`,
`check_complaints_live.py`, `test_view_js.js`.

## Data cache: `zoho_raw90/` (the pipeline's memory - do not delete)
| File | Purpose |
|---|---|
| `wh_text_check.json` | Per-ticket WH verdict cache. **Most valuable file**; grows incrementally |
| `ch_returns_c*.jsonl`, `ch_pickers_*`, `ch_qc_*`, `ch_delivered_daily.json` | ClickHouse pulls (chunked) |
| `cmp_returns_c*.json`, `cmp_zoho_tickets.json` | Complaint-baseline pulls |
| `rca_*.json(l)` | RCA inputs/outputs; `rca_manual_labels.json` = owner-confirmed ground truth |
| `rca_images/` | Downloaded photos (gitignored) |
| `ticket_dependency.json`, `ticket_routing.json` | Zoho Dependency / routing caches |
Gitignored: `.zoho.env`, `.zoho_token.json`, `zoho_raw90/_*`, `rca_images/`, `zoho_sample.csv`.
