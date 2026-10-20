"""
Extends zoho_raw90/rca_pickcheck.json `picked_full` ({order_id: 'S' | 'I'}) for orders not yet covered, from the
return-item pull rca_missing_items_raw.json (ClickHouse, return requests since 2026-08-10, see RCA doc section 12).
S = some "Incomplete Order" line claims >= its ordered quantity (whole line = SKU missing); I = partial (item missing).
Validated against the original pick-scan based labels: 792 of 805 orders agree. Existing entries are never overwritten.
Run: python3 pipeline/update_pickcheck.py   (before build_rca_extra.py)
"""
import json
from collections import defaultdict
from pathlib import Path

RAW = Path(__file__).parent / "zoho_raw90"


def main():
    d = json.loads((RAW / "rca_missing_items_raw.json").read_text())["result"]["data"]
    p = json.loads((RAW / "rca_pickcheck.json").read_text())
    by = defaultdict(list)
    for r in d:
        if r["reason"] == "Incomplete Order":
            by[str(int(r["order_id"]))].append(r)
    added = 0
    for o, ls in by.items():
        if o not in p["picked_full"]:
            p["picked_full"][o] = "S" if any((x["ret_qty"] or 0) >= (x["order_qty"] or 1) for x in ls) else "I"
            added += 1
    (RAW / "rca_pickcheck.json").write_text(json.dumps(p))
    print("pickcheck: added", added, "orders; total", len(p["picked_full"]))


if __name__ == "__main__":
    main()
