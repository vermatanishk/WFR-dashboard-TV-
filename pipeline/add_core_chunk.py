"""Write an incremental core chunk ch_{returns,pickers,qc}_c<N>.jsonl + merge cold flags from 4 saved ClickHouse-MCP result files.
usage: python3 pipeline/add_core_chunk.py <N> <returns.txt> <pickers.txt> <qc.txt> <cold.txt>
(build_full_dataset.py: rows of an order present in a chunk >= 4 replace that order's older rows.)"""
import json, sys
from pathlib import Path
HERE = Path(__file__).parent
n = sys.argv[1]
def data(p): return json.loads(Path(p).read_text())["result"]["data"]
spec = [("returns", sys.argv[2], ("order_id", "warehouse_id", "warehouse_name", "city", "remark", "reason")),
        ("pickers", sys.argv[3], ("order_id", "scanned_by_user_id", "picks")),
        ("qc", sys.argv[4], ("order_id", "ops_user_name", "user_id"))]
for name, src, cols in spec:
    rows = data(src)
    with open(HERE / f"zoho_raw90/ch_{name}_c{n}.jsonl", "w") as f:
        for r in rows: f.write(json.dumps({k: r[k] for k in cols}) + "\n")
    print(name, len(rows))
cf = json.loads((HERE / "order_cold_flag.json").read_text())
for r in data(sys.argv[5]): cf[str(r["order_id"])] = bool(r["cold"]) if r["cold"] is not None else None
(HERE / "order_cold_flag.json").write_text(json.dumps(cf)); print("cold flags", len(cf))
