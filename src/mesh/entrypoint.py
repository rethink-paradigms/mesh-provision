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

Direct-use guard:
    entrypoint.py checks ``MANIFEST.yaml`` before dispatching any command.
    Commands declared as ``direct_use: false`` or ``direct_cli_use: FORBIDDEN``
    are blocked with a structured error.  See ``mesh/manifest.py`` for details.
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    # Handle --help or no input on TTY
    if "--help" in sys.argv or "-h" in sys.argv:
        print("mesh-provision — lightweight cluster orchestrator")
        print("\nUsage:")
        print("  echo '{\"command\": \"init\", ...}' | mesh")
        print("\nCommands:")
        print("  init, destroy, add-worker, remove-worker, status")
        sys.exit(0)

    if sys.stdin.isatty():
        print("Error: No input provided on stdin. mesh-provision expects a JSON envelope.", file=sys.stderr)
        print("Use 'mesh --help' for usage information.", file=sys.stderr)
        sys.exit(1)

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

    # ---- Direct-use guard -----------------------------------------------
    # Check MANIFEST.yaml before dispatching any command that creates,
    # destroys, or modifies infrastructure.  The HTTP API (port 8100) is
    # the only valid entry point — it has its own auth and audit path via
    # agent-bodies.  This guard is a safety net so that anyone who pipes
    # JSON into the CLI gets a clear error instead of accidentally creating
    # an orphan VM.
    try:
        from mesh.manifest import guard_command

        guard_command(command)
    except ImportError:
        pass  # bare install / tests — guard is best-effort

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
