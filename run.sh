#!/usr/bin/env bash
# Starts the range, the Red agent and the Blue agent. Ctrl-C stops all three.
set -euo pipefail
cd "$(dirname "$0")"
trap 'kill 0' EXIT
uv run python target/app.py &
sleep 2
uv run python -m agents.red &
uv run python -m agents.blue &
echo "Range: http://127.0.0.1:5055/soc  |  In BAND: add Red + Blue to a room and say '@Red attack the shop'"
wait
