#!/bin/bash
# 99-wait-for-nomad.sh
#
# Wait for Nomad to elect a Raft leader and become ready.
#
# Nomad's systemd unit starts asynchronously -- `systemctl restart nomad`
# returns before the agent has initialised, joined a Raft cluster, and
# elected a leader.  Any subsequent `nomad ...` CLI invocation silently
# fails until the HTTP API responds with a leader.
#
# This script polls GET /v1/status/leader until it returns a non-empty
# string (a valid leader address) or the timeout expires.
#
# Usage: source this or run directly.  Exits 0 on success, 1 on timeout.

set -e

NOMAD_ADDR="${NOMAD_ADDR:-http://127.0.0.1:4646}"
POLL_INTERVAL="${NOMAD_POLL_INTERVAL:-2}"    # seconds between attempts
TIMEOUT="${NOMAD_WAIT_TIMEOUT:-60}"           # total seconds to wait

echo ">>> [99] Waiting for Nomad leader at ${NOMAD_ADDR} ..."

start_ts=$(date +%s)

while true; do
  leader=$(curl -fsSL --connect-timeout 2 --max-time 4 "${NOMAD_ADDR}/v1/status/leader" 2>/dev/null || echo "")

  if [ -n "$leader" ] && [ "$leader" != '""' ]; then
    echo ">>> [99] Nomad leader elected: ${leader} (waited ~$(($(date +%s) - start_ts))s)"
    exit 0
  fi

  elapsed=$(($(date +%s) - start_ts))
  if [ "$elapsed" -ge "$TIMEOUT" ]; then
    echo "ERROR: Nomad leader not elected within ${TIMEOUT}s (last response: ${leader:-empty})" >&2
    exit 1
  fi

  sleep "$POLL_INTERVAL"
done
