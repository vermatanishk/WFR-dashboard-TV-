"""
Append-only archive of every export row ever produced (owner, 2026-11-20: "ensure we don't delete old data - anything behind L60 days;
cache and save it, process only incrementally new data").

The reporting views show the last 60 days, but the exports (complaints / WFR / damage / swap / RCA) are rebuilt from raw inputs on every
refresh and rows that fall out of a window used to vanish from the files (and from the Google Sheet raw tabs, which were cleared and
re-written). This script keeps `pipeline/archive/<name>_archive.json` = {columns, key_cols, rows}: an UPSERT of every export row by its
business key. Rows are only added or refreshed with the latest version, NEVER deleted; new columns are appended at the end. The Google
Sheet (gsheet/Code.gs) reads the same archive files, so its raw tabs are archive U export.

  python3 pipeline/archive_exports.py          # upsert all exports (run at the end of refresh_all.py build)
  python3 pipeline/archive_exports.py check    # gate: archive covers every export row and never shrank

Keys: complaints-style exports (Order ID + Complaint type), swap/RCA exports (Order ID + Ticket ID / Order ID).
Public repo: the exports contain only IDs, dates and bucket labels - the archive adds nothing more.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ARCH = HERE / "archive"
# name -> key columns
EXPORTS = {
    "complaints_export": ("Order ID", "Complaint type"),
    "cmp_wfr_export": ("Order ID", "Complaint type"),
    "cmp_damage_export": ("Order ID", "Complaint type"),
    "cmp_swap_baseline_export": ("Order ID", "Complaint type"),
    "swap_export": ("Order ID", "Ticket ID"),
    "rca_export": ("Order ID", "Ticket ID"),
}


def _key(cols, row, key_cols):
    return "|".join(str(row[cols.index(k)]) for k in key_cols)


def load_archive(name):
    p = ARCH / f"{name}_archive.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"columns": [], "key_cols": list(EXPORTS[name]), "rows": [], "max_rows_seen": 0}


def upsert(name):
    exp = json.loads((HERE / f"{name}.json").read_text())
    arch = load_archive(name)
    cols = list(arch["columns"])
    for c in exp["columns"]:
        if c not in cols:
            cols.append(c)                      # new columns are appended, old ones never dropped/reordered
    widen = len(cols) - len(arch["columns"])
    rows = [r + [""] * widen for r in arch["rows"]]
    keys = list(EXPORTS[name])
    index = {_key(cols, r, keys): i for i, r in enumerate(rows)}
    added = updated = 0
    for r in exp["rows"]:
        rec = {c: v for c, v in zip(exp["columns"], r)}
        new = [rec.get(c, "") for c in cols]
        k = _key(cols, new, keys)
        if k in index:
            old = rows[index[k]]
            # keep a previously known value where the new export is blank (a column the export no longer carries)
            merged = [n if n not in ("", None) else o for n, o in zip(new, old)]
            if merged != old:
                updated += 1
            rows[index[k]] = merged
        else:
            index[k] = len(rows)
            rows.append(new)
            added += 1
    out = {"columns": cols, "key_cols": keys, "rows": rows, "max_rows_seen": max(arch.get("max_rows_seen", 0), len(rows)),
           "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source_t2_cap_date": exp.get("t2_cap_date")}
    ARCH.mkdir(exist_ok=True)
    (ARCH / f"{name}_archive.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"{name}: archive {len(rows)} rows (+{added} new, {updated} refreshed, export {len(exp['rows'])})")
    return out


def check():
    bad = []
    for name in EXPORTS:
        p = ARCH / f"{name}_archive.json"
        if not p.exists():
            bad.append(f"{name}: archive missing")
            continue
        arch = json.loads(p.read_text())
        exp = json.loads((HERE / f"{name}.json").read_text())
        keys = EXPORTS[name]
        have = {_key(arch["columns"], r, keys) for r in arch["rows"]}
        miss = [r for r in exp["rows"] if _key(exp["columns"], r, keys) not in have]
        if miss:
            bad.append(f"{name}: {len(miss)} export rows not in the archive (run archive_exports.py)")
        if len(arch["rows"]) < arch.get("max_rows_seen", 0):
            bad.append(f"{name}: archive SHRANK ({len(arch['rows'])} < {arch['max_rows_seen']})")
    return bad


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        b = check()
        print("archive intact" if not b else "\n".join(b))
        sys.exit(1 if b else 0)
    for n in EXPORTS:
        upsert(n)
