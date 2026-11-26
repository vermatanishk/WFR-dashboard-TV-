"""
Root-cause analysis for EVERY in-scope WFR complaint (owner, 2026-11-27): the union of ClickHouse return requests and Zoho tickets, not only
the ticketed ones. Each complaint (order x type) gets  bucket 1 = the FIRST cut  and  bucket 2 = the SECOND cut (reason); the Warehouse
outcome (accepted / rejected / no comment) is the complaint's own "WH input" column, so every cut is shown with its accept / reject pattern.

WRONG MEDICINE  (needs the customer photo: the received SKU exists nowhere in the system - `is_extra_drug_item` is never set)
  cut 1  intended SKU (ordered return-item SKU) vs actual SKU (read off the photo):
         LASA           different brand, look-alike / sound-alike name (name similarity >= 0.70 or same consonant skeleton), different active salt
         Same family    same brand (other strength / pack / form) OR the same active salt under another brand
         Different      nothing in common
         + coverage buckets: photo shows the ordered SKU | photo not legible / ordered SKU not photographed | no photo (ticket only)
  cut 2  reason (LASA / same family / different only):  bin sharing (same bin or rack at the order's warehouse, only with a catalog candidate
         that matches every strength read off the pack)  >  batch overlap (the batch printed on the received pack = the batch allocated to the ordered SKU)  >  other
MISSING / SHORT QTY  (return-item quantities; a ticket-only complaint falls back to the ticket text, then a flagged default)
  cut 1  SKU missing (a line claims >= its ordered quantity = zero units sent) | Item missing (partial quantity)
  cut 2  pack quantity confusion (GRN inwarded in pack units: a GRN before the complaint with qty = pack size x open PO qty, or the catalog / MDM pack
         definition disagrees with the pack-mapping workbook)  >  single-vs-pack error (item missing on a multipack SKU: pack of N strips, customer
         counted strips / WH sent one pack unit)  >  counting issue (everything else; "confirmed" when the Warehouse admitted it)
EXPIRY  (marketplace_order_item_batches: batch expiry vs allocation time, every complaint)
  cut 1  expired at allocation | near expiry at allocation (<= 6 months of shelf life; day-1 expiry = end of that month) | allocation correct (> 6 months) and still a complaint
  cut 2  the batch of the complained SKU carries MULTIPLE expiries in the warehouse batch inventory (different year-month = the "inverting" / data-entry error) | other

Image reads are capped at "likely"; unreadable = not determinable, never inferred. Inputs missing for a complaint -> bucket "Inputs pending" (gate).
"""
import difflib
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from build_rca_inputs import bin_relation
from build_rca_wrongmed import FORM_WORDS, PRODUCT_TYPES, STOP, brand_token, candidate_verified, head, relation, same_brand, split_products, toks
from image_reads import reads_by_order

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"

WM_LASA = "LASA (look-alike / sound-alike)"
WM_FAM = "Same family (same brand or same active salt)"
WM_DIFF = "Completely different medicine"
WM_SAME = "Photo shows the ordered SKU (complaint not supported)"
WM_NL = "Photo not legible / ordered SKU not in photo"
WM_NP = "No photo (ticket only, no return request)"
WM_BIN, WM_BATCH, WM_OTH = "Bin sharing (same bin / rack)", "Batch overlap", "Other (no bin or batch link)"
MQ_SKU, MQ_ITEM = "SKU missing (zero units sent)", "Item missing (partial quantity)"
MQ_PACK, MQ_SINGLE, MQ_COUNT = "Pack quantity confusion (GRN / catalog)", "Single vs pack error (multipack SKU)", "Counting issue"
EX_EXP, EX_NEAR, EX_OK = "Expired at allocation", "Near expiry at allocation (<= 6 months)", "Allocation correct (> 6 months), complaint raised"
EX_MULTI, EX_OTH = "Batch has multiple expiries in the system", "Other (single expiry on record)"
ND = "Not determinable"
OLD = "Older than the 60-day RCA window (not analysed)"
WINDOW_DAYS = 60
PENDING = "Inputs pending"

COLS = ["WFR cut 1", "WFR cut 2", "WFR cut detail", "WFR cut basis"]
# complaint type -> [(first cut, [second cut values])]; the funnel layout is generated from this
TREE = {
    "Wrong medicine": [(WM_LASA, [WM_BIN, WM_BATCH, WM_OTH]), (WM_FAM, [WM_BIN, WM_BATCH, WM_OTH]), (WM_DIFF, [WM_BIN, WM_BATCH, WM_OTH]),
                       (WM_SAME, []), (WM_NL, []), (WM_NP, []), (PENDING, []), (OLD, [])],
    "Missing / short qty": [(MQ_SKU, [MQ_PACK, MQ_SINGLE, MQ_COUNT, ND, PENDING]), (MQ_ITEM, [MQ_PACK, MQ_SINGLE, MQ_COUNT, ND, PENDING]), (OLD, [])],
    "Expiry": [(EX_EXP, [EX_MULTI, EX_OTH]), (EX_NEAR, [EX_MULTI, EX_OTH]), (EX_OK, [EX_MULTI, EX_OTH]), (ND, []), (PENDING, []), (OLD, [])],
}

