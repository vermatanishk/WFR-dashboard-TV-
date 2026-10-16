"""
Routing signals for the swap-case tickets -> zoho_raw90/swap_ticket_routing.json
  {ticket_id: {"dependency": current cf_dependency, "dependency_ever": [all values it ever had],
               "tags_now": [...], "tags_ever": [...]}}
Why: "Dependency not marked" in the investigation funnel means the ticket was never routed to the Warehouse. The
Dependency field is the primary signal; ticket TAGS (e.g. "blr wh", "logistics") are the fallback, read from the
current tags and from the ticket History (TagsAdded / TagsRemoved events, so a tag later removed still counts).
Only labels are stored - no comment text. Run before build_swap.py.
"""
import json
from build_swap import HERE, select_tickets
from zoho_auth import desk_get

OUT = HERE / "zoho_raw90/swap_ticket_routing.json"


def main():
    tickets, _ = select_tickets()
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    for tn in sorted(tickets):
        hit = desk_get("/tickets/search", {"ticketNumber": tn, "limit": 1})["data"]
        hit = next((h for h in hit if str(h["ticketNumber"]) == tn), None)
        if not hit:
            continue
        tid = hit["id"]
        tags_now = [t["name"] for t in desk_get(f"/tickets/{tid}/tags").get("tags", [])]
        deps, tags, frm = [], set(tags_now), 1
        cur = (hit.get("cf") or {}).get("cf_dependency")
        while True:
            page = desk_get(f"/tickets/{tid}/History", {"limit": 50, "from": frm}).get("data", [])
            for h in page:
                for p in h.get("eventInfo") or []:
                    v = p.get("propertyValue")
                    if p.get("propertyName") == "Dependency" and isinstance(v, dict):
                        deps += [x for x in (v.get("previousValue"), v.get("updatedValue")) if x]
                    if p.get("propertyName") == "Tags" and isinstance(v, list):
                        tags |= set(v)
            if len(page) < 50:
                break
            frm += 50
        out[tn] = {"dependency": cur, "dependency_ever": sorted(set(deps + ([cur] if cur else []))),
                   "tags_now": sorted(tags_now), "tags_ever": sorted(tags)}
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(len(out), "tickets")


if __name__ == "__main__":
    main()
