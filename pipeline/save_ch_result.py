"""Save a ClickHouse-MCP result file (auto-saved when >100k chars) as a pipeline raw file.
usage: python3 pipeline/save_ch_result.py <tool-results file> <dest under zoho_raw90/> [--keep-pad]
Writes {"result": {...}} like the existing cmp_returns_*.json files; drops any 'pad' column used to force the file save."""
import json, sys
from pathlib import Path
src, dest = sys.argv[1], sys.argv[2]
d = json.loads(Path(src).read_text())["result"]
for r in d["data"]:
    r.pop("pad", None)
Path(__file__).parent.joinpath("zoho_raw90", dest).write_text(json.dumps({"result": d}))
print(dest, len(d["data"]), "rows")
