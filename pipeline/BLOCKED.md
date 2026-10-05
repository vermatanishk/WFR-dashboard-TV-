# Daily refresh BLOCKED — 2026-10-05 ~19:00 IST

**Blocker:** Zoho Desk MCP connector is connected, but the tools this
pipeline depends on for reading ticket comment text are unavailable.

The MCP tool loader reports these Zoho Desk tools excluded at schema
validation (duplicate `required` entries in `path_variables`, rejected by
the Anthropic API before the tool ever reaches this session):

- `getTicketComments` — used by step 2c (90-day WH-text admission
  backfill) and step 5 (EOD T-2 tab) to read a ticket's Warehouse-role
  comments
- `getTicketComment`, `getTicketConversations`, `getThread`, `getThreads`
  — no viable fallback for reading comment text either
- also excluded, not used by this pipeline: `getTicket`, `getContact`,
  `getAccount`, `getTicketsByContact`, `getTicketsMetrics`, `getTask`

Confirmed via `ToolSearch` (`select:mcp__Zoho_Desk__getTicketComments`) —
returns no matching tool, i.e. it isn't just slow to connect, it's excluded
for this session entirely.

**Why this stops the whole run, not just part of it:** per CLAUDE.md, the
wh_accepted/bod/considered_bod classification (the core of this dashboard)
is decided *entirely* by reading each ticket's actual Warehouse-role Zoho
comment text — there is deliberately no ClickHouse-remark fallback anymore
(removed 2026-09-21 specifically because it produced ~80% wrong verdicts).
Without `getTicketComments` there is no way to do step 2c's backfill or
step 5's EOD tab without guessing, which the brief explicitly forbids
("never take a shortcut where the spec calls for reading actual text").
Running steps 1/2/3/4 alone and skipping 2c/5/5b would also leave
`wh_text_check.json` un-grown and `data_eod.json` stale/missing for
today's T-2 date, silently degrading Tab 1 and Tab 2 without any record of
why — worse than not refreshing at all.

**Action needed:** a human needs to look at why these Zoho Desk MCP tool
schemas are being rejected (likely a server-side definition bug — same
duplicate-`required`-items issue across all of them) and get
`getTicketComments` working again. No workaround was attempted (no raw
API calls, no alternate auth) per standing instructions.

No pipeline steps were run this session. No data files were modified.
