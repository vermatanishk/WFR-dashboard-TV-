"""
Wrong-medicine RCA -> zoho_raw90/rca_wrongmed.json, keyed by order_id.

Owner rules (2026-10-14): for a wrong-medicine complaint ONLY the received SKU
NAME is needed (read off the customer's photo); batch/expiry are a bonus from
the back of the pack, never required. If only the SKU name is legible the RCA
runs on the name alone.

Inputs
  rca_return_images_raw.jsonl / rca_image_check.json  - received brand per order (vision read)
  rca_wrongmed_raw.jsonl - one row per (order, ordered drug, received brand) from ClickHouse:
      ordered name + bin from mdm_drug_warehouse_locations (the order's warehouse), and the
      best catalog candidate for the received brand (shortest display_name starting with the
      brand) with ITS bin. Return-item `drug_code` is the ORDERED SKU.

Per (order, ordered drug) result:
  relation_type: same_sku_consistent  - the photo shows the ordered product (complaint not supported by the photo)
                 same_brand_variant   - same brand, different strength / pack / form  (tree: "same medicine, different pack form")
                 different_medicine   - different brand
                 unknown              - no legible received SKU name
  bin_relation:  from build_rca_inputs.bin_relation(), computed ONLY when the catalog candidate is
                 verified (every numeric/alpha token read off the pack appears in the candidate's name);
                 otherwise 'candidate_unverified' - never a guessed bin link.
All image-derived => strength 'likely' at most.
"""
import json
import re
from pathlib import Path

from build_rca_inputs import bin_relation

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
PRODUCT_TYPES = {"strip", "carton", "bottle", "tube", "ampoule", "can", "cartridge"}
FORM_WORDS = {"cream", "lotion", "gel", "tablet", "tablets", "capsule", "capsules", "syrup", "soap",
              "shampoo", "powder", "solution", "serum", "spray", "drops", "kit", "ointment"}
STOP = {"tablet", "tablets", "capsule", "capsules", "ip", "of", "and", "mg", "ml", "gm", "s", "tabs",
        "strip", "strips", "test", "only", "drop", "drops", "eye", "new", "baby", "bar", "oil", "g", "x", "per",
        "hair", "growth", "control", "fall", "hairfall", "chek", "softgel", "softgels", "protein", "powder", "jar",
        "cap", "caps", "sr", "er", "xr", "cr", "dr", "pr"}


def head(s):
    """The printed product name only - drop the '(composition, maker)' tail of a read."""
    return re.split(r"[(\[]", s or "")[0]


def toks(s):
    t = re.findall(r"[a-z]+|\d+(?:\.\d+)?", (s or "").lower())
    while t and t[0] in ("new", "the"):   # marketing prefixes: 'New Maxmoist Ultra' is Maxmoist
        t = t[1:]
    return t


def brand_token(s):
    t = toks(s)
    return t[0] if t else ""


def relation(ordered_name, received_full):
    ot, rt = toks(ordered_name), toks(head(received_full))
    if not rt:
        return "unknown"
    if not ot or not same_brand(ordered_name, received_full):
        return "different_medicine"
    onum = {t for t in ot if re.fullmatch(r"\d+(?:\.\d+)?", t)}
    rnum = {t for t in rt if re.fullmatch(r"\d+(?:\.\d+)?", t)}
    oform = FORM_WORDS & set(ot)
    rform = FORM_WORDS & set(rt)
    if rform and oform and not (rform & oform):
        return "same_brand_variant"
    if rnum and onum and not (rnum <= onum):
        return "same_brand_variant"
    # extra distinguishing words on only one side (e.g. 'Total' vs 'Hair', 'Gold' vs none)
    oword = {t for t in ot[1:] if t.isalpha() and t not in STOP and t not in FORM_WORDS}
    rword = {t for t in rt[1:] if t.isalpha() and t not in STOP and t not in FORM_WORDS}
    # any distinguishing word present on only one side (Active vs Instant, Sugar Free, Gold, Total ...)
    if (rword ^ oword) - {"mg", "mcg", "iu"}:
        return "same_brand_variant"
    return "same_sku_consistent"


