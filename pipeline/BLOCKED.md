# Known blockers in this container (2026-11-25 7pm scheduled run)

## This run: 17/24 gates green via the ClickHouse + Zoho Desk MCP connectors only

Both connectors worked (ClickHouse org PlatinumRx, Zoho org 60026539570). `pipeline/.zoho.env` is
still absent, so every REST-only script fails immediately - same as every recent unattended run.
Work done this run:

- ClickHouse returns pull: 4 trailing-28-day chunks (28 Oct - 25 Nov), closing the "returns pull
  covers through yesterday" gate.
- Rebuilt `build_complaints.py` on the fresh returns data - this surfaced 4 new WH-verdict gaps and
  33 new "Photo not read yet" damage rows (expected: fresher returns data = more complaint rows to
  investigate).
- Closed the 4 new WH-verdict gaps via the Zoho Desk MCP fallback (searchTickets by ticketNumber,
  paired by ticketNumber not position, then getTicketComments, full thread read before concluding):
  270916/order 4852480, 270838/order 4866333, 270940/order 4887704 (all Damage), 270871/order 4895817
  (Order swap) - all 4 threads had only L2-Agent comments, no Warehouse-role comment on any of them,
  so all 4 are `no_wh_comment`, ingested via `ingest_wh.py`.
- Rebuilt `build_complaints.py` again, `cmp_view_spec.py`, `archive_exports.py`, `build_html.py`.
- Attempted `damage_images.py sheets` - failed locally with `ImportError: cannot import name
  '_imaging' from 'PIL'` (broken Pillow install in this container) - moot anyway since the image
  *download* itself is blocked by blocker #2 below.
- Asked (via `update_environment`) to add `cdn.platinumrx.in` to this environment's network
  allowlist, since the block has now recurred for several days running - refused automatically
  because no person is present on an unattended run to approve it. See "For the owner" below for
  how to approve it.

Gates still green from before: core data/verdicts, EOD T-2, zoho complaint ticket freshness,
RCA photos (T-2 window), swap-complaints-all-covered, archive intact, index.html freshness.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`)

Still absent. Blocks `pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`,
`pull_swap_routing.py`, `pull_complaint_tickets.py`'s full range, `recheck_wh_comments.py`'s batch
mode, and `fetch_swap_images.py`. This is why `rca_export.json` and `swap_export.json` are both
still capped at `t2_cap_date` 2026-11-20 (5 days stale) - advancing them needs the Dependency field
and routing tags for every new ticket since then, which only the REST path pulls in bulk; doing it
ticket-by-ticket through the MCP fallback for this many tickets was out of today's token budget.
The single-ticket MCP fallback (searchTickets + getTicketComments) was still used today for the
core/complaint WH-verdict gaps, which is cheap at this volume (4 tickets).

## 2. cdn.platinumrx.in not in this environment's network allowlist

Re-confirmed this run with a direct curl request: `CONNECT tunnel failed, response 403`. Asked to
add it via `update_environment` this run; refused because the call needs a person's live approval
and this is an unattended scheduled run. Blocks:
- 23-33 damage/RCA complaint rows "Photo not read yet" in the sanity window (ClickHouse image-URL
  pull works fine, only the image *download* is blocked).
- Every RCA image read (expiry/wrong-medicine/damage photo evidence).
- The 2 residual swap cases (4800881, 4895817) that need an image check to pair.

## 3. RCA item-missing tags: pack-mapping workbook not in this container

`~/Downloads/Pack Quantity & Base Value Changes*.xlsx` still does not exist in this container, so
the 30 orders flagged "Tags pending" in the T-2 window cannot be tagged. Manual-pull input per
CLAUDE.md, not something a session can regenerate itself.

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
