"""
Photo step of the Order damage tab. Same contract as rca_images.py: the daily refresh is a Claude Code session that READS the
photos with its own vision (nothing is inferred by code), this script only fetches, dedupes, builds contact sheets and merges.

  1. build_complaints.py marks physical-damage complaints with a return request but no read as "Photo not read yet"
     -> zoho_raw90/damage_pending_orders.json  (list of order ids, written by `pending`)
  2. ClickHouse pull for those orders (return items: order_id, drug_code, reason, image_urls; pad column forces a saved file)
     -> zoho_raw90/damage_images_raw.json   (public cdn.platinumrx.in URLs; images never committed, rca_images/ is gitignored)
  3. python3 pipeline/damage_images.py sheets [OUT_DIR]   downloads by content hash, writes 4-image contact sheets sNNN.jpg + order.json
  4. the session reads every sheet and writes `IDX CODE` lines (codes below) to a text file
  5. python3 pipeline/damage_images.py merge OUT_DIR/codes.txt   -> damage30_image_buckets.json (order bucket = highest-priority code
     over the order's photos: P > L > O > C > Q > D > N > X)  then re-run build_complaints.py

Codes: P primary pack breached | L leak/spill | O outer shipper damaged | C carton damaged | Q product quality | D label/closure/device
       N no visible damage | X image not relevant / unreadable.   Only the complained SKU matters; never name a person.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
PRIO = "PLOCQDNX"


def sheets(out):
    from PIL import Image, ImageDraw
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    idx_p = RAW / "rca_image_index.json"
    index = json.loads(idx_p.read_text()) if idx_p.exists() else {}
    img_dir = RAW / "rca_images"; img_dir.mkdir(exist_ok=True)
    pend = set(json.loads((RAW / "damage_pending_orders.json").read_text()))
    sel, seen = [], set()
    for r in json.loads((RAW / "damage_images_raw.json").read_text())["result"]["data"]:
        if r["order_id"] not in pend:
            continue
        for u in json.loads(r["image_urls"] or "[]"):
            h = index.get(u)
            if h is None:
                try:
                    b = urllib.request.urlopen(u, timeout=30).read()
                except Exception:
                    continue
                h = hashlib.sha256(b).hexdigest()[:16]
                (img_dir / f"{h}.jpeg").write_bytes(b)
                index[u] = h
            if (r["order_id"], h) not in seen:
                seen.add((r["order_id"], h)); sel.append([r["order_id"], h])
    idx_p.write_text(json.dumps(index))
    sel.sort()
    W, H = 640, 540
    for s in range(0, len(sel), 4):
        sh = Image.new("RGB", (W * 2, H * 2), "white"); d = ImageDraw.Draw(sh)
        for j, (o, h) in enumerate(sel[s:s + 4]):
            try:
                im = Image.open(img_dir / f"{h}.jpeg").convert("RGB"); im.thumbnail((W - 4, H - 24))
            except Exception:
                continue
            x, y = (j % 2) * W, (j // 2) * H
            sh.paste(im, (x + 2, y + 20)); d.text((x + 4, y + 4), f"#{s + j} o{o}", fill="black")
        sh.save(out / f"s{s // 4:03d}.jpg", quality=80)
    (out / "order.json").write_text(json.dumps({"sel": sel}))
    print(len(sel), "images in", (len(sel) + 3) // 4, "sheets ->", out)


def merge(codes_file):
    out = Path(codes_file).parent
    sel = json.loads((out / "order.json").read_text())["sel"]
    codes = {int(a): b for a, b in (l.split() for l in Path(codes_file).read_text().splitlines() if l.strip())}
    assert sorted(codes) == list(range(len(sel))), "every image index must have exactly one code"
    assert set(codes.values()) <= set(PRIO), set(codes.values())
    p = RAW / "damage30_image_buckets.json"
    d = json.loads(p.read_text())
    base = max((int(k) for k in d["image_codes"]), default=-1) + 1
    per = {}
    for i, (o, h) in enumerate(sel):
        d["image_codes"][str(base + i)] = {"order": o, "hash": h, "code": codes[i]}
        per.setdefault(o, []).append(codes[i])
    for o, cs in per.items():
        d["order_bucket"][str(o)] = next(c for c in PRIO if c in cs)
    p.write_text(json.dumps(d))
    uni = RAW / "damage30_orders.json"
    print("merged", len(sel), "images,", len(per), "orders; total orders with a bucket:", len(d["order_bucket"]))


if __name__ == "__main__":
    if sys.argv[1] == "sheets":
        sheets(sys.argv[2] if len(sys.argv) > 2 else str(HERE / "damage_sheets"))
    else:
        merge(sys.argv[2])
