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

OUT = HERE / "zoho_raw90/swap_ticket_routing.json"


def main():
    from pull_ticket_routing import fetch_routing
    tickets, _ = select_tickets()
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    for tn in sorted(tickets):
        res = fetch_routing(tn)
        if res:
            out[tn] = res
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(len(out), "tickets")


if __name__ == "__main__":
    main()
