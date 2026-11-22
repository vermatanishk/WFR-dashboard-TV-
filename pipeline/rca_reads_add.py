"""Append vision reads to rca_sheets/reads.jsonl (guarantees exactly 10 fields). Input on stdin: lines  idx|brand|strength|maker|batch|expiry|mrp|type|legibility|note  with up to 10 fields (missing trailing fields padded)."""
import json, sys
out = open("rca_sheets/reads.jsonl", "a")
for ln in sys.stdin:
    ln = ln.rstrip("\n")
    if not ln.strip(): continue
    f = ln.split("|")
    if len(f) > 10: f = f[:9] + ["|".join(f[9:])]
    f += [""] * (10 - len(f))
    out.write(json.dumps(f) + "\n")
