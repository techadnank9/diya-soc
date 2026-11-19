#!/usr/bin/env bash
# Render entrypoint: the range on $PORT, plus the agents when BAND keys are set.
set -uo pipefail
cd "$(dirname "$0")"
export TARGET_URL="http://127.0.0.1:${PORT:-5055}"
python target/app.py &
sleep 3
if [[ -n "${RED_BAND_AGENT_ID:-}" && -n "${BLUE_BAND_AGENT_ID:-}" ]]; then
  python -m agents.red &
  python -m agents.blue &
else
  echo "BAND keys not set: serving the range and SOC only"
fi
wait -n
