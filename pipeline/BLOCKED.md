# Daily refresh BLOCKED — 2026-09-19 run

**Missing connector: ClickHouse MCP** (needed for steps 2, 2b, 2c, 3, 4, 5b, 5c of the
daily refresh — the entire ClickHouse-side join/aggregation work).

## What was checked

- `ListConnectors` reports ClickHouse as `connected: true` and `enabledInChat: true`
  (directoryUuid `01adc2b5-5676-4dda-9e32-2cce63929d5c`, installedServerId
  `145a2230-60f9-4ee9-88d9-96747c090568`), so the org-level connection looks fine.
- However, no ClickHouse tool is actually exposed to this session. Checked the full
  deferred-tools listing given at session start (no `mcp__ClickHouse__*` entries at
  all) and tried `ToolSearch` with many query variants — "clickhouse", "query database
  sql", "run_select_query", "list_databases list_tables", "ClickHouse Cloud data
  explore", "+ClickHouse", and direct name guesses (`mcp__ClickHouse__run_select_query`,
  `run_query`, `list_databases`, `list_tables`) — all returned "No matching deferred
  tools found".
- Zoho Desk MCP tools (`mcp__Zoho_Desk__*`) ARE available and working (searchTickets,
  getTicketComments, etc. all present) — only ClickHouse is affected.

## What this blocks

Everything in the daily refresh that touches `prx_prod_db` — the returns/pickers/QC
join, cold-chain classification, the WH-text admission fallback's ClickHouse-remark
pass, personnel roster totals, orders-volume denominators, EOD tab location/picker/
packer/QC/manifester attribution, and (today isn't relevant since 2026-09-19 is not a
Sunday) the weekly RFD pipeline. None of this can be computed without ClickHouse.

## Not attempted

No partial refresh was run and no files were regenerated — running build_full_dataset.py
etc. without fresh ClickHouse data would either crash on stale/missing input files or,
worse, silently republish yesterday's numbers relabeled as today's. Per the project's
own instructions ("never publish stale or fabricated numbers"), the safer failure is to
stop here untouched rather than half-refresh.

## To unblock

A human needs to re-enable/reconnect the ClickHouse MCP connector for this session (or
this Claude Code environment's connector wiring) so a `mcp__ClickHouse__*` tool actually
appears — the org-level "connected" status above is not sufficient on its own. Once a
ClickHouse tool is available, this file can be deleted and the run retried from step 1.

Last known-good dashboard data is still the 2026-09-18 19:29 IST refresh (commit
`fe34321`) — the live site is one day stale, not broken.
