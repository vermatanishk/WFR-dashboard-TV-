"""
Image step of the RCA pipeline: fetch + dedupe + pending-manifest. It does NOT
read images - in this repo the daily refresh is a Claude Code session (see
CLAUDE.md), so the session reads each pending image with its own vision and
appends a structured result to zoho_raw90/rca_image_check.json.

Source of URLs: ClickHouse marketplace_return_items.image_urls (public
https://cdn.platinumrx.in/meds-prescription/<uuid>_cs.jpeg, 2-3 per order, no
auth). The session saves the pull to zoho_raw90/rca_return_images_raw.jsonl:
    {"order_id","drug_code","reason","image_urls":[...]}
  `drug_code` on a return item is the ORDERED SKU (verified on 4129639:
  1305281 = Amlip AT) - the received SKU can only come from the image.
Skip reason `RTO` rows at pull time (no images, not complaints).

Images are stored by content hash under zoho_raw90/rca_images/ which is
gitignored: customer photos can show invoices, names and addresses and must
never be committed or surfaced in reports.

Result schema (rca_image_check.json, key = sha256[:16] of the image bytes):
  {"order_id", "drug_code_ordered", "image_type": strip|carton|invoice|bottle|other,
   "brand": str|null, "strength": str|null, "pack": str|null, "maker": str|null,
   "batch": str|null, "mfg": str|null, "expiry": str|null, "mrp": str|null,
   "legibility": {"brand": high|medium|low|none, "batch": ..., "expiry": ...},
   "notes": str, "read_by": "claude-session", "read_on": "YYYY-MM-DD"}
Rules: unreadable -> null with legibility none, NEVER inferred; two close
catalog variants -> note "ambiguous", never a silent pick; people are never
named. Image-derived verdicts are capped at `likely` until a per-field
accuracy number exists (rca_image_pilot in the plan).

Run: python3 pipeline/rca_images.py   -> downloads new images, prints pending
"""
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
IMG_DIR = RAW / "rca_images"


def main():
    IMG_DIR.mkdir(exist_ok=True)
    src = RAW / "rca_return_images_raw.jsonl"
    checks_p = RAW / "rca_image_check.json"
    checks = json.loads(checks_p.read_text()) if checks_p.exists() else {}
    index_p = RAW / "rca_image_index.json"   # url -> hash, so re-runs don't re-download
    index = json.loads(index_p.read_text()) if index_p.exists() else {}
    pending, fetched, failed = [], 0, 0
    for line in src.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        for url in r["image_urls"]:
            h = index.get(url)
            if h is None:
                try:
                    b = urllib.request.urlopen(url, timeout=30).read()
                except Exception:
                    failed += 1
                    continue
                h = hashlib.sha256(b).hexdigest()[:16]
                (IMG_DIR / f"{h}.jpeg").write_bytes(b)
                index[url] = h
                fetched += 1
            if h not in checks:
                pending.append({"hash": h, "order_id": r["order_id"], "drug_code_ordered": r["drug_code"],
                                "reason": r["reason"], "path": str(IMG_DIR / f"{h}.jpeg")})
    index_p.write_text(json.dumps(index))
    (RAW / "rca_image_pending.json").write_text(json.dumps(pending))
    print(f"fetched {fetched}, failed {failed}, already read {len(checks)}, pending {len(pending)}")


if __name__ == "__main__":
    main()
