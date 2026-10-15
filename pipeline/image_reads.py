"""Image reads keyed by ORDER. rca_image_check.json is keyed by image content hash and stores the
first order that carried the file; identical files (logo placeholders, re-uploaded photos, the same
carton photographed for two orders) are read once. This expands every read to every order whose
return line carried that file (via rca_image_index.json url->hash and rca_return_images_raw.jsonl)."""
import json
from pathlib import Path

RAW = Path(__file__).parent / "zoho_raw90"


def reads_by_order():
    checks = json.loads((RAW / "rca_image_check.json").read_text())
    idx = json.loads((RAW / "rca_image_index.json").read_text()) if (RAW / "rca_image_index.json").exists() else {}
    out, seen = {}, set()
    for h, r in checks.items():
        out.setdefault(r["order_id"], []).append(r)
        seen.add((r["order_id"], h))
    p = RAW / "rca_return_images_raw.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            for u in row.get("image_urls") or []:
                h = idx.get(u)
                if h in checks and (row["order_id"], h) not in seen:
                    seen.add((row["order_id"], h))
                    out.setdefault(row["order_id"], []).append({**checks[h], "order_id": row["order_id"]})
    return out
