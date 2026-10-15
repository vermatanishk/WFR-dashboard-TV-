"""Merge session vision reads (idx|brand|strength|maker|batch|expiry|mrp|type|brand_legibility|note) into
zoho_raw90/rca_image_check.json. Args: reads.txt order.json"""
import json, sys, datetime as d
from pathlib import Path
reads, order = sys.argv[1], sys.argv[2]
order = json.load(open(order))
p = Path(__file__).parent / "zoho_raw90/rca_image_check.json"
db = json.load(open(p))
n = 0
for line in open(reads):
    f = line.rstrip("\n").split("|")
    if len(f) < 10: continue
    i = int(f[0]); o = order[i]
    nz = lambda s: s or None
    note = f[9]
    if f[1].startswith("(") or f[1].split("|")[0].strip().lower().startswith(("multiple","unnamed","blue","green","red","white","pink","yellow","silver","brown","maroon","empty","displayed","partly","soft","one","blister","back","beside","others")):
        note = (f[1] + "; " + f[9]).strip("; ")   # no usable product name on the photo: keep the description, never as a brand
        f[1] = ""
    lvl = f[8] or "none"
    lg = lambda v: (("high" if lvl in ("high","medium") else "low") if v else "none")
    batch, exp = nz(f[4]), nz(f[5])
    db[o["hash"]] = {"order_id": o["order_id"], "drug_code_ordered": o["drug_code_ordered"],
        "image_type": f[7] or "other", "brand": nz(f[1]), "strength": nz(f[2]), "pack": None, "maker": nz(f[3]),
        "batch": batch, "mfg": None, "expiry": exp, "mrp": nz(f[6]),
        "legibility": {"brand": lvl, "batch": "high" if batch else "none", "expiry": "high" if exp else "none"},
        "notes": note, "read_by": "claude-session", "read_on": d.date.today().isoformat()}
    n += 1
p.write_text(json.dumps(db))
print("merged", n, "total", len(db))
