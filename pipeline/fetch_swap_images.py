"""Fetch complainant images of unpaired swap cases from Zoho (thread + comment attachments, REST) into zoho_raw90/swap_images/ (gitignored),
then build 4-per-sheet contact sheets swap_sheets/ (gitignored). Usage: python3 fetch_swap_images.py <ticketNumber> ... ; sheets -> `sheets`."""
import json, sys, urllib.request, urllib.parse
from pathlib import Path
from zoho_auth import desk_get, get_token, env
HERE = Path(__file__).parent
OUT = HERE / "zoho_raw90/swap_images"; OUT.mkdir(exist_ok=True)

def download(href, dest):
    e = env()
    req = urllib.request.Request(href, headers={"Authorization": "Zoho-oauthtoken " + get_token(), "orgId": e["ZOHO_DESK_ORG_ID"]})
    b = urllib.request.urlopen(req, timeout=60).read()
    dest.write_bytes(b); return len(b)

def run(tn):
    r = (desk_get("/tickets/search", {"ticketNumber": tn, "limit": 1}).get("data") or [])
    tid = next(x["id"] for x in r if str(x["ticketNumber"]) == str(tn))
    atts = []
    for th in (desk_get(f"/tickets/{tid}/threads", {"limit": 100}).get("data") or []):
        try:
            full = desk_get(f"/tickets/{tid}/threads/{th['id']}")
            atts += [a for a in full.get("attachments", [])]
        except Exception: pass
    for c in (desk_get(f"/tickets/{tid}/comments", {"limit": 100}).get("data") or []):
        atts += c.get("attachments", [])
    n = 0
    for a in atts:
        nm = a.get("name", "").lower()
        if not nm.endswith((".jpg", ".jpeg", ".png")): continue
        href = a.get("href") or a.get("previewurl")
        try:
            download(href, OUT / f"{tn}_{n}{Path(nm).suffix}"); n += 1
        except Exception as ex:
            print("  fail", nm, str(ex)[:60])
    print(tn, "images", n, "of", len(atts), "attachments")

def sheets():
    from PIL import Image, ImageDraw
    S = HERE / "swap_sheets"; S.mkdir(exist_ok=True)
    files = sorted(OUT.glob("*.*")); W, H = 640, 540
    for s in range(0, len(files), 4):
        sh = Image.new("RGB", (W * 2, H * 2), "white"); d = ImageDraw.Draw(sh)
        for j, f in enumerate(files[s:s + 4]):
            try: im = Image.open(f).convert("RGB"); im.thumbnail((W - 4, H - 24))
            except Exception: continue
            x, y = (j % 2) * W, (j // 2) * H; sh.paste(im, (x + 2, y + 20)); d.text((x + 4, y + 4), f"#{s + j} {f.stem}", fill="black")
        sh.save(S / f"s{s // 4:03d}.jpg", quality=80)
    (S / "order.json").write_text(json.dumps([f.name for f in files])); print(len(files), "images,", (len(files) + 3) // 4, "sheets")

if __name__ == "__main__":
    if sys.argv[1] == "sheets": sheets()
    else:
        for tn in sys.argv[1:]: run(tn)
