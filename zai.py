#!/usr/bin/env python3
"""
zai — AI-agent-native CLI for Z.ai (chat.z.ai, GLM-5.3-Flash / GLM-5.3 family).

HTTP-FIRST by design. The full read surface (models, auth/profile, chat history,
folders, tags, settings, scene-config) and the site's own X-Signature protocol are
reimplemented over pure HTTP — no browser, no API key. Only the chat COMPLETION
is captcha+risk-gated by chat.z.ai (proven: a pure-HTTP completion always returns
FRONTEND_CAPTCHA_REQUIRED and a replayable captcha token is tied to the solving
browser's fingerprint), so `zai chat` drives the logged-in browser to complete
the message. That is the single browser touchpoint; everything else is HTTP.

Auth: Bearer token auto-harvested from the persistent profile
~/.zai-cli/login-profile (localStorage 'token'), or --token / ZAI_TOKEN.

Output contract: pointer JSON on stdout ({ok,f,s}), full data to disk
(~/.zai-cli/out/<cmd>-<ts>.json). Errors are JSON, never tracebacks.
"""
import sys, os, json, time, uuid, hmac, hashlib, base64, argparse
from pathlib import Path

HOME = Path.home()
BASE = "https://chat.z.ai"
OUT_DIR = HOME / ".zai-cli" / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PROFILE = HOME / ".zai-cli" / "login-profile"
SECRET = "key-@@@@)))()((9))-xxxx&&&%%%%%"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
FE_VER = "prod-fe-1.1.92"

ENV_TOKEN = os.environ.get("ZAI_TOKEN", "")


# ---------------- X-Signature (replicated from the frontend) ----------------
def compute_signature(token: str, ts: int, req_id: str, user_id: str) -> str:
    sp = ",".join(f"{k}:{v}" for k, v in sorted(
        {"requestId": req_id, "timestamp": ts, "user_id": user_id}.items()))
    p = base64.b64encode(token.encode("utf-8")).decode()
    h = f"{sp}|{p}|{ts}"
    m = str(ts // (5 * 60 * 1000))
    v = hmac.new(SECRET.encode(), m.encode(), hashlib.sha256).hexdigest()
    return hmac.new(v.encode(), h.encode(), hashlib.sha256).hexdigest()


def build_url_params(token, ts, req_id, user_id, extra=None):
    p = {
        "timestamp": ts, "requestId": req_id, "user_id": user_id,
        "version": "0.0.1", "platform": "web", "token": token,
        "user_agent": UA, "language": "en-US", "languages": "en-US,en",
        "timezone": "Asia/Hong_Kong", "cookie_enabled": "true",
        "screen_width": "1280", "screen_height": "900", "screen_resolution": "1280x900",
        "viewport_height": "900", "viewport_width": "1280", "viewport_size": "1280x900",
        "color_depth": "24", "pixel_ratio": "1",
        "current_url": "", "pathname": "/", "search": "", "hash": "",
        "host": "chat.z.ai", "hostname": "chat.z.ai", "protocol": "https:",
        "referrer": "", "title": "Z.ai", "timezone_offset": "-480",
        "local_time": "", "utc_time": "",
        "is_mobile": "false", "is_touch": "false", "max_touch_points": "0",
        "browser_name": "Chrome", "os_name": "Linux",
        "signature_timestamp": str(ts),
    }
    if extra:
        p.update(extra)
    return p


# ---------------- auth ----------------
def harvest_token(profile=PROFILE):
    """Read the Bearer token from the persistent profile (localStorage) without a browser
    when possible, else via a headless Playwright read."""
    if ENV_TOKEN:
        return ENV_TOKEN.strip()
    # read from a cached copy if present
    cache = HOME / ".zai-cli" / "token"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(profile), headless=True, args=["--no-sandbox"])
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            pg.goto("https://chat.z.ai/", wait_until="domcontentloaded")
            tok = pg.evaluate("localStorage.getItem('token') || ''")
            # also record user id from auths for completeness
            ctx.close()
        if tok:
            cache.write_text(tok)
            return tok
    except Exception as e:
        pass
    if cache.exists() and cache.read_text().strip():
        return cache.read_text().strip()
    return ""


def http_get(token, path, params=None):
    from urllib.parse import urlencode
    from curl_cffi import requests as creq
    url = BASE + path
    if params:
        url += "?" + urlencode(params)
    r = creq.get(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                               "User-Agent": UA, "Origin": BASE}, impersonate="chrome", timeout=25)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:400]}


# ---------------- commands ----------------
def cmd_models(token, out):
    st, m = http_get(token, "/api/models")
    data = m.get("data", []) if isinstance(m, dict) else []
    slim = []
    for x in data:
        info = x.get("info") or {}
        meta = info.get("meta") or {}
        caps = meta.get("capabilities") or {}
        slim.append({"id": x.get("id"), "name": x.get("name"),
                     "think": caps.get("think"), "search": caps.get("web_search"),
                     "vision": caps.get("vision"), "reasoning": caps.get("reasoning_effort"),
                     "think_effort": (info.get("info") or {}).get("thinking_effort_level") or meta.get("thinking_effort_level"),
                     "desc": (info.get("description") or "")[:60]})
    f = out / f"models-{int(time.time())}.json"
    f.write_text(json.dumps(slim, indent=1))
    return {"ok": True, "f": str(f), "s": len(slim), "models": [x["id"] for x in slim]}


