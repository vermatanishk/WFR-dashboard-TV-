"""Run: python3 pipeline/test_rca.py - golden fixtures for build_rca_inputs.py"""
from datetime import date
from build_rca_inputs import bin_relation, shelf_verdict, effective_expiry
from build_rca_wrongmed import relation, candidate_verified
from build_rca_extra import mrp_batch_verdict

BIN = [
    # 4129639 (WH1, live ClickHouse 2026-10-14): Amlip AT 5/50 vs Ecosprin 75.
    # Same zone+vertical, different rack; both relocated within 3 minutes of
    # each other. Manual RCA called this "bin proximity"; under the decided
    # rule it is a (weak, nearby) picking error - never a layout error.
    ("4129639", "A1-6-1-1", "A1-6-3-1", "picking_error_nearby"),
    ("same-bin", "E1-8-3-1", "E1-8-3-1", "picking_error"),
    ("same-rack", "E1-8-3-1", "E1-8-3-2", "picking_error"),
    ("different", "E1-8-3-1", "C1-2-2-2", "no_bin_link"),
    ("UN-zone", "UN-1-1-1", "UN-1-1-1", "unknown"),
    ("missing", None, "A1-6-1-1", "unknown"),
]
SHELF = [
    # (delivered, expiry as stored, expected bucket)
    (date(2026, 7, 4), "2026-07-01", "near_expiry_lt_3m"),   # 258DB2422: 07/2026 print, valid to 31 Jul
    (date(2026, 6, 24), "2026-08-01", "near_expiry_lt_3m"),  # T40818A
    (date(2026, 7, 20), "2026-10-01", "shelf_life_ge_3m"),   # CU405: 103 days to month end
    (date(2026, 7, 4), "2026-06-30", "outright_expired"),
    (date(2026, 8, 1), "2027-11-01", "shelf_life_ge_3m"),
]


REL = [
    # (ordered name, received read, expected) - real cases from the 2026-10-14 image read
    ("Maxmoist Ultra 0.3% Eye Drop 10ml", "Maxmoist Ultra eye drops 10 ml", "same_sku_consistent"),
    ("Miragron 50mg Tablet ER 10s", "Miragron ER 25 (mirabegron 25 mg, Steris)", "same_brand_variant"),
    ("Pynomax Tx Lotion 100ml", "Pynomax-Tx Cream SPF 50 (Galcare)", "same_brand_variant"),
    ("Cefyclav 200/125mg Tablet 6s", "Cefasyn 250 (cefuroxime axetil 250 mg, Cipla)", "different_medicine"),
    ("Rosugard 10mg Tablet 10s", "Rosugard 10 (rosuvastatin 10 mg, Cipla)", "same_sku_consistent"),
    ("Extend Hair Tablet 10s", "Extend Total (multivitamin/multimineral/antioxidant, KLM)", "same_brand_variant"),
]


def run():
    bad = 0
    # MRP/batch: Aptamil Gold 1 (ticket 259643) - pack 960 vs system 1010, batch differs
    v = mrp_batch_verdict({"batch": "2604147901", "mrp": 1010}, {"batch": "2512147901", "mrp": 960})
    assert v["mrp_relation"] == "system_higher_than_pack" and v["mrp_delta"] == 50 and v["batch_relation"] == "differs", v
    assert mrp_batch_verdict({"batch": "ABC1", "mrp": 100}, {"batch": "ABC1", "mrp": 100})["verdict"].startswith("consistent")
    assert mrp_batch_verdict({"batch": "ABC1", "mrp": None}, {"batch": "ABC1", "mrp": 90})["mrp_relation"] == "unknown"
    print("[OK] mrp_batch_verdict")
    for ordered, got_s, want in REL:
        got = relation(ordered, got_s)
        bad += got != want
        print(f"[{'OK' if got == want else 'FAIL'}] rel {ordered[:28]!r} vs {got_s[:30]!r} -> {got} (want {want})")
    assert candidate_verified("Cefasyn 250 (cefuroxime)", "Cefasyn 250mg Tablet 4s")
    assert not candidate_verified("Aptamil Premium 1 (infant formula)", "Aptamil Preterm Powder 400gm")
    for name, a, b, want in BIN:
        got = bin_relation(a, b)[0]
        bad += got != want
        print(f"[{'OK' if got == want else 'FAIL'}] bin {name}: {a} vs {b} -> {got} (want {want})")
    for deliv, exp, want in SHELF:
        got = shelf_verdict(exp, deliv)[0]
        bad += got != want
        print(f"[{'OK' if got == want else 'FAIL'}] shelf {exp} @ {deliv} -> {got} (want {want})")
    assert effective_expiry("2027-11-01")[0] == date(2027, 11, 30)
    assert effective_expiry("2027-01-12")[0] == date(2027, 1, 12)
    print(f"\n{len(BIN) + len(SHELF) + len(REL) - bad}/{len(BIN) + len(SHELF) + len(REL)} passed")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
