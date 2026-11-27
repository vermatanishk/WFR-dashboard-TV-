# Known blockers in this container (2026-11-27 7pm scheduled run)

## This run: 17/24 gates green via the ClickHouse + Zoho Desk MCP connectors only

Both connectors worked (ClickHouse org PlatinumRx, Zoho org 60026539570). `pipeline/.zoho.env` is
still absent, so every REST-only script fails immediately - same as every recent unattended run.
Work done this run:

- ClickHouse returns pull: the 4 incremental 7-day chunks `refresh_all.py plan` listed (30 Oct - 27
  Nov), closing the "returns pull covers through yesterday" gate.
- Zoho complaint-ticket pull: REST failed immediately (`pull_complaint_tickets.py`), so pulled the
  "Return and Pickup" disposition tickets for 2026-11-26 and 2026-11-27 via the Zoho Desk MCP
  `searchTickets` fallback with `customField1="cf_dispositions:Return and Pickup"` (keeps each day's
  result well under the ~100-row API cap that a whole-day unfiltered query hits - confirmed the hard
  way: an unfiltered day-level query for 2026-11-26 silently returned only 100 of 149 tickets despite
  `count` reporting the true total, and even a half-day window still hit the cap at 106; the
  disposition filter is what actually fixes it, not date-splitting). Merged via `ingest_tickets.py`.
  2026-11-25 was re-checked and matched exactly (127=127), so left alone (never-recheck-on-match).
- Downloaded the "Pan India errors sheets" Google Sheet via the Drive MCP (`wh_error_log.py <csv>`):
  2 new August-through-today rows, 1 ticket newly marked `admitted`.
- Ran the full local (non-REST) build/RCA/swap chain: `build_rca_wrongmed/inputs/extra/build_rca`,
  `build_item_missing_tags` (needed `pip install pandas openpyxl` for the `python3` binary this
  container's `python3` resolves to - `/usr/local/bin/python3` = 3.11, pandas was only present under
  the separate `python3.13`), `build_rca_export/trend`, `build_swap`, `swap_view_spec`,
  `build_complaints` (both passes), `cmp_view_spec`, `archive_exports`, `build_html`, full test suite.
- Fixed two real bugs found while reconciling `sanity_check.py` against today's rebuild (not data
  staleness - both would have kept failing every day otherwise):
  1. `sanity_check.py`'s WH-accepted check only credited an order via a ticket's `admitted` verdict
     in `wh_text_check.json`, so a `wh_error_log`-only acceptance on an order with **no complaint
     ticket at all** (order 4230365 - legitimate per CLAUDE.md's "WH accepted without a complaint
     ticket" row) always failed the check. Now also credits orders present in `wh_error_log.json`
     with `scope: "in"`.
  2. `build_swap.py` anchored its 60-day window on **today** (`rca["generated_at"]`) instead of the
     T-2 cap `sanity_check.py` uses, leaving a 2-3 day gap at the old edge of the window where a
     ticketless swap complaint could sit uncovered (order 3844008, created 2026-09-27, fell just
     outside `start` while sanity's window still counted it). Anchored on `cap` instead - this was a
     standing bug that would recur at the window's trailing edge every day, not a one-off.
- `pull_ticket_routing.py` ran to completion without a REST error (unclear why - likely all 11
  candidate fetches failed individually inside its own try/except and it just resaved the unchanged
  cache; not investigated further, no gate depends on it today).
- Skipped (REST-only, hangs/fails immediately with no `.zoho.env`): `wh_error_log.py`'s own apply
  step ran fine with no args, but `pull_dependency.py`, `recheck_wh_comments.py` (both the no-arg and
  `--extra` calls - full backlog is ~1,165 tickets, far beyond what a single day's MCP fallback
  budget can cover one ticket at a time), `pull_swap_tickets.py`, `pull_swap_routing.py`,
  `read_swap_wh.py`, `scan_pack_text.py` all failed or hung on the missing REST credentials and were
  left alone; `wh_text_check.json`'s existing cache already has 0 hard gaps (gate green), so nothing
  this skip touches is a correctness gap today, only thoroughness.

Gates still red, same 3 structural causes as every recent run (see below): damage/RCA photos
(network), RCA item-missing tags (workbook), Zoho Desk REST access. `sanity_check.py` fails the same
3 checks, all tracing to those causes.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`)

Still absent. Blocks `pull_dependency.py`, `pull_ticket_routing.py` (effectively), `pull_swap_tickets.py`,
`pull_swap_routing.py`, `scan_pack_text.py`, and the ~1,165-ticket WH-comment recheck backlog
(`recheck_wh_comments.py`). The MCP fallback (`searchTickets` + per-ticket `getTicketComments`) works
but costs roughly one tool round-trip per ticket, so it only scales to the handful of tickets a gate
actually requires (today: the 2 new ticket-pull days), not the full backlog.

## 2. cdn.platinumrx.in not in this environment's network allowlist

Re-confirmed this run with a direct curl request: `CONNECT tunnel failed, response 403`. Blocks:
- 15 damage/RCA complaint rows "Photo not read yet" in the sanity window (ClickHouse image-URL pull
  works fine, only the image *download* is blocked).
- Every RCA image read (expiry/wrong-medicine/damage photo evidence).
- The 1 residual swap case (4923220) that needs an image check to pair.

An unattended run cannot get live approval for `update_environment`, so this needs the owner to add
the host once from an interactive session (see "For the owner" below).

## 3. RCA item-missing tags: pack-mapping workbook not in this container

`~/Downloads/Pack Quantity & Base Value Changes*.xlsx` still does not exist in this container, so
the 12 orders flagged "Tags pending" in the T-2 window (18 "Inputs pending" in the wider WFR
root-cause view) cannot be tagged. Manual-pull input per CLAUDE.md, not something a session can
regenerate itself.

## For the owner

Same three structural asks as every recent run:
1. **Zoho REST**: a persistence mechanism for `pipeline/.zoho.env` in the unattended container, or
   re-running the daily refresh from an interactive session periodically to close the REST-only gaps.
2. **Network**: start this routine with "Run now" once and approve the `cdn.platinumrx.in`
   allowlist prompt when it's shown interactively (or add the host in environment settings
   directly) - fixes the photo-read backlog permanently for every future scheduled run too.
3. The pack-mapping workbook needs to live somewhere this container can read it (committed
   gitignored, or re-uploaded each interactive session) for item-missing tagging to run unattended.

All three are one-time or few-minute actions in an interactive session.