def candidate_verified(received_full, cand_name):
    need = [t for t in toks(head(received_full))[1:] if t not in STOP and t not in FORM_WORDS and (t.isdigit() or len(t) >= 4)]
    cn = " ".join(toks(cand_name))
    return bool(cand_name) and all(t in cn for t in need)


def same_brand(a, b):
    """'Accuchek Instant Kit' and 'Accu-Chek Instant S' are the same brand family; compare the
    first two alphabetic tokens joined, not just the first token."""
    ta = [t for t in toks(head(a)) if t.isalpha()][:2]
    tb = [t for t in toks(head(b)) if t.isalpha()][:2]
    if not ta or not tb:
        return False
    ka, kb = "".join(ta), "".join(tb)
    return ta[0] == tb[0] or ka.startswith(kb[:7]) or kb.startswith(ka[:7])


def split_products(read):
    """A single photo read can name several products ('A; B', 'A and B', 'A with an X carton').
    Split at top level (outside parentheses) so each product is judged separately."""
    parts, depth, cur = [], 0, ""
    i = 0
    while i < len(read):
        ch = read[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if depth == 0 and (ch in ";," or read[i:i + 5].lower() == " and "):
            parts.append(cur.strip()); cur = ""; i += 1 if ch in ";," else 5; continue
        cur += ch
        i += 1
    parts.append(cur.strip())
    NOT_PRODUCT = {"shipper", "invoice", "label", "bag", "bubble", "wrap", "box", "pack", "photo", "hand"}
    out = []
    for p in parts:
        if toks(p) and toks(p)[0] in NOT_PRODUCT:
            continue
        p = re.sub(r"\b(cartons?|strips?|boxes|box|three|two)\b", "", p, flags=re.I).strip(" ,")
        if p and brand_token(p):
            out.append(p)
    return out


def main():
    checks = json.loads((RAW / "rca_image_check.json").read_text())
    lines = json.loads((RAW / "rca_order_lines.json").read_text())
    recv = {}
    for r in checks.values():
        if r.get("brand") and r.get("image_type") in PRODUCT_TYPES:
            for prod in split_products(r["brand"]):
                recv.setdefault(r["order_id"], []).append(prod)
    rows = [json.loads(l) for l in (RAW / "rca_wrongmed_raw.jsonl").read_text().splitlines() if l.strip()]
    # One entry per (order, ordered return-item SKU). The photographed products are evaluated against
    # THAT SKU only (owner rule): the best same-brand product decides same / variant; if none of the
    # photographed products is of the ordered brand, the received item is a different medicine.
    out = {}
    cand_rows = {}
    for r in rows:
        cand_rows.setdefault((r["order_id"], r["drug_code"]), []).append(r)
    for (oid, drug), crs in cand_rows.items():
        o = str(oid)
        name, oloc = crs[0]["ordered_name"], crs[0]["ordered_loc"]
        prods = recv.get(oid, [])
        mine = [p for p in prods if same_brand(name, p)]
        if mine:
            full = max(mine, key=lambda b: (len(set(toks(head(b))) & set(toks(name))), len(b)))
            rel = relation(name, full)
        elif prods:
            full, rel = "; ".join(dict.fromkeys(prods)), "different_medicine"
        else:
            full, rel = None, "unknown"
        entry = {"ordered_drug": drug, "ordered_name": name, "received": full, "relation_type": rel, "strength": "likely"}
        if rel in ("same_brand_variant", "different_medicine"):
            # catalog candidate for the first received product that has a candidate row
            pick = next((c for c in crs if c["cand"] and any(brand_token(c["brand"]) == brand_token(x) for x in ([full] if mine else prods))), None)
            if pick and candidate_verified(full if mine else next(x for x in prods if brand_token(x) == brand_token(pick["brand"])), pick["cand_name"]):
                br = bin_relation(oloc, pick["cand_loc"])
                entry.update({"candidate": pick["cand_name"], "ordered_loc": oloc, "candidate_loc": pick["cand_loc"],
                              "bin_relation": br[0], "bin_why": br[1], "bin_strength": br[2]})
            else:
                entry["bin_relation"] = "candidate_unverified"
        out.setdefault(o, []).append(entry)
    # one best entry per ordered drug: prefer the received item that matches by brand
    best = {}
    for o, es in out.items():
        per = {}
        for e in es:
            k = e["ordered_drug"]
            rank = {"same_sku_consistent": 0, "same_brand_variant": 1, "different_medicine": 2, "unknown": 3}[e["relation_type"]]
            if k not in per or rank < per[k][0]:
                per[k] = (rank, e)
        best[o] = [v[1] for v in per.values()]
    # STRUCTURAL foreign-item rule (owner, 2026-10-14): a photographed product whose brand is not on ANY
    # line of the order was physically delivered in error -> that product is the received wrong SKU.
    # Other products of the same brand family as an ordered line (same-brand items delivered with the
    # rest of the order) are not foreign, and other ordered lines in frame are ignored.
    for o, es in best.items():
        ordered_names = [n for _, n in lines.get(o, [])]
        foreign = []
        for prod in recv.get(int(o), []):
            if brand_token(prod) and not any(same_brand(n, prod) for n in ordered_names) \
               and not any(same_brand(f, prod) for f in foreign):
                foreign.append(prod)
        for e in es:
            e["foreign_items"] = foreign
            photographed_any = any(same_brand(e["ordered_name"], p) for p in recv.get(int(o), []))
            if foreign:
                e["relation_type"] = "different_medicine"
                e["received"] = "; ".join(foreign)
                e["basis"] = "foreign_item_not_on_order"
            elif e["ordered_name"] and not photographed_any and e["relation_type"] != "unknown":
                e["relation_type"] = "other_order_line_photographed"
                e["basis"] = "ordered SKU not in photo; only other lines of the order"
    # Owner-confirmed labels override the image classifier (and are the ground truth for any
    # future accuracy measurement). Rule from the owner: evaluate only the SKU in concern -
    # the ordered return-item SKU - other products in the same photo are out of scope.
    lp = RAW / "rca_manual_labels.json"
    if lp.exists():
        for o, lab in json.loads(lp.read_text()).items():
            ents = best.get(o) or [{"ordered_drug": None, "ordered_name": None}]
            best[o] = [{**{k: e.get(k) for k in ("ordered_drug", "ordered_name")},
                        "received": lab.get("received"), "relation_type": lab["relation_type"],
                        "strength": "confirmed", "source": "owner", "note": lab.get("note"),
                        "bin_relation": None} for e in ents]
    # Verified bin / batch-sharing RCA for different-medicine cases (rca_wrongmed_rca.json, saved from
    # the ClickHouse MCP): bin relation via bin_relation(); batch sharing = the ordered line's allocated
    # batch number of THIS order also appears on the received SKU in other orders (one-off text
    # coincidences between unrelated SKUs are common, so it is only reported, never a verdict alone).
    rp = RAW / "rca_wrongmed_rca.json"
    if rp.exists():
        extra = json.loads(rp.read_text())
        for o, es in best.items():
            for e in es:
                x = extra.get(f"{o}|{e.get('ordered_drug')}")
                if x and e.get("relation_type") in ("different_medicine", "same_brand_variant"):
                    e.update({k: v for k, v in x.items() if v is not None})
    (RAW / "rca_wrongmed.json").write_text(json.dumps(best))
    from collections import Counter
    flat = [e for es in best.values() for e in es]
    print(len(best), "orders;", dict(Counter(e["relation_type"] for e in flat)))
    print("bin:", dict(Counter(e.get("bin_relation") for e in flat if e["relation_type"] in ("same_brand_variant", "different_medicine"))))
    for e in flat:
        if e.get("bin_relation") in ("picking_error", "picking_error_nearby"):
            print("  ", e["ordered_name"], "->", e["candidate"], e["ordered_loc"], e["candidate_loc"], e["bin_relation"])


if __name__ == "__main__":
    main()