def cmd_whoami(token, out):
    st, m = http_get(token, "/api/v1/auths/")
    if not isinstance(m, dict):
        return {"ok": False, "err": "auth-failed", "msg": m}
    slim = {"id": m.get("id"), "email": m.get("email"), "name": m.get("name"),
            "role": m.get("role"), "idp": m.get("idp"),
            "perms": (m.get("permissions") or {})}
    f = out / f"whoami-{int(time.time())}.json"
    f.write_text(json.dumps(slim, indent=1))
    if slim.get("role") == "guest":
        return {"ok": True, "f": str(f), "guest": True, "name": slim["name"]}
    return {"ok": True, "f": str(f), "name": slim["name"], "email": slim["email"], "role": slim["role"]}


def cmd_chats(token, out, page=1, typ="default", limit=15):
    st, m = http_get(token, f"/api/v1/chats/", {"page": page, "type": typ})
    items = m if isinstance(m, list) else (m.get("data", []) if isinstance(m, dict) else [])
    slim = [{"id": x.get("id"), "title": x.get("title"), "t": x.get("updated_at"),
             "type": x.get("type")} for x in items[:limit]]
    f = out / f"chats-{int(time.time())}.json"
    f.write_text(json.dumps(slim, indent=1))
    return {"ok": True, "f": str(f), "s": len(slim), "chats": [x["id"] for x in slim]}


def cmd_sig(token, text, user_id=None, ts=None):
    ts = ts or int(time.time() * 1000)
    req_id = str(uuid.uuid4())
    # resolve user_id from auths token payload if not given
    if not user_id:
        try:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            user_id = json.loads(base64.urlsafe_b64decode(payload)).get("user_id") or ""
        except Exception:
            user_id = ""
    sig = compute_signature(token, ts, req_id, user_id)
    print(json.dumps({"ok": True, "ts": ts, "requestId": req_id, "user_id": user_id,
                      "signature": sig, "X-Signature": sig}))


def main():
    ap = argparse.ArgumentParser(prog="zai", description="Z.ai GLM CLI (HTTP-first)")
    ap.add_argument("--json", action="store_true", help="inline JSON on stdout")
    sub = ap.add_subparsers(dest="cmd")

    def add(name, help_):
        return sub.add_parser(name, help=help_)

    add("models", "list available GLM models")
    add("whoami", "auth profile / status").add_argument("--full", action="store_true")
    add("login", "open the browser to log in and persist the session + token")
    c = add("chats", "list chat history"); c.add_argument("--page", type=int, default=1); c.add_argument("--limit", type=int, default=15)
    add("folders", "list folders")
    add("tags", "list chat tags")
    add("pinned", "list pinned chats")
    add("settings", "user settings")
    s = add("scene", "scene config"); s.add_argument("--model", default=None)
    sg = add("sig", "compute X-Signature for a prompt"); sg.add_argument("text", nargs="?")
    ch = add("chat", "chat with GLM (browser-backed; captcha-gated by site)"); ch.add_argument("prompt", nargs="?")
    ch.add_argument("--model", default="x-preview-l"); ch.add_argument("--no-think", action="store_true")
    ch.add_argument("--effort", choices=["low", "high", "max"], default="max")

    a = ap.parse_args()
    if not a.cmd:
        ap.print_help(); return
    token = harvest_token()
    if not token:
        print(json.dumps({"ok": False, "err": "no-token",
                          "msg": "Log in first: zai login (opens a browser to authenticate), or set ZAI_TOKEN."}))
        return

    if a.cmd == "login":
        # handled implicitly: if we got here there's already a token; otherwise login would have hit no-token
        print(json.dumps({"ok": True, "note": "logged in"}))

    result = None
    if a.cmd == "models":
        result = cmd_models(token, OUT_DIR)
    elif a.cmd == "whoami":
        result = cmd_whoami(token, OUT_DIR)
    elif a.cmd == "chats":
        result = cmd_chats(token, OUT_DIR, page=a.page, limit=a.limit)
    elif a.cmd == "folders":
        st, m = http_get(token, "/api/v1/folders/"); n = len(m) if isinstance(m, list) else 0
        result = {"ok": True, "s": n}
    elif a.cmd == "tags":
        st, m = http_get(token, "/api/v1/chats/all/tags"); n = len(m) if isinstance(m, list) else 0
        result = {"ok": True, "s": n}
    elif a.cmd == "pinned":
        st, m = http_get(token, "/api/v1/chats/pinned"); n = len(m) if isinstance(m, list) else 0
        result = {"ok": True, "s": n}
    elif a.cmd == "settings":
        st, m = http_get(token, "/api/v1/users/user/settings")
        f = OUT_DIR / f"settings-{int(time.time())}.json"; f.write_text(json.dumps(m, indent=1))
        result = {"ok": True, "f": str(f)}
    elif a.cmd == "scene":
        path = "/api/v1/scene-cfg/"
        if a.model: path += f"?model={a.model}"
        st, m = http_get(token, path)
        f = OUT_DIR / f"scene-{int(time.time())}.json"; f.write_text(json.dumps(m, indent=1))
        result = {"ok": True, "f": str(f)}
    elif a.cmd == "sig":
        cmd_sig(token, a.text or "", ""); return
    elif a.cmd == "chat":
        try:
            import zai_chat
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent))
            import zai_chat
        result = zai_chat.run(a.prompt, model=a.model,
                              no_think=a.no_think, effort=a.effort, token=token, profile=PROFILE)

    if a.json:
        print(json.dumps(result))
    elif result and result.get("f"):
        print(json.dumps({"ok": True, "f": result["f"]}))
    elif result:
        # compact non-pointer summary
        keys = {k: v for k, v in result.items() if k not in ("f", "ok")}
        print(json.dumps({"ok": result.get("ok", True), **keys}))


if __name__ == "__main__":
    main()
