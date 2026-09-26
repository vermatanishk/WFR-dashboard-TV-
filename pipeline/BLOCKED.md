# Refresh blocked — 2026-09-26 (scheduled 7pm IST run)

**Missing/unusable connector: Zoho Desk (org id 60026539570, department 'Support')**

Second consecutive day this has blocked the refresh (see previous
`pipeline/BLOCKED.md` commit from 2026-09-25 — same root cause, still
unresolved).

The Zoho_Desk MCP server is present but requires OAuth authorization, and
this session is non-interactive (no browser flow available here). All
5 tool-pull steps (1, 2c, 5, 5b) and therefore the entire daily refresh
depend on Zoho Desk (`searchTickets`, `getTicketComments`), so the run was
stopped before touching any ClickHouse or pipeline state.

ClickHouse MCP connector (PlatinumRx org, service 'PRx Nucleus',
db prx_prod_db) was confirmed available and was NOT the blocker.

No data was pulled, no pipeline scripts were run, and no existing pipeline
files were modified in this attempt.

## To unblock

Authorize the Zoho Desk connector from an interactive session (via
`claude mcp` / `/mcp`, or claude.ai connector settings if it's a claude.ai
connector), then re-run the daily refresh. Dashboard data is now 2 days
stale (last successful refresh: 2026-09-24 19:50 IST) and will keep
falling behind until this is authorized.