STOPSALT = {"tablets", "tablet", "capsules", "capsule", "solution", "cream", "gel", "oral", "release", "sustained", "extended", "delayed", "topical",
            "injection", "with", "and", "drops", "syrup", "powder", "lotion", "ointment", "sachet", "ophthalmic", "film", "coated", "chewable", "dispersible"}


def _js(name, default=None):
    p = RAW / name
    return json.loads(p.read_text()) if p.exists() else default


def _salt_tokens(s):
    return {t for t in re.findall(r"[a-z]{5,}", (s or "").lower()) if t not in STOPSALT}


def _skeleton(b):
    return re.sub(r"[aeiouyhw]", "", re.sub(r"(.)\1+", r"\1", b.lower()))


def squash(s):
    """Brand key ignoring spacing / hyphens / form words: 'Flexipep G' == 'Flexi Pep-G'."""
    extra = {"sachet", "sachets", "nasal", "ear", "oral", "jelly", "suspension", "injection", "inhaler", "tab", "tabs", "cap"}
    return "".join(t for t in toks(head(s)) if t.isalpha() and t not in STOP and t not in FORM_WORDS and t not in extra)


def lasa_like(a, b):
    a, b = brand_token(a), brand_token(b)
    if not a or not b or a == b:
        return False
    r = difflib.SequenceMatcher(None, a, b).ratio()
    return r >= 0.70 or (len(a) >= 5 and len(b) >= 5 and _skeleton(a) == _skeleton(b))


def _rows(name):
    d = _js(name, {"result": {"data": []}})
    return d["result"]["data"] if isinstance(d, dict) and "result" in d else d


class Inputs:
    def __init__(self):
        self.reads = reads_by_order()
        self.lines = _js("rca_order_lines.json", {})
        self.ordered = {(r["order_id"], r["drug_code"]): r for r in _rows("wfr_wm_ordered.json")}
        self.batches = {(r["order_id"], r["drug_code"]): r for r in _rows("wfr_wm_batches.json")}
        self.cand = defaultdict(list)
        for r in _rows("wfr_wm_candidates.json"):
            self.cand[r["brand"]].append(r)
        imgs = defaultdict(int)
        p = RAW / "rca_return_images_raw.jsonl"
        if p.exists():
            for l in p.read_text().splitlines():
                if l.strip():
                    x = json.loads(l)
                    imgs[x["order_id"]] += len(x.get("image_urls") or [])
        self.images = imgs
        self.mq = defaultdict(list)
        for r in _js("wfr_mq_lines.json", []):
            self.mq[r["order_id"]].append(r)
        self.pack = _js("pack_mapping_subset.json", {})
        grn = _js("wfr_grn_store.json", {"checked_codes": [], "rows": []})
        self.grn_checked = {int(c) for c in grn["checked_codes"]}
        self.grn = defaultdict(list)
        for r in grn["rows"]:
            self.grn[int(r["code"])].append(r)
        done = _js("wfr_inputs_done.json", {})
        self.done = {k: set(done.get(k, [])) for k in ("wm", "mq", "exp")}
        self.brands_done = set(done.get("wm_brands", []))
        self.text_kind = _js("rca_missing_text_kind.json", {})
        self.pack_text = _js("mq_pack_text_flags.json", {})
        self.exp = defaultdict(list)
        for r in _js("wfr_exp_batches.json", []):
            self.exp[r["order_id"]].append(r)


# ------------------------------------------------------------------------------------------------ wrong medicine
def _received_products(inp, order):
    out = []
    for r in inp.reads.get(order, []):
        if r.get("brand") and r.get("image_type") in (PRODUCT_TYPES | {"other"}):
            for p in split_products(r["brand"]):
                out.append((p, r))
    return out


