# WFR Dashboard - Handover

Ops dashboard for PlatinumRX warehouses: mis-shipment / wrong-fulfillment complaints (wrong item, short qty,
expiry, damage, swap), who admitted fault vs benefit-of-doubt (BOD), and root causes.

- **Live site:** `index.html` at repo root, auto-deployed by Vercel on push to `main`
  (repo `vermatanishk/WFR-dashboard-TV-`). No CI config.
- **Google Sheet mirror:** Apps Script (`pipeline/gsheet/Code.gs`) reads JSONs from GitHub raw and rebuilds tabs daily.
- **No cron / GitHub Action.** "Refresh" = a Claude Code session that pulls data via MCP, runs the scripts, commits, pushes.

## Read in this order
1. [01_HOW_TO_RUN.md](01_HOW_TO_RUN.md) - setup, daily refresh, tests, deploy
2. [02_FILE_MAP.md](02_FILE_MAP.md) - which file does what
3. [03_KEY_LOGIC_AND_TRAPS.md](03_KEY_LOGIC_AND_TRAPS.md) - definitions and gotchas that bite
4. Deep docs (repo root): `CLAUDE.md` (authoritative, most current), `RCA_Learnings_and_Decisions.md`,
   `RFD_Adherence_Logic_Documentation.md`, `pipeline/gsheet/README.md`.
   `Mis-shipment_Dashboard_Requirements.md` is the original spec and is **stale** in places.

## Dashboard tabs
Tab 1 Everything (tiles, macro trend, ticket list) | EOD (T-2 text admissions) | personnel leaderboards |
RFD adherence | 6 RCA (ticket-level detail) | 7 WFR funnel | 8 Order swap | 9 Order damage | 10 Summary.

## Out of scope for this handover
Untracked experiments in the folder, unrelated to the dashboard build: `Model dev/`, `Video detection system/`,
`weights/`, `runs/`, `PRx pNPS Dashboard.xlsx`. `deliverables_private/` holds one-off leadership docs.
(`pipeline/scan_damage_video.py` is the only video-related script the pipeline touches.)

## Access you need (not in the repo)
- GitHub push access to the repo; Vercel project linked to it.
- MCP connectors: **Zoho Desk** and **ClickHouse** (`prx_prod_db`, read-only).
- `pipeline/.zoho.env` (Zoho REST credentials; gitignored - get from the current owner; **never commit**; repo is public).
  The token cache `pipeline/.zoho_token.json` regenerates itself.
- Google account that owns the Sheet (to re-paste `Code.gs` when it changes).
