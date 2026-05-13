"""
mesh-provision — subprocess entry point.

Protocol:
    stdin  ← one JSON envelope  {"version": "1", "command": "...", "params": {...}}
    stdout → one JSON result     {"cluster_id": ..., "leader_ip": ..., ...}
    stderr → one JSON error      {"error": {"code": "...", "message": "..."}}

Exit codes:
    0 = success (result on stdout)
    1 = error   (error on stderr)

Usage:
    echo '{"version":"1","command":"init","params":{...}}' | python3 -m mesh.cli init --input stdin --output json
    # OR directly:
    echo '{"version":"1","command":"init","params":{...}}' | python3 -c "from mesh.entrypoint import main; main()"
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    raw = sys.stdin.read()

    # Parse envelope
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fatal("invalid_json", f"Invalid JSON on stdin: {exc}")

    if not isinstance(msg, dict):
        _fatal("invalid_json", "Expected a JSON object on stdin")

    if msg.get("version") != "1":
        _fatal(
            "unsupported_version",
            f"Unsupported version {msg.get('version')!r}. Expected: \"1\"",
        )

    command = msg.get("command")
    params = msg.get("params", {})

    if not isinstance(params, dict):
        _fatal("invalid_json", "\"params\" must be a JSON object")

    # Dispatch
    if command == "init":
        from mesh.commands.init import handle_init
        handle_init(params)

    elif command == "destroy":
        from mesh.commands.destroy import handle_destroy
        handle_destroy(params)

    elif command == "add-worker":
        from mesh.commands.add_worker import handle_add_worker
        handle_add_worker(params)

    elif command == "remove-worker":
        from mesh.commands.remove_worker import handle_remove_worker
        handle_remove_worker(params)

    elif command == "status":
        from mesh.commands.status import handle_status
        handle_status(params)

    else:
        _fatal(
            "unknown_command",
            f"Unknown command {command!r}. Valid commands: init, destroy, add-worker, remove-worker, status",
        )


def _fatal(code: str, message: str) -> None:
    """Write a pre-dispatch error to stderr and exit 1."""
    sys.stderr.write(
        json.dumps({"version": "1", "status": "error", "error": {"code": code, "message": message}})
        + "\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
