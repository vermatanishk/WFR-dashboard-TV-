"""
Zoho Desk auth helper. Credentials live in pipeline/.zoho.env (gitignored:
Vercel auto-deploys this repo, so secrets must never be committed). The refresh
token is long-lived; the access token (1h) is refreshed automatically and
cached in pipeline/.zoho_token.json (also gitignored) so every script just
calls get_token()/desk_get() and never handles expiry itself.

Fallback: if the REST path fails (revoked token, API limit), the session
should use the Zoho Desk MCP (searchTickets / getTicket / getTicketComments)
and write the same cache files - see CLAUDE.md "RCA layer".
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ENV = HERE / ".zoho.env"
TOKEN = HERE / ".zoho_token.json"


def env():
    return dict(l.strip().split("=", 1) for l in ENV.read_text().splitlines() if "=" in l and not l.startswith("#"))


def get_token(force=False):
    if not force and TOKEN.exists():
        t = json.loads(TOKEN.read_text())
        if t["expires_at"] - time.time() > 120:
            return t["access_token"]
    e = env()
    d = urllib.parse.urlencode({"grant_type": "refresh_token", "client_id": e["ZOHO_CLIENT_ID"],
                                "client_secret": e["ZOHO_CLIENT_SECRET"],
                                "refresh_token": e["ZOHO_REFRESH_TOKEN"]}).encode()
    r = json.load(urllib.request.urlopen(e["ZOHO_ACCOUNTS_URL"] + "/oauth/v2/token", d, timeout=30))
    if "access_token" not in r:
        raise RuntimeError(f"Zoho token refresh failed: {r}")
    TOKEN.write_text(json.dumps({"access_token": r["access_token"], "expires_at": time.time() + int(r.get("expires_in", 3600))}))
    TOKEN.chmod(0o600)
    return r["access_token"]


def desk_get(path, params=None, retry=True):
    e = env()
    url = e["ZOHO_DESK_API"] + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": "Zoho-oauthtoken " + get_token(),
                                               "orgId": e["ZOHO_DESK_ORG_ID"]})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as ex:
        if ex.code == 401 and retry:
            get_token(force=True)
            return desk_get(path, params, retry=False)
        raise
