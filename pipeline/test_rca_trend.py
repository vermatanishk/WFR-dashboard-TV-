"""Run: python3 pipeline/test_rca_trend.py - every parent row of rca_trend.json must equal the sum of its
children in EVERY column (3mo / 1mo / 2wk / each day). Added after the first version failed three of these."""
import json
from pathlib import Path

R = json.loads((Path(__file__).parent / "rca_trend.json").read_text())
rows = R["rows"]
lab = [r["label"].strip() for r in rows]


def col(i):
    r = rows[i]
    return [r["3mo"]["n"], r["1mo"]["n"], r["2wk"]["n"]] + [r["daily"][d]["n"] for d in R["days"]]


def ix(l, start=0):
    return lab.index(l, start)


def chk(name, parent, children):
    P = col(parent)
    C = [sum(x) for x in zip(*[col(c) for c in children])]
    bad = [(i, p, c) for i, (p, c) in enumerate(zip(P, C)) if p != c]
    print(("OK  " if not bad else "FAIL"), name, bad[:3])
    return not bad


ok = True
nd = ix("No decision"); wm = ix("Wrong medicine"); wr = ix("↳ photo read", wm); ex = ix("Expiry")
dm = ix("Damaged"); nc = ix("↳ non-cold"); ncr = ix("↳ photo read", nc); mq = ix("Missing / short quantity")
ok &= chk("raised = accepted + rejected + no decision + not yet read", 0, [ix("WH Accepted"), ix("WH Rejected"), nd, ix("Not yet read")])
ok &= chk("no decision reasons", nd, list(range(nd + 1, nd + 10)))
ok &= chk("no decision return state", nd, [ix("↳ return raised"), ix("↳ return cancelled"), ix("↳ return request not raised")])
ok &= chk("wrong medicine read / unread", wm, [wr, ix("↳ photo not read yet", wm)])
ok &= chk("wrong medicine read children", wr, [ix("↳ photo shows the ordered SKU"), ix("↳ same medicine, different pack form"), ix("↳ different medicine"), ix("↳ SKU name not readable")])
ok &= chk("expiry allocation split", ex, [ex + 1, ex + 2, ex + 3, ex + 4])
ok &= chk("expiry photo read / unread", ex, [ex + 5, ex + 6])
ok &= chk("expiry photo outcomes", ex + 5, [ex + 7, ex + 8, ex + 9, ex + 10, ex + 11])
ok &= chk("damaged cold / non-cold", dm, [ix("↳ cold chain"), nc])
ok &= chk("non-cold read / unread", nc, [ncr, ix("↳ photo not read yet", nc)])
ok &= chk("non-cold buckets", ncr, list(range(ncr + 2, ncr + 10)))
ok &= chk("missing qty = SKU missing + item missing", mq, [mq + 1, mq + 2])
ok &= chk("categories add to raised", 0, [wm, ex, dm, mq, ix("Order swap"), ix("MRP / batch mismatch")])
raise SystemExit(0 if ok else 1)
