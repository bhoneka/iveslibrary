#!/usr/bin/env python3
"""Register iveslibrary.com on Porkbun and point it at GitHub Pages.

Credentials are read from ~/.config/porkbun/env (never passed on the command line):
    PORKBUN_API_KEY=pk1_...
    PORKBUN_SECRET_KEY=sk1_...
(Create them at porkbun.com → Account → API Access.)

Usage:
    python3 porkbun_setup.py check                # availability + price, no charge
    python3 porkbun_setup.py register             # buys the domain with account credit (asks y/N)
    python3 porkbun_setup.py dns                  # replaces default records with GitHub Pages A/AAAA + www CNAME
    python3 porkbun_setup.py status               # shows current DNS + nameservers
Then: gh api -X PUT repos/bhoneka/iveslibrary/pages -f cname=iveslibrary.com   (and add CNAME file / enforce HTTPS)
"""
import json, os, sys, urllib.request

DOMAIN = os.environ.get("DOMAIN", "iveslibrary.com")
GH_USER = "bhoneka"
BASE = "https://api.porkbun.com/api/json/v3"
GH_A = ["185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"]
GH_AAAA = ["2606:50c0:8000::153", "2606:50c0:8001::153", "2606:50c0:8002::153", "2606:50c0:8003::153"]

def creds():
    p = os.path.expanduser("~/.config/porkbun/env")
    kv = {}
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1); kv[k.strip()] = v.strip().strip('"').strip("'")
    key = kv.get("PORKBUN_API_KEY") or os.environ.get("PORKBUN_API_KEY")
    sec = kv.get("PORKBUN_SECRET_KEY") or os.environ.get("PORKBUN_SECRET_KEY")
    if not key or not sec:
        sys.exit("Missing keys. Put PORKBUN_API_KEY and PORKBUN_SECRET_KEY in ~/.config/porkbun/env")
    return {"apikey": key, "secretapikey": sec}

def pb(path, **extra):
    body = json.dumps({**creds(), **extra}).encode()
    req = urllib.request.Request(f"{BASE}/{path}", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read().decode())
        except Exception: return {"status": "HTTP_ERROR", "code": e.code}

def show(x):
    print(json.dumps(x, indent=1, ensure_ascii=False))

cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
if cmd == "check":
    show(pb("ping")); show(pb(f"domain/checkDomain/{DOMAIN}"))
elif cmd == "register":
    chk = pb(f"domain/checkDomain/{DOMAIN}"); show(chk)
    if chk.get("status") != "SUCCESS" or chk.get("response", {}).get("avail") != "yes":
        sys.exit("Not available.")
    cost = round(float(chk["response"]["price"]) * 100)
    ans = input(f"Register {DOMAIN} for ${cost/100:.2f} from Porkbun account credit? [y/N] ").strip().lower()
    if ans != "y": sys.exit("Cancelled.")
    show(pb(f"domain/create/{DOMAIN}", cost=cost, agreeToTerms="yes", whoisPrivacy=True))
elif cmd == "status":
    show(pb(f"domain/getNs/{DOMAIN}")); show(pb(f"dns/retrieve/{DOMAIN}"))
elif cmd == "dns":
    # clear Porkbun's parking defaults on @ and www, then add GitHub Pages records
    for t, name in [("A", ""), ("AAAA", ""), ("ALIAS", ""), ("CNAME", "www"), ("A", "www")]:
        pb(f"dns/deleteByNameType/{DOMAIN}/{t}/{name}")
    for ip in GH_A: show(pb(f"dns/create/{DOMAIN}", name="", type="A", content=ip, ttl="600"))
    for ip in GH_AAAA: show(pb(f"dns/create/{DOMAIN}", name="", type="AAAA", content=ip, ttl="600"))
    show(pb(f"dns/create/{DOMAIN}", name="www", type="CNAME", content=f"{GH_USER}.github.io", ttl="600"))
    show(pb(f"dns/retrieve/{DOMAIN}"))
else:
    sys.exit(__doc__)
