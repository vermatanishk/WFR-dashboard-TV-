# Daily refresh BLOCKED — 2026-10-20 19:11 IST

**Missing connector: ClickHouse** (PlatinumRx org, service "PRx Nucleus", db `prx_prod_db`).

The Zoho Desk MCP connector is available and working (`searchTickets`, `getTicketComments`,
etc. all resolved normally via ToolSearch).

The ClickHouse MCP connector shows as present at the account level —
`ListConnectors({keywords:["clickhouse"]})` returned:
```
{"name":"ClickHouse","installState":"connected","connected":true,"enabledInChat":true}
```
—but no ClickHouse tool (`get_organizations`, `get_services_list`, `list_databases`,
`list_tables`, `run_select_query`, etc.) could actually be loaded in this session. Multiple
`ToolSearch` queries ("clickhouse", "+clickhouse", direct `select:mcp__ClickHouse__...` by
name, broader keyword queries, and a retry after an 8s wait) all came back with zero matches.

Per the refresh runbook's explicit instruction ("CHECK CONNECTORS FIRST ... If either is
missing, STOP: write pipeline/BLOCKED.md naming which connector is missing, commit, exit"),
stopping here rather than guessing at ClickHouse data or skipping steps 2/2b/2c/3/4/5/5c
that depend on it.

**Nothing was pulled or changed this run** — no ticket data, no ClickHouse queries, no
pipeline outputs regenerated, no commit beyond this file. The repo's last successful refresh
remains `Refresh 2026-10-19 19:35 IST` (commit `84fc3ad`).

**Next step for a human**: verify the ClickHouse MCP connector session for this environment —
it may need to be re-authorized or the connector session restarted, since the account-level
status says connected/enabled but the tool surface never materialized. Once it's confirmed
working (e.g. a session where `ToolSearch("clickhouse")` or the equivalent returns real
tool schemas), re-run the daily refresh.
