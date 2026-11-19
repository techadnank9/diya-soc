"""Red Agent: attacks the range, files tasks on the BAND board, hands off to Blue."""

from __future__ import annotations

import asyncio
import json
import os

from band import Agent, configure_logging
from band.core.simple_adapter import SimpleAdapter
from band.runtime.shutdown import run_with_graceful_shutdown

from agents.common import attack_all, ensure_lyzr_agents, extract_payload, lyzr_think

configure_logging()
BLUE_ID = os.getenv("BLUE_BAND_AGENT_ID", "")
MAX_ROUNDS = 3


async def safe(coro):
    try:
        return await coro
    except Exception as e:  # board/memory extras must never break the attack loop
        print(f"[red] band call failed: {e}")
        return None


def task_id(obj) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get("id") or (obj.get("data") or {}).get("id")
    return getattr(obj, "id", None) or getattr(getattr(obj, "data", None), "id", None)


class RedAdapter(SimpleAdapter[str]):
    def __init__(self) -> None:
        super().__init__()
        self.rooms: dict[str, dict] = {}  # room_id -> {"round": n, "tasks": {vuln: task_id}, "human": id}

    async def on_message(self, msg, tools, history, participants_msg, contacts_msg, *,
                         is_session_bootstrap: bool, room_id: str) -> None:
        state = self.rooms.setdefault(room_id, {"round": 0, "tasks": {}, "human": None})
        from_blue = msg.sender_type == "Agent" and (not BLUE_ID or msg.sender_id == BLUE_ID)
        if from_blue:
            if "RETEST" not in msg.content.upper():
                await tools.no_reply("blue message without retest request")
                return
            payload = extract_payload(msg.content) or {}
            state["tasks"].update(payload.get("tasks", {}))
        else:
            state["human"] = msg.sender_id
            state["round"] = 0
            state["tasks"] = {}

        if state["round"] >= MAX_ROUNDS:
            await tools.send_message("Max retest rounds reached, handing back to the humans.",
                                     mentions=[state["human"]] if state["human"] else None)
            return
        state["round"] += 1
        rnd = state["round"]

        await tools.send_event(f"Round {rnd}: firing 4 live exploits at the Diya Sweets range",
                               "thought")
        if rnd == 1:
            await safe(tools.set_board(
                goal_title="Diwali Red vs Blue: harden Diya Sweets",
                goal_summary="Red attacks, Blue patches, Red re-attacks until every finding is closed."))

        results = await asyncio.to_thread(attack_all)
        for r in results:
            await tools.send_event(
                json.dumps({"exploit": r["vuln"], "payload": r["payload"]}), "tool_call",
                metadata={"tool": "exploit", "vuln": r["vuln"]})
            await tools.send_event(
                ("EXPLOITED: " if r["exploited"] else "BLOCKED: ") + r["evidence"][:140],
                "tool_result", metadata={"tool": "exploit", "vuln": r["vuln"]})

        open_ = [r for r in results if r["exploited"]]
        closed = [r for r in results if not r["exploited"]]

        # Board: one task per confirmed finding, closed when the retest proves the fix.
        for r in open_:
            if r["vuln"] not in state["tasks"]:
                t = await safe(tools.create_task(
                    subject=f"[{r['cwe']}] {r['title']}",
                    detail=f"Payload: {r['payload']}\nEvidence: {r['evidence'][:200]}"))
                if tid := task_id(t):
                    state["tasks"][r["vuln"]] = tid
            elif rnd > 1:
                await safe(tools.update_task(state["tasks"][r["vuln"]], status="failed",
                                             comment=f"Round {rnd}: still exploitable."))
        if rnd > 1:
            for r in closed:
                if tid := state["tasks"].get(r["vuln"]):
                    await safe(tools.update_task(tid, status="completed",
                                                 comment=f"Round {rnd}: exploit blocked. Verified by Red."))

        if not open_:
            await safe(tools.store_memory(
                content=f"Diya Sweets range fully hardened in {rnd} rounds; {len(closed)} exploits now blocked.",
                system="long_term", type="episodic", segment="agent",
                thought="Remember how many rounds hardening took for future engagements.",
                scope="agent"))
            await tools.send_message(
                f"Round {rnd} verdict: all {len(closed)} exploits are now BLOCKED. "
                "Every task on the board is verified closed. Happy Diwali, the lights stay on.",
                mentions=[state["human"]] if state["human"] else None)
            return

        evidence = [{k: r[k] for k in ("vuln", "title", "cwe", "payload", "evidence")} for r in open_]
        report = await lyzr_think("red", "Evidence:\n" + json.dumps(evidence, indent=1), room_id[:12])
        if not report:
            report = "\n".join(f"- {r['title']} ({r['cwe']}): exploited with `{r['payload']}`" for r in open_)

        handoff = {"round": rnd, "findings": evidence,
                   "tasks": {r["vuln"]: state["tasks"].get(r["vuln"]) for r in open_}}
        text = (f"Round {rnd}: {len(open_)} live exploit(s), {len(closed)} blocked.\n\n{report}\n\n"
                f"Blue, please patch these:\n```json\n{json.dumps(handoff)}\n```")
        await tools.send_message(text, mentions=[BLUE_ID] if BLUE_ID else None)


async def main() -> None:
    ensure_lyzr_agents()
    agent = Agent.create(adapter=RedAdapter(), agent_id=os.environ["RED_BAND_AGENT_ID"],
                         api_key=os.environ["RED_BAND_API_KEY"])
    await run_with_graceful_shutdown(agent)


if __name__ == "__main__":
    asyncio.run(main())
