# Known blockers in this container (2026-11-07 7pm run)

Both of these are environment-level, not data/logic bugs. This run still refreshed everything that
doesn't depend on them (see commit history) - `python3 pipeline/refresh_all.py gates` is green except
for the photo gate below.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged from 2026-11-06

Still absent in this fresh container (gitignored by design, repo is public). Scripts that call
`zoho_auth.desk_get()` - `pull_complaint_tickets.py`, `recheck_wh_comments.py` (full, uncapped run),
`pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `check_complaints_live.py` -
cannot run. The Zoho Desk MCP connector (available this session) is a documented fallback, but only
at bounded scale (dozens of tickets, not the full org pull these scripts do) - see 2026-11-06's note.

This run used the MCP fallback at bounded scale where it mattered:
- Read live comments for the 21 complaint-baseline tickets stuck at "Verdict not read (gap)" and the
  19 T-2 (2026-11-05) EOD tickets (most overlapped) - gap gate is now 0, EOD tab rebuilt through 2026-11-05.
- Did **not** attempt a full `pull_complaint_tickets.py`-equivalent org-wide pull, or the RCA/swap
  pipelines' Dependency/routing pulls - still blocked, same reasoning as 2026-11-06.

`complaints_export.json`'s Zoho-ticket side (`cmp_zoho_tickets.json`) is therefore one day staler than
the ClickHouse return side (pulled 2026-11-06, not re-pulled today) - still inside the gate's 1-day
tolerance, but will go red tomorrow if the credential is still missing.

## 2. cdn.platinumrx.in not in this environment's network allowlist (new today)

Damage-complaint photo reads (both the Order damage tab and the RCA layer) need to download images
from `cdn.platinumrx.in`. This container's network proxy returns 403 for that host - it's not on the
environment's allowed-hosts list. Adding it (`update_environment`) needs a person to approve the
prompt, and this is an unattended scheduled run with nobody present to answer it, so the call was
refused automatically. 13 orders are "Photo not read yet" within the last 30 days (all surfaced by
today's incremental return-request pull); `test_complaints.py`'s photo-backlog check was run with
`PHOTO_BACKLOG_OK=1` to allow this interim push - `refresh_all.py gates` still correctly reports it red.

## For the owner

- Zoho REST: same ask as 2026-11-06 - needs a persistence mechanism (secret storage / env var) this
  session can't set up itself.
- Network: next time a person runs this routine interactively (e.g. "Run now"), they'll be shown an
  approval prompt to add `cdn.platinumrx.in` to the Default environment's allowed hosts - approving it
  once fixes this permanently for future scheduled runs too, since it's a personal-environment-wide
  setting. Alternatively add it directly in environment network settings.
