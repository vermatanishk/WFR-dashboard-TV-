# RCA layer — learnings and decisions (2026-10-14 → 2026-10-15)

Companion to [CLAUDE.md](CLAUDE.md) (how to run the pipeline). This file records **why** the RCA layer is
shaped the way it is: owner decisions, data traps found, and open gaps. Read it before changing the tree.

## 1. What was built
Per raised complaint (one row per **order**, first ticket wins — same as the dashboard's `dedupeByOrder()`):
1. **Investigation funnel** — how the warehouse handled it (outcome-based).
2. **Raised-why tree** — why the issue happened (per category).
3. **Return request state** — Raised / Cancelled / Not raised (global cut, added 2026-10-15).

Surfaces: website Tab 6 "RCA", Tab 7 "RCA view" (day-wise table, same pattern as the Everything-tab macro
table), and a live Google Sheet (Raw data + RCA view) fed from `rca_export.json` in git.

## 2. Architecture decisions
| Decision | Why |
|---|---|
| RCA view = pure function of `rca_export.json` through a declarative layout (`rca_view_spec.py`) | One definition evaluated in Python (site) and Apps Script (sheet); tests prove cell-for-cell equality |
| Export holds IDs, dates, warehouse, bucket labels only | Repo is public — no names, phones or WH comment text |
| Apps Script reads raw.githubusercontent.com + hidden `Spec` tab | Simple `onEdit` triggers cannot call `UrlFetchApp` |
| Counts unique per order | Reconciles with the Everything tab tile (2,199 vs 2,366 mismatch was duplicate tickets) |
| T-2 cap on the view | WH needs ~2 days to comment; newer days are structurally low |
| Return state as a **global filter**, not rows under "No decision" | It is a different question from "how did WH investigate" |
| Zoho Desk = master for issue/investigation data; ClickHouse = evidence (batches, bins, image CDNs) | Owner rule |
| Zoho REST creds in gitignored `pipeline/.zoho.env`; Zoho Desk MCP is the fallback | Repo auto-deploys to Vercel — secrets never committed |

## 3. Investigation funnel rules
- Outcome only: **Accepted / Rejected / No decision / Not yet read**. `Dependency` is *not* a stage (agents
  edit it later); it is shown informationally.
- "Not yet read" = no cached WH verdict — a coverage gap, kept separate from No decision.
- No decision, first match wins: footage not available → batch "not from our inventory" claim → CX image not
  clear (WH said so **or** every image on the return was unreadable) → dependency not marked → return not
  received → other WH note → no WH comment.
- No WH comment, owner rule: not agent-markable as Warehouse when another dependency applies, order COGS < 100
  (allocated qty × `zoho_inward_items.rate`), or DocPharma (warehouse_id 4); otherwise `agent_mistake`.
- Owner-confirmed admissions: MRP mismatch, missing / not-mentioned free item, packer did not remove medicine
  outside, expiry / excess / wrong free item sent.
- **Provisional verdicts must be re-read every refresh** (`recheck_wh_comments.py`). 1,135 of 1,412
  provisional/uncached verdicts had changed (e.g. 233123 admission and 250676 denial were stuck as
  `no_wh_comment`). The no-decision sub-reason is read from **every** WH comment, not the evidence snippet.
- Pair Zoho results to tickets by `ticketNumber`, never by position.

## 4. Raised-why tree (v2)
- **Wrong medicine**: photo read / not available (no return request) / not read yet →
  same SKU shown · same medicine different pack · different medicine (bin link, batch shared) · not readable.
  Bin links attributed as **picking error only** (same bin strong, same rack supporting, same zone+vertical
  weak; zone `UN` is never a bin). Judge **only the SKU in concern** (the ordered return-item SKU); other
  products in the photo are out of scope. Foreign item (not same brand family) rule applied structurally.
- **Expiry**: shelf life at **delivery** (status 70), day-1 expiry = end of month, `<3m` vs `>=3m`. Memo
  "batch/expiry differs from allocation" splits into received item expired / not expired / expiry not legible.
- **Damaged**: 1) cold vs non-cold from the drug flag, 2) images read **only** for non-cold (cold = temperature
  complaint, never image-read), 3) each line gets one of 8 buckets (`damaged_buckets.py`; wrong-item and
  logo-only fold into "Image not relevant"). Logistics exception (NDR/OFD count, delivery attempts) is a memo;
  no exception = *undetermined*, never WH.
