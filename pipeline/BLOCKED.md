# Known blockers in this container (2026-11-23 7pm scheduled run)

## This run: 16/20 gates green via the ClickHouse + Zoho Desk MCP connectors only

Both connectors worked. `pipeline/.zoho.env` is still absent, so the REST-only scripts
(`pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `pull_swap_routing.py`,
`pull_complaint_tickets.py`, `recheck_wh_comments.py`) fail immediately - same as every recent
unattended run. Everything that *can* be done via the Zoho Desk MCP fallback (searchTickets by
ticketNumber, never batched-and-paired-by-position, then getTicketComments with the full thread read
before classifying) was done directly this run:

- Core WH-verdict gate: 36 tickets past T-2 (2026-11-21) read and classified - 3 admissions, 28 denials,
  4 no_wh_comment, 1 unrecognized. Gate closed (0).
- EOD tab rebuilt through T-2 2026-11-21 (3 accepted).
- Complaint-baseline WH-verdict gap (7 tickets) closed the same way.
- Order Swap: closed the one unpaired residual case (order 4807460, ticket 270588 - the agent's own
  comment names the swap partner order 4842987, corroborated by ClickHouse: same pincode, warehouse,
  courier label path).
- Also found and pushed 26 commits a prior session had left uncommitted to origin (origin/main was stuck
  at 2026-11-17 while local disk held work through 2026-11-22) - the live dashboard was several days
  stale before this run for a reason unrelated to this container's blockers.

Full detail of this run's work is in the "Refresh 2026-11-23" commit message.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`)

Still absent. Blocks the RCA layer's `pull_dependency.py` / `pull_ticket_routing.py` and the swap/
complaint pull scripts specifically (not the WH-verdict reads, which the MCP fallback covers) - this is
why `rca_export.json` and `swap_export.json`'s `t2_cap_date` stay at 2026-11-20 instead of advancing to
2026-11-21 even though the core and complaint-baseline layers are current through 2026-11-22.

## 2. cdn.platinumrx.in not in this environment's network allowlist

Re-confirmed this run with a direct curl request: `CONNECT tunnel failed, response 403`. Tried
`update_environment` to add it to the Default environment's allowlist (a concrete, recurring need,
documented in this file for weeks) - refused because nobody is present to approve it on an unattended
run. This blocks:
- 9 damage complaint rows "Photo not read yet" (1 inside the T-2 sanity-check window) - the ClickHouse
  image-URL pull itself works fine, only the image *download* is blocked.
- The new unpaired swap complaint (order 4800814, no ticket at all) - no image, no thread to check either.
- Every RCA image read (expiry/wrong-medicine/damage photo evidence).

## 3. RCA item-missing tags: pack-mapping workbook not in this container

`~/Downloads/Pack Quantity & Base Value Changes*.xlsx` (the Sheet1 pack-quantity mapping workbook) does
not exist in this container, so the 30 orders flagged "Tags pending" in the T-2 window cannot be tagged.
This is a manual-pull input per CLAUDE.md, not something a session can regenerate itself.

## For the owner

Same two structural asks as every recent run, now the only things stopping this refresh from being
fully green:
1. **Zoho REST**: a persistence mechanism for `pipeline/.zoho.env` in the unattended container, or
   re-running the daily refresh from an interactive session periodically to close the REST-only gaps.
2. **Network**: approve the `cdn.platinumrx.in` allowlist prompt once from an interactive "Run now" -
   fixes the photo-read backlog permanently for every future scheduled run too.
3. The pack-mapping workbook would need to live somewhere this container can read it (e.g. committed to
   the repo, gitignored, or re-uploaded each interactive session) if item-missing tagging is meant to run
   unattended.

All three are one-time or few-minute actions in an interactive session.
