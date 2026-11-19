"""Blue Agent: reads Red's findings from the room, patches, asks Red to retest."""

from __future__ import annotations

import asyncio
import json
import os

from band import Agent, configure_logging
from band.core.simple_adapter import SimpleAdapter
from band.runtime.shutdown import run_with_graceful_shutdown

from agents.common import apply_patch, ensure_lyzr_agents, extract_payload, lyzr_think

configure_logging()
PACE = float(os.getenv("DEMO_PACE", "0"))  # seconds between steps, for live demos
RED_ID = os.getenv("RED_BAND_AGENT_ID", "")

FIX_NOTES = {
    "sqli_login": "Parameterised the login query (`?` placeholders). Detect: alert on `'` or `--` in username.",
    "xss_search": "HTML-escaped the search echo and added a strict CSP. Detect: `<script` in query string.",
    "idor_orders": "Order lookup now checks the caller owns the order (403 otherwise). Detect: user reading other users' order ids.",
    "debug_leak": "Removed the /debug endpoint from production. Detect: any hit on /debug.",
}


async def safe(coro):
    try:
        return await coro
    except Exception as e:
        print(f"[blue] band call failed: {e}")
        return None


class BlueAdapter(SimpleAdapter[str]):
    async def on_message(self, msg, tools, history, participants_msg, contacts_msg, *,
                         is_session_bootstrap: bool, room_id: str) -> None:
        payload = extract_payload(msg.content)
        if not payload or not payload.get("findings"):
            await tools.send_message(
                "Blue Team here. I patch whatever the Red agent proves exploitable in this room. "
                "Ask the Red agent to attack and I'll take it from there.",
                mentions=[msg.sender_id])
            return

        findings = payload["findings"]
        tasks = payload.get("tasks", {})
        rnd = payload.get("round", 1)
        for f in findings:
            if tid := tasks.get(f["vuln"]):
                await safe(tools.update_task(tid, status="in_progress",
                                             comment="Blue: root-causing and writing the patch."))

        await tools.send_event(f"Triaging {len(findings)} finding(s) from Red round {rnd}", "thought")
        plan = await lyzr_think("blue", "Findings:\n" + json.dumps(findings, indent=1), room_id[:12])

        await asyncio.sleep(PACE)
        vulns = [f["vuln"] for f in findings]
        await tools.send_event(json.dumps({"enable": vulns}), "tool_call",
                               metadata={"tool": "deploy_patch"})
        state = await asyncio.to_thread(apply_patch, vulns)
        await tools.send_event(json.dumps(state), "tool_result", metadata={"tool": "deploy_patch"})

        for f in findings:
            if tid := tasks.get(f["vuln"]):
                await safe(tools.update_task(tid, status="completed",
                                             comment="Patch deployed: " + FIX_NOTES.get(f["vuln"], "")))

        await safe(tools.store_memory(
            content="Patched: " + "; ".join(FIX_NOTES.get(v, v) for v in vulns),
            system="long_term", type="procedural", segment="agent",
            thought="Reusable fix playbook for these vulnerability classes.", scope="agent"))

        await asyncio.sleep(PACE)
        notes = "\n".join(f"- {f['title']}: {FIX_NOTES.get(f['vuln'], '')}" for f in findings)
        body = plan or notes
        text = (f"Patched {len(vulns)} issue(s) and deployed to the range.\n\n{body}\n\n"
                f"Red, please RETEST and close the tasks if the exploits fail:\n"
                f"```json\n{json.dumps({'round': rnd, 'tasks': tasks})}\n```")
        await tools.send_message(text, mentions=[RED_ID] if RED_ID else None)


async def main() -> None:
    ensure_lyzr_agents()
    agent = Agent.create(adapter=BlueAdapter(), agent_id=os.environ["BLUE_BAND_AGENT_ID"],
                         api_key=os.environ["BLUE_BAND_API_KEY"])
    await run_with_graceful_shutdown(agent)


if __name__ == "__main__":
    asyncio.run(main())