def wm_one(inp, order, drug, has_return):
    o = inp.ordered.get((order, drug)) or {}
    oname = o.get("ordered_name") or ""
    prods = _received_products(inp, order)
    if not oname:
        return [PENDING, "", "ordered SKU name missing", "none"]
    if not prods:
        if not has_return:
            return [WM_NP, "", "", "none"]
        if inp.images.get(order) and not any(r.get("image_type") for r in inp.reads.get(order, [])):
            return [PENDING, "", "photo not read yet", "none"]
        return [WM_NL, "", "no legible product name on the photos", "photo"]
    lines = [n for _, n in inp.lines.get(str(order), [])]
    foreign = []
    for p, r in prods:
        if brand_token(p) and not any(same_brand(n, p) for n in lines) and not any(same_brand(f[0], p) for f in foreign):
            foreign.append((p, r))
    mine = [(p, r) for p, r in prods if same_brand(oname, p)]
    if foreign:
        f, fr = foreign[0]
        ftext = f + " " + (fr.get("strength") or "")
        if brand_token(f) not in inp.brands_done:
            return [PENDING, "", "catalog candidates for received brand '" + brand_token(f) + "' not pulled yet", "none"]
        cands = [c for c in inp.cand.get(brand_token(f), []) if candidate_verified(ftext, c["name"])]
        c = cands[0] if cands else None
        fsalt = _salt_tokens((fr.get("strength") or "") + " " + " ".join(re.findall(r"\(([^)]*)\)", f))) | (_salt_tokens(c["salt"]) if c else set())
        shared = _salt_tokens(o.get("salt")) & fsalt
        if shared:
            b1, why = WM_FAM, "same active salt: " + ", ".join(sorted(shared)[:2])
        elif lasa_like(oname, f):
            b1, why = WM_LASA, f"{brand_token(oname)} / {brand_token(f)} look or sound alike"
        else:
            b1, why = WM_DIFF, "no shared salt, dissimilar name"
        # cut 2: bin sharing > batch overlap > other
        b2, b3 = WM_OTH, why
        if c:
            locs = {l.split(":", 1)[0]: l.split(":", 1)[1] for l in (c.get("locs") or []) if ":" in l}
            br = bin_relation(o.get("ordered_loc"), locs.get(str(o.get("wh"))))
            if br[0] in ("picking_error", "picking_error_nearby"):
                return [b1, WM_BIN, br[1], "likely"]
        norm = lambda s: re.sub(r"[^A-Z0-9]", "", (s or "").upper())
        alloc = {norm(b) for b in (inp.batches.get((order, drug)) or {}).get("batches", [])}
        if fr.get("batch") and norm(fr["batch"]) in alloc:
            return [b1, WM_BATCH, "printed batch " + fr["batch"] + " = allocated batch of the ordered SKU", "likely"]
        return [b1, b2, b3 if c else why + "; no verified catalog candidate for the bin check", "likely"]
    if mine:
        full = max(mine, key=lambda x: len(x[0]))[0]
        rel = relation(oname, full)
        if rel == "same_brand_variant" and squash(oname) == squash(full):
            rel = "same_sku_consistent"
        if rel == "same_sku_consistent":
            return [WM_SAME, "", "", "likely"]
        return [WM_FAM, WM_OTH, "same brand, different strength / pack / form", "likely"]
    return [WM_NL, "", "only other lines of the order are in the photo", "photo"]


def wm_complaint(inp, order, drugs, has_return):
    if order not in inp.done["wm"]:
        return [PENDING, "", "wrong-medicine inputs (ordered SKU / photo reads / batches) not pulled yet", "none"]
    if not drugs:
        return [WM_NP if not has_return else PENDING, "", "", "none"]
    res = [wm_one(inp, order, d, has_return) for d in drugs]
    rank = {WM_LASA: 0, WM_FAM: 1, WM_DIFF: 2, WM_SAME: 3, WM_NL: 4, WM_NP: 5, PENDING: 6}
    return min(res, key=lambda r: rank.get(r[0], 9))


