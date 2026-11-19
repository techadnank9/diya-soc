# Diya SOC: Red vs Blue agents that harden an app together on BAND

Built for the Diwali Agent-to-Agent Hackathon (Security track: Attack & Defend).

Two autonomous agents share a **BAND room** with the humans who own the app:

- **Red Agent** fires real exploits (SQL injection, reflected XSS, IDOR, secret leak) at a deliberately vulnerable shop. It opens one **BAND task** per confirmed finding, posts a severity report written by its **Lyzr** brain, and **@mentions Blue** with a machine-readable handoff.
- **Blue Agent** picks up the handoff, moves each task to *in progress*, asks its **Lyzr** brain for root cause, fix and detection rule, deploys the patch to the range, moves tasks to *in review* and **@mentions Red to retest**.
- Red re-attacks. Blocked exploits close their tasks as *completed*; anything still open is marked *failed* and goes back to Blue. The loop runs until the board is clean (max 3 rounds), then Red reports back to the human who started it.

Both agents write what they learned to **BAND memory** (Red: episodic engagement record, Blue: procedural fix playbook).

## Why BAND

The collaboration happens entirely through BAND primitives, not a private queue between two scripts:

| BAND feature | Used for |
| --- | --- |
| Shared room + @mentions | Red ↔ Blue handoffs, human kicks off and gets the verdict |
| Room goal (`set_board`) | The mission: harden Diya Sweets |
| Task board | One task per vulnerability, driven pending → in_progress → in_review → completed/failed by two different agents |
| Events (`thought`, `tool_call`, `tool_result`) | Every exploit and patch is visible live in the room |
| Memory | Long-term engagement record and fix playbook |

Humans watch and steer in the same room. Lyzr Agent Studio hosts the two reasoning brains (auto-created via the Lyzr REST API on first run).

## Run it

```bash
cp .env.example .env   # fill in 2 BAND agents + LYZR_API_KEY
./run.sh
```

Then in BAND: create a room, add **Red** and **Blue**, and send `@Red attack the shop`.
Watch the range live at http://127.0.0.1:5055/soc.

## Layout

- `agents/red.py`: Red agent (BAND `SimpleAdapter`)
- `agents/blue.py`: Blue agent
- `agents/common.py`: Lyzr client, exploit toolkit, patch deployer
- `target/app.py`: deliberately vulnerable Flask shop + `/soc` live dashboard

The target is a local test range with fake data. Never expose it publicly.
