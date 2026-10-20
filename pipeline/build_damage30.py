"""Damage deep dive (last 30 days of customer returns, from 2026-09-20): order-level split + SKU/region/courier
distributions. Inputs under zoho_raw90/: damage30_raw.json (return items), damage30_ship.json (ofd/ndr/region),
damage30_image_buckets.json (hand-read photo codes, priority P>L>O>C>Q>D>N>X), damage30_zoho_live.json.
Codes: P primary pack breached, L leak/spill, O outer shipper damaged, C carton damaged, Q product quality,
D label/closure/device defect, N no visible damage, X image not relevant. Cold = cold reason or cold flag (not photo-read)."""
import json, collections, os
Z = os.path.join(os.path.dirname(__file__), "zoho_raw90")
L = lambda f: json.load(open(os.path.join(Z, f)))
raw = L("damage30_raw.json")["result"]["data"]
ship = {r["order_id"]: r for r in L("damage30_ship.json")["result"]["data"]}
bk = {int(k): v for k, v in L("damage30_image_buckets.json")["order_bucket"].items()}
live = L("damage30_zoho_live.json")
orders = collections.defaultdict(list)
for r in raw: orders[r["order_id"]].append(r)
NAME = dict(P="Primary pack breached", L="Leak / spill", O="Outer shipper damaged", C="Carton damaged",
            Q="Product quality (powder/caking/discoloured)", D="Label / closure / device defect",
            N="No visible damage in photo", X="Image not relevant / unreadable")
out = []
for o, rs in orders.items():
    r0 = rs[0]; s = ship.get(o, {})
    cold = any(r["reason"] == "Issue with cold storage items" or r["cold"] for r in rs)
    cat = "Cold chain (temperature complaint)" if cold else NAME.get(bk.get(o), "No photo on file")
    out.append(dict(order=o, cat=cat, carrier=r0["carrier"] or "none", partner=r0["partner"], region=s.get("region") or "?",
                    tier=s.get("tier") or "?", state=r0["state"], wh=r0["wh"], ndr=(s.get("ndr") or 0) > 0,
                    ofd=(s.get("ofd") or 0) > 1, skus=[r["sku"] for r in rs], refund=sum(float(r["refund"] or 0) for r in rs)))
json.dump(out, open(os.path.join(Z, "damage30_orders.json"), "w"))
C = collections.Counter
n = len(out)
def tab(title, key):
    c = C(key(o) for o in out); print(f"\n{title}"); [print(f"  {str(k):48s}{v:5d} {v/n:6.1%}") for k, v in c.most_common()]
tab("SPLIT", lambda o: o["cat"]); tab("CARRIER", lambda o: o["carrier"]); tab("REGION", lambda o: o["region"])
tab("TIER", lambda o: o["tier"]); tab("STATE (top)", lambda o: o["state"]); tab("WAREHOUSE", lambda o: o["wh"])
print("\nNDR>0:", sum(o["ndr"] for o in out), " OFD>1:", sum(o["ofd"] for o in out), " total", n)
print("\nCATEGORY x CARRIER")
cars = [k for k, _ in C(o["carrier"] for o in out).most_common(5)]
print("  %-46s" % "", *["%10s" % c[:9] for c in cars])
for cat, _ in C(o["cat"] for o in out).most_common():
    print("  %-46s" % cat, *["%10d" % sum(1 for o in out if o["cat"] == cat and o["carrier"] == c) for c in cars])
print("\nCATEGORY x REGION")
regs = ["NORTH", "WEST", "SOUTH", "EAST"]
for cat, _ in C(o["cat"] for o in out).most_common():
    print("  %-46s" % cat, *["%7d" % sum(1 for o in out if o["cat"] == cat and o["region"] == r) for r in regs])
sk = C(); skc = collections.defaultdict(C)
for o in out:
    for s in set(o["skus"]): sk[s] += 1; skc[s][o["cat"]] += 1
print("\nTOP SKUs (orders)")
for s, v in sk.most_common(15): print(f"  {s:40s}{v:4d}  {dict(skc[s].most_common(2))}")
print("\nrefund total", round(sum(o["refund"] for o in out)))
