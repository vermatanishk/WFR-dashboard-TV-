"""
Ticket-text scan for single-vs-pack / pack-quantity patterns on missing / short qty complaints (owner, 2026-11-27) -> zoho_raw90/mq_pack_text_flags.json.
A multipack SKU (e.g. a packet of 2 strips x 15 tablets) is a classic mis-count: the customer ordered "2 strips" / "a pack of 3" and received one unit.
Zoho Desk REST description / subject wildcards over the window; only ticket ids + matched pattern kinds are stored - never the text (public repo).
Run: python3 pipeline/scan_pack_text.py [days=75]   (incremental: merges into the stored file, never drops)
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pull_swap_tickets import search

HERE = Path(__file__).parent
OUT = HERE / "zoho_raw90/mq_pack_text_flags.json"
QUERIES = [("description", "*strip*"), ("description", "*pack of*"), ("description", "*packet*"), ("description", "*combo*"),
           ("description", "*box of*"), ("description", "*only one*"), ("description", "*only 1*"), ("description", "*pack*"),
           ("subject", "*strip*"), ("subject", "*pack*")]
PATTERNS = {
    "count_of_units": re.compile(r"\b(\d+|one|two|three|four|five|six)\s*(strips?|packs?|packets?|boxes|box|bottles?|sachets?)\b", re.I),
    "pack_of": re.compile(r"\b(pack|box|packet) of \d+", re.I),
    "only_one": re.compile(r"\bonly\s+(one|1|two|2)\b", re.I),
    "combo": re.compile(r"\b(combo|multipack|multi-pack|twin ?pack|family pack)\b", re.I),
    "fewer_than_ordered": re.compile(r"(ordered|order)\s*(for)?\s*(\d+|one|two|three)\b.{0,60}(received|got|delivered|sent)\s*(only)?\s*(\d+|one|two)", re.I),
}


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 75
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    found = {}
    d = start
    while d <= end:
        e = min(d + timedelta(days=2), end)
        for field, pat in QUERIES:
            for t in search(field, pat, d.isoformat(), e.isoformat()):
                found.setdefault(t["ticketNumber"], t)
        print(d, e, len(found), flush=True)
        d = e + timedelta(days=1)
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    for tn, t in found.items():
        text = re.sub(r"<[^>]+>", " ", (t.get("subject") or "") + " " + (t.get("description") or ""))
        text = re.sub(r"Contact No:\s*\d+", " ", text)
        sig = sorted(k for k, rx in PATTERNS.items() if rx.search(text))
        out[tn] = {"signals": sig, "pack_pattern": bool(sig), "created": t["createdTime"][:10],
                   "sub_disposition": (t.get("cf") or {}).get("cf_sub_disposition")}
    OUT.write_text(json.dumps(out, separators=(",", ":"), sort_keys=True))
    print("tickets scanned", len(found), "with a pack pattern", sum(1 for v in out.values() if v["pack_pattern"]))


if __name__ == "__main__":
    main()
