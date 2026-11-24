# Known blockers in this container (2026-11-24 7pm scheduled run)

## This run: 18/23 gates green via the ClickHouse + Zoho Desk MCP connectors only

Both connectors worked. `pipeline/.zoho.env` is still absent, so the REST-only scripts
(`pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `pull_swap_routing.py`,
`pull_complaint_tickets.py`, `recheck_wh_comments.py`, `fetch_swap_images.py`) fail immediately - same
as every recent unattended run. Everything that *can* be done via the Zoho Desk MCP fallback
(searchTickets by ticketNumber, never batched-and-paired-by-position, then getTicketComments with the
full thread read before classifying) was done directly this run:

- ClickHouse return-request pull: 4 trailing-28-day chunks (27 Oct - 24 Nov), closing the "returns pull
  covers through yesterday" gate. (Note: `SELECT x.*` qualifies the column as `x.order_id`, not
  `order_id` - had to rename it in all 4 saved files before `build_complaints.py` would load them;
  worth selecting `x.order_id AS order_id` explicitly next time.)
- Core WH-verdict gate: 25 tickets (1 past-T2 + 24 provisional) read and classified via MCP - 1 denied,
  21 no_wh_comment, 3 unrecognized. Gate closed (0).
- `build_full_dataset.py` / `build_report.py` / `build_eod_auto.py` rerun - EOD tab through T-2
  2026-11-22 (1 ticket, denied).
- Zoho complaint-ticket pull (REST blocked): pulled 2026-11-22 (re-pull, was same-day-partial) and
  2026-11-23 via MCP `searchTickets customField1=cf_dispositions:Return and Pickup`, `ingest_tickets.py`,
  `extend_consolidated.py`. Closed the "zoho complaint tickets" freshness gate.
- Complaint-baseline WH-verdict gap: 18 tickets closed via the same MCP flow - found a genuine new
  admission (270694 / order 4882462, "we have sent wrong batch to cx", MRP/Batch Mismatch). Note:
  `ingest_wh.py`'s order_id lookup only checks `data.json` (MRP/Switch-Orders tickets are deliberately
  excluded from data.json, so this ticket's `order_id` came back `None`) - patched it by hand from the
  ticket pull; `ingest_wh.py` should also fall back to `cmp_zoho_tickets.json`'s `order_raw` the way its
  own docstring already claims it does.
- Order Swap: the one new baseline swap complaint (order 4800881) is now covered by a case via
  `build_swap.py`'s automatic "baseline swap complaints" step - no manual pairing needed this time.
  Also re-ran `swap_view_spec.py` after `build_swap.py` (was skipped at first, caused 3 `test_view_js.js
  swap` cell mismatches - fixed by rerunning in the right order).
- Rebuilt `cmp_view_spec.py`, `archive_exports.py`, `build_html.py`; all local tests green except the
  known photo backlog (`test_complaints.py` damage-photo check, `PHOTO_BACKLOG_OK=1` confirmed it's the
  only failure) and the three structural items below.

Full detail of this run's work is in the "Refresh 2026-11-24" commit message.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`)

Still absent. Blocks the RCA layer's `pull_dependency.py` / `pull_ticket_routing.py`, the swap/complaint
pull scripts, and `fetch_swap_images.py` specifically (not the WH-verdict reads or ticket pulls, which
the MCP fallback covers) - this is why `rca_export.json` and `swap_export.json`'s `t2_cap_date` stay at
2026-11-20 instead of advancing, and why the one residual swap case (order 4800881) can't be
image-checked this run.

## 2. cdn.platinumrx.in not in this environment's network allowlist

Re-confirmed this run with a direct curl request: `CONNECT tunnel failed, response 403`. This blocks:
- 20 damage/RCA complaint rows "Photo not read yet" in the sanity window - the ClickHouse image-URL pull
  itself works fine, only the image *download* is blocked.
- Every RCA image read (expiry/wrong-medicine/damage photo evidence).

## 3. RCA item-missing tags: pack-mapping workbook not in this container

`~/Downloads/Pack Quantity & Base Value Changes*.xlsx` (the Sheet1 pack-quantity mapping workbook) does
not exist in this container, so the 30 orders flagged "Tags pending" in the T-2 window cannot be tagged.
This is a manual-pull input per CLAUDE.md, not something a session can regenerate itself.

## For the owner

Same three structural asks as every recent run, now the only things stopping this refresh from being
fully green:
1. **Zoho REST**: a persistence mechanism for `pipeline/.zoho.env` in the unattended container, or
   re-running the daily refresh from an interactive session periodically to close the REST-only gaps
   (RCA pipeline, swap routing/image-pairing).
2. **Network**: approve the `cdn.platinumrx.in` allowlist prompt once from an interactive "Run now" -
   fixes the photo-read backlog permanently for every future scheduled run too.
3. The pack-mapping workbook would need to live somewhere this container can read it (e.g. committed to
   the repo, gitignored, or re-uploaded each interactive session) if item-missing tagging is meant to run
   unattended.

All three are one-time or few-minute actions in an interactive session.
