"""
Classifies a ticket's Warehouse-team ("roleName": "Warehouse ") Zoho comments
as an admission of fault (WH shipped the wrong/short thing) or a denial
("We have sent proper medicine to Cx"). This is the ONLY signal that actually
attributes a mis-shipment mistake - the ClickHouse marketplace_return_request
remark is a separate, back-office field populated when the physical return is
processed, and was found (2026-09-21 investigation) to disagree with the WH
team's own comment on ~80% of tickets nobody had manually spot-checked, almost
always in the direction of crediting the warehouse when it had explicitly
denied fault.

Seeded from pipeline/build_eod.py's ADMISSION_PHRASES/REQUEST_PHRASES lists
(built up over ~15 dated EOD-tab run notes of real trap cases) plus every
example found live during the 2026-09-21 investigation. See
test_wh_comment_classifier.py for the real, documented cases this is
validated against - extend both files together when a new trap phrase shows
up, never just patch classify_wh_comments() without adding its fixture.
"""
from __future__ import annotations

import re

# ---- Phrase tables -----------------------------------------------------
#
# Order of evaluation matters (see classify_one_comment): a REQUEST can
# contain an ADMISSION-looking substring - e.g. "kindly share the image of
# wrong medicine" is the WH team asking for photo evidence, not admitting
# they sent the wrong medicine (confirmed false-positive, ticket 248136,
# 2026-08-01). REQUEST and NEUTRAL are checked before DENIAL/ADMISSION.

ADMISSION_PHRASES = [
    "wrong sku", "wrong item", "wrong qty", "wrong medicine",
    "short qty", "qty short", "less qty", "sent short", "sent wrong",
    "missing qty", "agreed on short", "have agreed on", "sent damaged",
]

# Denials were previously handled only implicitly ("no admission phrase
# matched"), which is why they were never distinguished from "no comment at
# all" in wh_text_check.json. This is now a first-class table.
DENIAL_PHRASES = [
    "proper medicine", "correct medicine", "correct item",
    "right qty", "right item", "complete order", "complete qty",
    "with ice packs", "good expiry",
]

# Request for evidence - never an admission or denial, even if it contains
# a matching substring (the 248136 lesson). Reused verbatim from build_eod.py.
REQUEST_PHRASES = [
    "kindly share", "please share", "share the image", "share image",
    "share the photo", "share photo", "send the image", "send image",
    "send the photo", "send photo", "provide image", "provide photo",
    "helpfull to find", "helpful to find",
    "kindly share the order id", "share the order id", "kindly share the order",
]

# Factual/procedural statements that are neither an admission nor a denial -
# codifies patterns previously only described in build_eod.py run-note prose.
NEUTRAL_PHRASES = [
    "footage not found", "not related to our inventory",
    "is not cold storage medicine", "not reached at warehouse",
    "containce only", "not in warehouse", "under maintenance",
    "not available in our inventory", "no batch available",
]

# Genuinely non-literal admissions found in practice, kept as an explicit,
# auditable override list rather than trying to regex-generalize a one-off
# phrasing. Key: a lowercase substring of the comment; value: the reason.
# Ticket 257160 (2026-09-06): "we have sent deferent manufacturer company
# medicine to Cx" - a first-person admission of sending the wrong item,
# phrased without the literal word "wrong", matching the ticket's own
# "different manufacturer company" complaint.
INTENT_OVERRIDE_ADMISSIONS = [
    "deferent manufacturer company", "different manufacturer company",
]


def strip_html(raw: str | None) -> str:
    """Comments are basic <div>/<span>-wrapped HTML with &nbsp; etc. entities -
    no need for a full HTML parser, just strip tags and decode the handful of
    entities Zoho actually uses."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
            .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
            .replace("&quot;", '"'))
    return re.sub(r"\s+", " ", text).strip()


def classify_one_comment(text: str) -> str:
    """Returns 'request' | 'neutral' | 'denied' | 'admitted' | 'unrecognized'
    for a single (already HTML-stripped) Warehouse-role comment body."""
    low = text.lower()
    if any(p in low for p in INTENT_OVERRIDE_ADMISSIONS):
        return "admitted"
    if any(p in low for p in REQUEST_PHRASES):
        return "request"
    if any(p in low for p in NEUTRAL_PHRASES):
        return "neutral"
    if any(p in low for p in DENIAL_PHRASES):
        return "denied"
    if any(p in low for p in ADMISSION_PHRASES):
        return "admitted"
    return "unrecognized"


def classify_wh_comments(comments: list[dict]) -> dict:
    """
    comments: raw Zoho getTicketComments 'data' list - each item has
    'content' (HTML), 'commentedTime' (ISO string, sortable as-is), and
    'commenter': {'roleName': str}.

    Returns {'verdict': 'admitted'|'denied'|'no_wh_comment'|'unrecognized',
             'evidence': str|None, 'reason': str}.
    """
    wh_comments = [
        c for c in comments
        if (c.get("commenter") or {}).get("roleName", "").strip().lower().startswith("warehouse")
    ]
    if not wh_comments:
        return {"verdict": "no_wh_comment", "evidence": None,
                "reason": "No Warehouse-team comment on this ticket."}

    wh_comments = sorted(wh_comments, key=lambda c: c.get("commentedTime") or "")

    winning_verdict = None
    winning_text = None
    saw_unrecognized = False
    for c in wh_comments:
        text = strip_html(c.get("content"))
        verdict = classify_one_comment(text)
        if verdict in ("denied", "admitted"):
            # Later comments override earlier ones - the WH team sometimes
            # denies first, then admits once shown evidence (251580/254519/
            # 257160 lesson: always read the full thread, not just the first
            # Warehouse comment).
            winning_verdict = verdict
            winning_text = text
        elif verdict == "unrecognized":
            saw_unrecognized = True
            winning_text = winning_text or text

    if winning_verdict == "admitted":
        return {"verdict": "admitted", "evidence": winning_text,
                "reason": f"Genuine first-person Warehouse admission: \"{winning_text}\""}
    if winning_verdict == "denied":
        return {"verdict": "denied", "evidence": winning_text,
                "reason": f"Warehouse denial (stock/proper-item template): \"{winning_text}\""}
    if saw_unrecognized:
        return {"verdict": "unrecognized", "evidence": winning_text,
                "reason": f"Warehouse commented but it matched no known admission/denial pattern - needs manual review: \"{winning_text}\""}
    return {"verdict": "unrecognized", "evidence": None,
            "reason": "Every Warehouse comment was a request-for-evidence or neutral/factual note - no admission or denial found."}