# ------------------------------------------------------------------------------------------------ missing quantity
def mq_complaint(inp, order, drugs, ticket, wh_input, date_str):
    if order not in inp.done["mq"]:
        return [PENDING, PENDING, "return-item lines of the order not pulled yet", "none"]
    from build_complaints import reason_type
    ls = [x for x in inp.mq.get(order, []) if reason_type(x["reason"]) == "Missing / short qty" and (not drugs or x["drug_code"] in drugs)]
    if ls:
        sku = any((x["ret_qty"] or 0) >= (x["order_qty"] or 1) for x in ls)
        b1, basis = (MQ_SKU if sku else MQ_ITEM), "return item quantities"
    elif ticket and str(ticket) in inp.text_kind:
        k = inp.text_kind[str(ticket)]
        b1, basis = (MQ_SKU if k["kind"] == "sku_missing" else MQ_ITEM), "ticket text"
    else:
        b1, basis = MQ_ITEM, "default (no quantity detail)"
    if not ls:
        return [b1, ND, "SKU not identified (no return line on the order)", basis]
    codes = sorted({x["drug_code"] for x in ls if x["drug_code"]})
    if any(c not in inp.pack and c not in inp.grn_checked for c in codes):
        return [b1, PENDING, "pack mapping / GRN pull pending for " + ",".join(str(c) for c in codes if c not in inp.pack and c not in inp.grn_checked)[:60], basis]
    inward = conflict = False
    multipack = False
    for x in ls:
        c = x["drug_code"]
        m = inp.pack.get(str(c))
        cur = int(float(x["pack_qty"])) if x.get("pack_qty") is not None else None
        nm = x.get("name") or (m or {}).get("name") or ""
        mm = re.search(r"(\d+)\s*[Xx*]\s*[\d.]", nm)
        if m:
            base, xl = m["base"], m["xl"]
            ratio = max(xl, cur or xl) / max(min(xl, cur or xl), 1e-9)
            if abs(xl - (cur if cur is not None else xl)) > 1e-9 and (base > 1 or ratio >= 2):
                conflict = True
            if mm and int(mm.group(1)) > 1 and base == 1:
                conflict = True
            multipack = multipack or m["sp"] == "Pack"
        multipack = multipack or bool(mm and int(mm.group(1)) > 1)
        ps = {p for p in ((m or {}).get("base"), cur) if p and p > 1}
        for g in inp.grn.get(int(c), []):
            q, po = g["grn_qty"], g["open_po_qty"]
            if po and q and str(g["grn_date"])[:10] <= date_str and any(abs(q / po - p) < 1e-9 or abs(po / q - p) < 1e-9 for p in ps):
                inward = True
    sig = set((inp.pack_text.get(str(ticket)) or {}).get("signals") or []) if ticket else set()
    tflag = bool(sig)                       # any pack / strip count in the ticket text (supporting evidence)
    tstrong = bool(sig & {"pack_of", "combo"})   # the customer describes a pack / combo: multipack even if the mapping says Single
    if inward:
        return [b1, MQ_PACK, "GRN inwarded in pack units (grn qty = pack size x PO qty) before the complaint", basis]
    if conflict:
        return [b1, MQ_PACK, "catalog / MDM pack definition disagrees with the pack mapping", basis]
    if b1 == MQ_ITEM and (multipack or tstrong):
        return [b1, MQ_SINGLE, ("multipack SKU" if multipack else "ticket text describes a pack / combo") +
                ("; ticket text mentions strips / pack count" if tflag and multipack else ""), basis]
    return [b1, MQ_COUNT, "confirmed by the Warehouse" if wh_input == "WH accepted" else "by elimination (no pack or inward flag)", basis]


# ------------------------------------------------------------------------------------------------ expiry
def _exp_date(s):
    d = datetime.strptime(s[:10], "%Y-%m-%d")
    if d.day == 1:                                       # day-1 expiry = end of that month
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return d


def exp_complaint(inp, order, drugs):
    if order not in inp.done["exp"]:
        return [PENDING, "", "batch allocation / expiry rows of the order not pulled yet", "none"]
    rows = [r for r in inp.exp.get(order, []) if r["drug_code"] in drugs]
    if not drugs:
        return [ND, "", "no return item / SKU", "none"]
    if not rows:
        return [ND, "", "no batch allocation row on record for the complained SKU", "none"]
    worst = None
    for r in rows:
        alloc = datetime.strptime(r["alloc_at"][:10], "%Y-%m-%d")
        left = (_exp_date(r["expiry"]) - alloc).days
        if worst is None or left < worst[0]:
            worst = (left, r)
    left, r = worst
    b1 = EX_EXP if left < 0 else EX_NEAR if left <= 183 else EX_OK
    ym = {e[:7] for e in (r.get("inv_expiries") or [])} | {r["expiry"][:7]}
    if len(ym) > 1:
        return [b1, EX_MULTI, f"batch {r['batch']}: expiries on record {', '.join(sorted(ym))}", "system data"]
    return [b1, EX_OTH, f"batch {r['batch']}: {left} days of shelf life at allocation", "system data"]


# ------------------------------------------------------------------------------------------------ entry point
def analyse(complaints):
    """complaints: [{order, type, drugs, has_return, ticket, wh, date}] -> {(order, type): [b1, b2, b3, basis]}"""
    inp = Inputs()
    out = {}
    for c in complaints:
        t, o = c["type"], c["order"]
        if t == "Wrong medicine":
            r = wm_complaint(inp, o, c["drugs"], c["has_return"])
        elif t == "Missing / short qty":
            r = mq_complaint(inp, o, set(c["drugs"]), c["ticket"], c["wh"], c["date"])
        elif t == "Expiry":
            r = exp_complaint(inp, o, set(c["drugs"]))
        else:
            continue
        out[(o, t)] = r
    return out
