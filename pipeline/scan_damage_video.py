"""Scan Zoho tickets of the 30-day damage orders for video evidence (attachments/links) in comments and threads."""
import json,re,sys
sys.path.insert(0,".")
from zoho_auth import desk_get
live=json.load(open("zoho_raw90/damage30_zoho_live.json"))
tk={}
for o,ts in live:
    for t in ts: tk.setdefault(t["ticket"],o)
VID=re.compile(r"\.(mp4|mov|3gp|avi|mkv|webm)\b|video|footage|drive\.google|youtu|cctv",re.I)
out={}
def body(c): return re.sub(r"<[^>]+>"," ",c.get("content") or "")
for n,(num,o) in enumerate(tk.items()):
    try:
        s=desk_get("/tickets/search",{"ticketNumber":num}); tid=s["data"][0]["id"]
        res=dict(order=o,hits=[])
        for kind,path in (("comment",f"/tickets/{tid}/comments"),("thread",f"/tickets/{tid}/threads")):
            try: items=(desk_get(path,{"limit":100}) or {}).get("data",[])
            except Exception: items=[]
            for c in items:
                role=(c.get("commenter") or c.get("author") or {})
                txt=body(c)
                att=[a.get("name") or a.get("href","") for a in (c.get("attachments") or [])]
                vid_att=[a for a in att if re.search(r"\.(mp4|mov|3gp|avi|mkv|webm)",a,re.I)]
                if vid_att or VID.search(txt):
                    res["hits"].append(dict(kind=kind,who=role.get("roleName") or role.get("name") or c.get("direction"),
                      vid_att=vid_att,snip=VID.search(txt).group(0) if VID.search(txt) else ""))
        out[num]=res
    except Exception as e: out[num]=dict(order=o,error=str(e)[:80])
    if n%20==0: print(n,len(tk),flush=True)
json.dump(out,open("zoho_raw90/damage30_video_scan.json","w"))
print("done")
