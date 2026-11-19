"""Diya Sweets: a deliberately vulnerable shop used as the Red vs Blue range.

Every vulnerability has a patch switch in patches.json. The Blue agent turns
those switches on via /admin/patch; the Red agent then re-attacks to prove it.
Local range only. Never deploy this anywhere public.
"""

from __future__ import annotations

import html
import json
import sqlite3
import os
import time
from pathlib import Path

from flask import Flask, jsonify, request

ROOT = Path(__file__).parent
PATCHES = ROOT / "patches.json"
EVENTS = ROOT / "events.jsonl"
ADMIN_TOKEN = os.getenv("TARGET_ADMIN_TOKEN", "blue-team-local")

VULNS = {
    "sqli_login": "SQL injection in /login",
    "xss_search": "Reflected XSS in /search",
    "idor_orders": "IDOR on /api/orders/<id>",
    "debug_leak": "Secrets exposed on /debug",
}

app = Flask(__name__)


def patches() -> dict:
    if PATCHES.exists():
        return json.loads(PATCHES.read_text())
    return {k: False for k in VULNS}


def log(kind: str, **data) -> None:
    with EVENTS.open("a") as f:
        f.write(json.dumps({"t": time.time(), "kind": kind, **data}) + "\n")


def db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        create table users(id int, username text, password text, role text);
        insert into users values (1,'admin','diwali-2026!','admin'),(2,'priya','laddoo','customer'),(3,'arjun','barfi','customer');
        create table orders(id int, user_id int, item text, card_last4 text, address text);
        insert into orders values (101,2,'Kaju Katli box','4242','12 Mission St'),(102,3,'Gulab Jamun tin','1881','9 Castro St'),(103,1,'Diya set (x50)','0007','HQ');
        """
    )
    return con


@app.get("/")
def home():
    return '<h1>Diya Sweets</h1><p>Festival of Lights shop (a deliberately vulnerable test range). <a href="/soc">Open the live Red vs Blue SOC</a></p>'


@app.post("/login")
def login():
    body = request.get_json(force=True, silent=True) or {}
    user, pw = body.get("username", ""), body.get("password", "")
    con = db()
    if patches().get("sqli_login"):
        row = con.execute(
            "select id, username, role from users where username=? and password=?", (user, pw)
        ).fetchone()
    else:
        q = f"select id, username, role from users where username='{user}' and password='{pw}'"
        try:
            row = con.execute(q).fetchone()
        except sqlite3.Error as e:
            log("probe", vuln="sqli_login", blocked=False, note=str(e))
            return jsonify(error=str(e)), 500
    log("probe", vuln="sqli_login", blocked=bool(patches().get("sqli_login")), user=user[:40])
    if not row:
        return jsonify(ok=False), 401
    return jsonify(ok=True, user={"id": row[0], "username": row[1], "role": row[2]})


@app.get("/search")
def search():
    q = request.args.get("q", "")
    safe = patches().get("xss_search")
    shown = html.escape(q) if safe else q
    log("probe", vuln="xss_search", blocked=bool(safe), q=q[:60])
    resp = app.make_response(f"<p>Results for {shown}</p>")
    if safe:
        resp.headers["Content-Security-Policy"] = "default-src 'self'"
    return resp


@app.get("/api/orders/<int:oid>")
def order(oid: int):
    caller = request.headers.get("X-User-Id", "")
    row = db().execute("select id,user_id,item,card_last4,address from orders where id=?", (oid,)).fetchone()
    if not row:
        return jsonify(error="not found"), 404
    if patches().get("idor_orders") and str(row[1]) != caller:
        log("probe", vuln="idor_orders", blocked=True, oid=oid, caller=caller)
        return jsonify(error="forbidden"), 403
    log("probe", vuln="idor_orders", blocked=False, oid=oid, caller=caller)
    return jsonify(id=row[0], user_id=row[1], item=row[2], card_last4=row[3], address=row[4])


@app.get("/debug")
def debug():
    if patches().get("debug_leak"):
        log("probe", vuln="debug_leak", blocked=True)
        return jsonify(error="not found"), 404
    log("probe", vuln="debug_leak", blocked=False)
    return jsonify(STRIPE_SECRET="sk_test_FAKE_diya_123", DB_PASSWORD="diwali-2026!", DEBUG=True)


@app.post("/admin/patch")
def patch():
    if request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return jsonify(error="forbidden"), 403
    body = request.get_json(force=True) or {}
    p = patches()
    for k in body.get("enable", []):
        if k in VULNS:
            p[k] = True
    PATCHES.write_text(json.dumps(p, indent=2))
    log("patch", enabled=body.get("enable", []), by=body.get("by", "blue"))
    return jsonify(p)


@app.post("/admin/reset")
def reset():
    if request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        return jsonify(error="forbidden"), 403
    PATCHES.write_text(json.dumps({k: False for k in VULNS}, indent=2))
    EVENTS.write_text("")
    return jsonify(ok=True)


@app.get("/soc/state")
def soc_state():
    events = []
    if EVENTS.exists():
        events = [json.loads(l) for l in EVENTS.read_text().splitlines()[-80:] if l.strip()]
    return jsonify(patches=patches(), vulns=VULNS, events=events)


@app.get("/soc")
def soc():
    return (ROOT / "soc.html").read_text()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5055")), debug=False, threaded=True)
