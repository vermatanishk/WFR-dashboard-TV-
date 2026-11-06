# Blocked: Zoho Desk REST credentials missing in this session's container

Run: scheduled 7pm IST daily refresh, 2026-11-06 19:xx IST.

## What's blocked

`pipeline/.zoho.env` (gitignored, holds `ZOHO_CLIENT_ID`/`ZOHO_CLIENT_SECRET`/`ZOHO_REFRESH_TOKEN`/etc.)
does not exist in this container, and none of the `ZOHO_*` env vars are set either. Every pipeline
script that uses `zoho_auth.desk_get()` (REST) fails immediately with `FileNotFoundError`:
`pull_complaint_tickets.py`, `recheck_wh_comments.py`, `pull_dependency.py`, `pull_ticket_routing.py`,
`pull_swap_tickets.py`, `check_complaints_live.py`. `python3 pipeline/refresh_all.py build` therefore
stopped at its first step (`pull_complaint_tickets.py`).

`zoho_auth.py`'s own documented fallback is "use the Zoho Desk MCP (searchTickets / getTicket /
getTicketComments) and write the same cache files" — the Zoho Desk MCP connector *is* available this
session and was used read-only to confirm the above. But `pull_complaint_tickets.py` pulls **every**
ticket (all dispositions, whole support org) created on each of the last 3 days, paginated 100/page —
redoing that over MCP in one turn is not a small fallback, it's a full reimplementation with real
pagination/pairing risk (CLAUDE.md already documents live bugs from `searchTickets` not returning rows
in request order), and isn't appropriate for a "lean, once-a-day" scheduled run. I did not attempt it.

## What's NOT blocked / current state

Nothing here is urgent: an earlier session today (commit `8ebaf0e`, 2026-11-06 12:29 IST) already ran a
full refresh — `python3 pipeline/refresh_all.py gates` prints **all gates green**, data current through
2026-11-05 (complaints) / 2026-11-03 (RCA, swap), `index.html` already reflects it and is live on Vercel.
This session made no data or pipeline changes — working tree was clean before this file was added.

## For the owner

This credential file is gitignored by design (repo is public / auto-deploys), so it will be missing in
*every* fresh cloud container unless something recreates it at session start. If scheduled 7pm runs
should reliably do the Zoho REST pull themselves (rather than relying on an occasional hands-on session
that happens to have it), the credential needs a persistence mechanism this session doesn't have access
to set up itself — e.g. `request_credential`-style secret storage, or an env var the container could read
`zoho_auth.env()` from. Flagging rather than guessing a fix.
