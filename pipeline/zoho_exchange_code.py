"""
Exchange a Zoho Self Client grant code for a refresh token and store it in pipeline/.zoho.env (gitignored). No secret ever has to be pasted in chat.

Steps (do them logged in to Zoho as the user who is IN the PlatinumRx Desk org 60026539570, e.g. Anish):
  1. https://api-console.zoho.in  -> Self Client (create one if this login has none) -> copy Client ID and Client Secret.
  2. Put them into pipeline/.zoho.env  (ZOHO_CLIENT_ID=..., ZOHO_CLIENT_SECRET=...).
  3. Self Client > Generate Code: scope  Desk.tickets.READ,Desk.basic.READ,Desk.search.READ  (10 minutes), time duration 10 min. Copy the code.
  4. python3 pipeline/zoho_exchange_code.py <code>
  5. python3 pipeline/refresh_all.py gates   -> "Zoho Desk access" must turn OK.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ENV = Path(__file__).parent / ".zoho.env"


def read_env():
    e = {}
    for ln in ENV.read_text().splitlines():
        if "=" in ln and not ln.lstrip().startswith("#"):
            k, v = ln.split("=", 1)
            e[k.strip()] = v.strip()
    return e


def main(code):
    e = read_env()
    url = e.get("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in").rstrip("/") + "/oauth/v2/token"
    body = urllib.parse.urlencode({"grant_type": "authorization_code", "client_id": e["ZOHO_CLIENT_ID"],
                                   "client_secret": e["ZOHO_CLIENT_SECRET"], "code": code}).encode()
    res = json.load(urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30))
    if "refresh_token" not in res:
        raise SystemExit(f"no refresh_token in the response (code expired or reused?): { {k: v for k, v in res.items() if k != 'access_token'} }")
    lines, done = [], False
    for ln in ENV.read_text().splitlines():
        if ln.startswith("ZOHO_REFRESH_TOKEN="):
            ln, done = "ZOHO_REFRESH_TOKEN=" + res["refresh_token"], True
        lines.append(ln)
    if not done:
        lines.append("ZOHO_REFRESH_TOKEN=" + res["refresh_token"])
    ENV.write_text("\n".join(lines) + "\n")
    tok = ENV.parent / ".zoho_token.json"
    if tok.exists():
        tok.unlink()                     # force a fresh access token
    print("refresh token stored in pipeline/.zoho.env (scopes:", res.get("scope"), ")")


if __name__ == "__main__":
    main(sys.argv[1])
