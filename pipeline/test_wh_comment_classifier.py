"""
Fixtures are real Warehouse/L2 comment text pulled from live Zoho tickets
during the 2026-09-21 investigation (exact wording, quoted verbatim) plus
cases documented in pipeline/build_eod.py's dated run notes (quoted there,
reconstructed here as minimal comment objects since the raw API payload
wasn't captured at the time). Every fixture has a known-correct verdict -
either because I read the live comment thread myself, or because an earlier
run's manual/LLM comment read is already recorded in build_eod.py's history.

Run: python3 pipeline/test_wh_comment_classifier.py
"""
from wh_comment_classifier import classify_wh_comments


def wh(text, t="2026-01-01T00:00:00.000Z"):
    return {"content": f"<div>{text}</div>", "commentedTime": t,
            "commenter": {"roleName": "Warehouse "}}


def l2(text, t="2026-01-01T00:00:00.000Z"):
    return {"content": f"<div>{text}</div>", "commentedTime": t,
            "commenter": {"roleName": "L2 Agent"}}


# (ticket_id, comments, expected_verdict) - comments listed in chronological order
CASES = [
    # --- Denials found live, most followed by an L2 BOD/refund note that
    # confirms the denial is what actually happened (the L2 note never
    # overrides - it's just corroboration for the fixture, not the input) ---
    ("256523", [wh("We have sent proper medicine to Cx Mahiboob bee")], "denied"),
    ("255511", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("BOD should give to the Customer / amount 273.47", "2")], "denied"),
    ("256542", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("BOD approved by Nikhil", "2")], "denied"),
    ("256515", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("BOD approved by NIkhil", "2")], "denied"),
    ("256803", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("raised in cx L2 group, checking with shivadhan", "2")], "denied"),
    ("256774", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("BOD need to be initiated to the cx / amount is 357.94", "2")], "denied"),
    ("255934", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("regular cx / BOD need to be initiate to the cx. amount is 410.27", "2")], "denied"),
    ("254439", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("BOD Issued to Customer", "2")], "denied"),
    ("255056", [l2("Warehouse All check and update", "1"),
                wh("We have sent proper medicine to Cx Mahiboob bee", "2"),
                l2("regular cx / BOD Issued to Customer", "3"),
                l2("Refund initiated | TAT 3-4 working days | Closing the ticket", "4")], "denied"),
    ("255182", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("Refund processed | UTR Generated | Closing the ticket", "2")], "denied"),
    ("255005", [l2("Warehouse All kindly check", "1"),
                wh("We have sent proper medicine to Cx Mahiboob bee", "2"),
                l2("First return out of 5 | UTR 667550114235 | Refund is processed to Source", "3")], "denied"),
    ("255030", [l2("Warehouse All check and update", "1"),
                wh("We have sent proper medicine to cx Naveed.", "2"),
                l2("Refund processed | UTR 623611060013", "3")], "denied"),
    ("254960", [wh("We have sent proper medicine to cx Naveed.", "1"),
                l2("Refund initiated - TAT 4-5 W Days. Closing the ticket.", "2")], "denied"),
    ("254968", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("Called Cx - RNR | Refund initiated | TAT 4-5 W-Days", "2")], "denied"),
    ("254955", [wh("We have sent proper medicine to cx Naveen", "1"),
                l2("Refund initiated - TAT 4-5 W-Days. Closing the ticket", "2")], "denied"),
    ("254807", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("Refund initiated - 4-5 working days TAT - Closing the ticket", "2")], "denied"),
    ("254957", [l2("Warehouse All kindly check", "1"),
                wh("We have sent proper medicine to Cx Mahiboob bee", "2"),
                l2("Refund processed. Closing the ticket. TAT 4-5 W-Days", "3")], "denied"),
    ("255006", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("Refund processed | UTR 623316080816 | 4th time Return-Refund Cx", "2")], "denied"),
    ("255010", [l2("Warehouse All kindly check", "1"),
                wh("We have sent proper medicine to Cx Mahiboob bee", "2"),
                l2("Refund processed | Prx cash-Source | Closing the ticket", "3")], "denied"),
    ("254962", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("Refund initiated | 4-5 W-Days TAT | Called Cx - RNR", "2")], "denied"),
    ("254973", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("Refund initiated | 4-5 W-Day TAT | Called Cx to inform - RNR | Closing the ticket", "2")], "denied"),
    ("254681", [wh("We have sent proper medicine to Cx Mahiboob bee", "1"),
                l2("BOD Issued to Customer", "2"),
                l2("Refund initiated | TAT 5-6 W-Days | Closing the ticket", "3")], "denied"),
    ("254475", [l2("Please check and share the packaging footage", "1"),
                wh("We have sent proper medicine to cx Naveen", "2")], "denied"),
    ("254563", [wh("We have sent proper medicine to Cx", "1"),
                wh("We have sent proper medicine to Cx", "2")], "denied"),

    # --- Genuine admissions found live ---
    ("254732", [wh("We have sent short qty to Cx Mahiboob bee")], "admitted"),
    ("256837", [wh("We have sent only 3 qty short oxemia to cx Kindly check the footage ( We also have footage proof )", "1"),
                l2("claim accepted / refund will be initiated shortly", "2")], "admitted"),
    ("256797", [wh("We have sent short qty to Cx Mahiboob bee")], "admitted"),
    ("257048", [wh("We have sent short qty to Cx Mahiboob bee", "1"),
                l2("Refund Processed", "2")], "admitted"),
    ("256334", [wh("We have sent short qty to Cx Mahiboob bee", "1"),
                l2("claim accepted / refund will be process shortly", "2")], "admitted"),
    ("255021", [l2("Warehouse All check and update", "1"),
                wh("We have sent short qty to Cx Mahiboob bee", "2"),
                l2("WH have agreed on short Qty | Refund is processed | TAT 3-4 working days | Closing the ticket", "3")], "admitted"),

    # --- Genuine admissions documented in build_eod.py's run-note history ---
    ("252650", [wh("we have sent short qty to Cx")], "admitted"),
    ("252655", [wh("we have sent short qty to Cx")], "admitted"),
    ("252582", [wh("we have sent short qty to Cx")], "admitted"),
    ("252817", [wh("we have sent short qty to Cx")], "admitted"),
    ("252847", [wh("we have sent short qty to Cx")], "admitted"),
    ("252841", [wh("we have sent wrong sku to Cx")], "admitted"),
    ("253487", [wh("We have sent short qty to cx")], "admitted"),
    ("253532", [wh("We have sent wrong sku to Cx")], "admitted"),
    ("254861", [wh("we have sent wrong sku to Cx")], "admitted"),
    ("255831", [wh("We have sent short qty to Cx")], "admitted"),
    ("256106", [wh("we have sent wrong sku to Cx")], "admitted"),
    ("256576", [wh("We have sent short qty to Cx")], "admitted"),
    ("257161", [wh("We have sent only 1qty short qty to Cx")], "admitted"),
    ("257300", [wh("We have sent short qty to Cx Mahiboob bee")], "admitted"),
    # Non-literal admission via INTENT_OVERRIDE_ADMISSIONS - preceded by a
    # REQUEST comment that must NOT be misread as the final verdict.
    ("257160", [wh("Kindly share proper image of medicine to", "1"),
                wh("We have sent deferent manufacturer company medicine to Cx", "2")], "admitted"),
    # The 254519 "trap": an initial denial, then a LATER genuine admission
    # once evidence was shown - the later comment must win.
    ("254519", [wh("We have sent proper medicine to Cx", "1"),
                wh("we have sent wrong medicine to cx", "2")], "admitted"),

    # --- No Warehouse-role comment at all ---
    ("255356", [l2("Refund Processed")], "no_wh_comment"),
    ("255617", [], "no_wh_comment"),
    ("254415", [], "no_wh_comment"),
    ("255706", [l2("Return Pickup Initiated")], "no_wh_comment"),

    # --- Request/neutral traps: must NOT be misclassified as admitted/denied ---
    # Ticket 248136 (2026-08-01 false positive): a request for evidence that
    # contains the literal admission substring "wrong medicine" - must stay
    # unrecognized, not admitted.
    ("248136", [wh("Kindly share the image of wrong medicine Because it helpfull to find")], "unrecognized"),
    # Batch-disclaim pattern (253213/253629/253634): a denial, then a second
    # WH comment that's a neutral factual note - neutral must not erase the
    # earlier denial verdict.
    ("253634", [wh("We have sent proper medicine to Cx", "1"),
                wh("This batch medicine is not related to our inventory", "2")], "denied"),
    # Pure batch-disclaim with no denial/admission anywhere - unrecognized.
    ("253213", [wh("This batch medicine is not related to our inventory")], "unrecognized"),
    ("254126", [wh("Footage not found because it is under maintenance")], "unrecognized"),
    ("257237", [wh("Footage not found because it is old order")], "unrecognized"),
    ("257363", [l2("Noted. Raised with the carrier", "1"),
                l2("Delivered", "2"),
                wh("Your order id containce only 1qty", "3")], "unrecognized"),
    # WH asks for the order ID first (request), denies once supplied - the
    # request must not block the later denial from being read.
    ("254262", [wh("Share the order id", "1"),
                wh("We have sent proper medicine to Cx", "2")], "denied"),
    ("254720", [wh("Kindly share the order id", "1"),
                wh("We have sent proper medicine to cx", "2")], "denied"),

    # --- More real variants found migrating the legacy cache (2026-09-21) ---
    ("201575", [wh("We have sent sent with ice packs to cx")], "denied"),
    ("230310", [wh("By mistake We have sent damaged medicine to CX")], "admitted"),
    ("253878", [wh("1- 2027 is good expiry medicine")], "denied"),
    ("209498", [wh("This batch is not available in our inventory")], "unrecognized"),
    ("212263", [wh("No batch available in our inventory")], "unrecognized"),
]


def run():
    failures = []
    for ticket_id, comments, expected in CASES:
        result = classify_wh_comments(comments)
        got = result["verdict"]
        status = "OK" if got == expected else "FAIL"
        if got != expected:
            failures.append((ticket_id, expected, got, result["reason"]))
        print(f"[{status}] {ticket_id}: expected={expected} got={got}")

    print(f"\n{len(CASES) - len(failures)}/{len(CASES)} passed")
    if failures:
        print("\nFailures:")
        for ticket_id, expected, got, reason in failures:
            print(f"  {ticket_id}: expected {expected!r}, got {got!r} - {reason}")
        raise SystemExit(1)


if __name__ == "__main__":
    run()
