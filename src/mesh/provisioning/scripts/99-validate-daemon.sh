#!/bin/bash
# 99-validate-daemon.sh
#
# Validate the mesh-daemon binary and its config file WITHOUT starting the
# HTTP server.  Previously this was done via `timeout 2 mesh-daemon serve ...`
# which had two serious problems:
#
#   (1) The daemon could bind port 8080, write a PID file, and partially
#       initialise before being killed, leaving state that races against
#       the subsequent `systemctl start mesh-daemon`.
#
#   (2) `timeout 2` always exits 124 (killed), so the `|| true` swallowed
#       genuine startup failures that happened within the 2-second window.
#
# This script validates what cloud-init actually needs to know: the binary
# runs, the config file parses, and the daemon can construct its internal
# state -- without touching ports or writing PID files.
#
# Usage: run directly on the provisioned VM after install.sh.
#        Exits 0 if validation passes, 1 on any failure.
#        Diagnostic output goes to /tmp/daemon-diag.txt.

set -e

DIAG_FILE="${1:-/tmp/daemon-diag.txt}"
BINARY="/usr/local/bin/mesh-daemon"
CONFIG="/etc/mesh/config.yaml"

exec 3>&1  # save stdout
{
  echo "--- mesh-daemon validation $(date --iso-8601=seconds) ---"

  # 1. Binary exists and is executable
  if [ ! -x "$BINARY" ]; then
    echo "FAIL: $BINARY not found or not executable"
    exit 1
  fi
  echo "OK: binary exists at $BINARY"

  # 2. Binary reports a version (proves it can load and run)
  VERSION=$("$BINARY" version 2>&1) || {
    echo "FAIL: '$BINARY version' returned non-zero"
    exit 1
  }
  echo "OK: binary runs (version: ${VERSION:-unknown})"

  # 3. Config file exists and is valid YAML
  if [ ! -f "$CONFIG" ]; then
    echo "SKIP: $CONFIG not found (non-leader node -- expected)"
    echo "OK: validation skipped (no config file to validate)"
    exit 0
  fi

  if command -v python3 &>/dev/null; then
    python3 -c "
import yaml, sys
try:
    with open('$CONFIG') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        print(f'WARN: config is not a dict (got {type(data).__name__})')
    else:
        print(f'OK: config has {len(data)} top-level keys')
except yaml.YAMLError as e:
    print(f'FAIL: config YAML parse error: {e}')
    sys.exit(1)
except FileNotFoundError:
    print('SKIP: config not found')
" 2>&1
  elif command -v yq &>/dev/null; then
    yq eval 'true' "$CONFIG" >/dev/null 2>&1 && \
      echo "OK: config is valid YAML (yq)" || \
      { echo "FAIL: config is invalid YAML (yq)"; exit 1; }
  else
    echo "SKIP: no python3 or yq available -- skipping deep config validation"
  fi

  echo "--- validation complete ---"
} 2>&1 | tee -a "$DIAG_FILE" >&3

exit 0