- **Missing / short qty**: only the owner's split — SKU missing vs item missing. "Empty box" = missing qty.
  Evidence order: return-item quantities → ticket text → flagged default (`basis` kept). Pick scans are
  deliberately **not** evidence (a scan can be logged for a pick that never happened).
- **Order swap** (courier label order id ≠ ticket) and **MRP/Batch mismatch**: built, populated only after a
  fresh ticket pull (`CATEGORY_MAP` has the MRP labels).
- **Out of scope (owner)**: "Order not placed by customer" — low volume, not a WFR aspect.
- MECE rule: every parent row = sum of children in every column; unread / not-available / undetermined rows
  exist precisely so nothing drops out. Enforced by `test_rca_trend.py`.

## 5. Return request (primary measure)
- Not raised = no `marketplace_return_request` row; Cancelled = every return status in {280 cancelledReturn,
  231 returnPickupCancelled}; Raised = anything else.
- **"Photo not available" = no return request ⇒ no complaint photo exists.** These can never be read.
- Findings (2,193 orders): raised 1,995 · cancelled 45 · not raised 153.
  Dependency-not-marked = 345 → raised 238 (69%), cancelled 25, not raised 82 (24%).
  The owner's hypothesis (user only complained, no request) explains ~a quarter; the larger leak is **238
  raised returns never routed to the warehouse**. 61 tickets are Rejected with no return raised.

## 6. Image reading
- Source: `marketplace_return_items.image_urls` (public `cdn.platinumrx.in`, 1–3 per return item; reason `RTO`
  has none). Fetch/dedupe with `rca_images.py`; each is read by a Claude vision session (2 per contact sheet),
  results hash-keyed in `rca_image_check.json`. Unreadable = null, never inferred; PII never stored.
- Logo placeholder images detected by content hash (6bd60c718ba3, 9a6c99dbb2a9, 1973fd786a10).
- Image-derived verdicts are **capped at "likely"**; accuracy is built over time — lack of evidence does not
  mean the logic is absent. Owner labels live in `rca_manual_labels.json` and override the classifier.
- **Why photos weren't all read**: reading is a manual session step, not an automated reader. The first pass
  covered a 1–21 Sep sample plus all expiry and non-cold damaged; ~400 raised wrong-medicine orders were never
  queued.
- **Decision (2026-10-15): read all images, in batches, scope reduced to the last 60 days (was 90) to save
  compute.** Batch by month; rebuild and push after each batch.
- Observed: many "wrong medicine" returns are really **order swaps** (reason swap/switch, 5–10 lines of one
  order, e.g. 3175757, 3136382). Deriving swap from the return reason is pending an owner decision.

## 7. Data traps (ClickHouse / Zoho)
- Join on `order_id`, never `id`. PeerDB tables: `ORDER BY _peerdb_version DESC LIMIT 1 BY id`, drop
  `_peerdb_is_deleted`. Do **not** filter `is_active` on batch rows (it is 0).
- Return-item `drug_code` is the **ordered** SKU. Images in `image_urls`; `warehouse_image_urls` is empty.
- Zoho `ticketNumber` ≠ internal `id`. `searchTickets` order ≠ input order. `Attribution` is not an outcome.
- Day buckets: UTC date of `created_time`; EOD tab uses IST — a ticket after 18:30 UTC lands on different days.
- Upstream pushes data commits to `main`: fetch + merge (take theirs for generated files) before pushing.

## 8. Tests (run after touching export or layout)
`test_wh_comment_classifier.py`, `test_rca.py`, `test_rca_trend.py` (incl. return states add to All),
`check_view_from_export.py` (independent predicates, ~23.4k cells), `node test_view_js.js`.

## 9. Open items
- Photo reads (60-day scope): wrong medicine, 6 expiry, 26 non-cold damaged.
- ClickHouse inputs for new tickets: 1 COGS meta, 5 missing-qty defaults, 3 expiry orders, cancel codes.
- Order-swap derivation from return reason (owner decision pending).
- No per-field image accuracy figure yet.

## 10. 60-day photo read pass (2026-10-15)
- Scope per owner: all complaint photos for orders created since 2026-08-16 (60 days), in the T-2 window.
  550 image references -> 363 unique files read (identical files are read once; `pipeline/image_reads.py`
  expands a read to every order that carried the file - before this fix a shared file was credited to one order only).
- Result: **0 "photo not read yet" and 0 WH "not yet read" in the 60-day T-2 window**. Wrong-medicine reads moved
  from ~50% to complete; remaining unknown-SKU cases are labelled "Not readable" (no brand on the photo).
- Reads that show no product name are stored with brand null and the description in `notes`
  (never as a brand - descriptions like "white round tablets" were being treated as received brands).
- RTO-only returns are not complaint requests: `rca_return_state_override.json` marks them Not raised
  (order 3910085) so the photo row says "not available" instead of "not read yet".
- Catalog bin candidates (`rca_wrongmed_raw.jsonl`) were pulled for 95 order/brand pairs; where the catalog
  has no candidate with a bin at the order's warehouse the bin link stays "Bin not assessed".
- Orders created 2026-10-14 are outside T-2 (held back) and still carry unread photos; they enter on the next refresh.
- **View window = 60 days (fix 2026-10-15):** the export and Tab 7 still carried July 16 - Aug 15 rows whose photos
  were deliberately not read, so "Photo not read yet" kept showing (214 rows). `build_rca_export.py` now keeps only
  orders created in the last 60 days (`WINDOW_DAYS`), so the website, the sheet's Raw data tab and every test see
  the same window. Result: 1,440 orders, 0 unread photos in the T-2 window.
- **Wrong-SKU classes split MECE (owner, 2026-10-15):** "same family medicine", "different
  medicine" and "Not readable" each break into bin picking issue (incl. bin + batch both) / batch sharing
  issue (batch only) / other (no structural link or not assessable). Most land in "other" today because the
  catalog candidate bin at the order's warehouse was not found/verified for ~114 entries; batch sharing needs
  `rca_wrongmed_rca.json` for the new window. This is an evidence gap, not an absence of the issue.
- **Bin + batch pull for the 60-day window (2026-10-15):** `rca_wrongmed_cand_raw.json` holds, per (order, ordered
  drug, received brand), up to 6 same-brand catalog candidates with their bin at the order's warehouse and the
  count of OTHER orders where that candidate was allocated a batch number also carried by this order's ordered line.
  `build_rca_wrongmed.py` keeps only candidates that agree with every strength/number read off the pack, takes the
  strongest bin relation, and records `batch_shared_orders` (>=1 counts as batch sharing; export threshold changed
  from >1). Result for the window: same-medicine-different-pack 15 bin / 4 batch / 36 other; different medicine
  5 bin / 3 batch / 85 other (37 confirmed no structural link, 48 not assessable - no verified candidate with a bin).
  The Apps Script evaluator is layout-driven, so no script change is needed: run `refreshAll` after the push.
  Re-run this pull each refresh (query shape: see this section; pairs come from the wrongmed entries in the window).
- **Naming (owner, 2026-10-15):** the wrong-SKU classes are "Same family medicine" (same brand; strength, pack
  size, drug form or variant word differs - e.g. Aloja 12.5 vs 25, Accu-Chek Active vs Instant, Lotion vs Cream),
  "Different medicine" and "Not readable". "Same family" is not limited to a different pack form.
- **Cascade rule (owner, 2026-10-15):** every deep dive is placed directly below its parent metric, indented one level per step, no exceptions. Enforced in `rca_view_spec._cascade()` (depth-first order, indent and arrow derived from the parent chain; asserts every row has a known parent). Web indent is 18px per level, the Sheet uses 3 spaces per level.

## 11. Return-request outcome (holistic view, 2026-10-15)
- The return-request cut now has five outcomes per order (`rca_return_outcome_raw.json`, ClickHouse DTO return
  requests + items): **Raised - Accepted & refunded** (facility QC 250 / refund approved 245-247, nothing rejected),
  **Raised - Cancelled** (cancelledReturn 280 / returnPickupCancelled 231), **Raised - Rejected** (QC 250 with at
  least one rejected item), **Raised - In progress** (requested / pickup / transit / validation) and **Not raised**
  (no customer DTO request; RTO-only returns are not complaints).
- Bug fixed: the old Raised/Cancelled/Not raised cut only knew cancel codes for orders pulled earlier, so 181
  cancelled returns were shown as "Raised". Cancelled is now 213 in the 60-day window (was 30).
- ClickHouse cannot tell who cancelled (customer vs system): 280 `cancelledReturn` is the only code; labelled
  "Cancelled", not "customer-initiated".
- Window mix (1,440 orders): accepted & refunded 984 (68%), cancelled 213 (14%), rejected 57 (4%), in progress
  72 (5%), not raised 114 (8%). 739 of the 1,020 tickets WH *rejected* were still refunded (BOD) - refund is not
  evidence of a WH fault.
