"""
MANIFEST.yaml loader and direct-use guard.

Reads code/mesh-provision/MANIFEST.yaml and enforces the ``direct_use``
policy declared there.  Any dangerous/mutating command (init, destroy,
add-worker, remove-worker) is blocked when called via the stdin CLI unless
the caller opts out with an explicit bypass environment variable.

Design rationale
----------------
- The MANIFEST is the single source of truth for usage policy.  If the policy
  changes, no code changes are needed — only the YAML.
- Bypass (``MESH_PROVISION_ALLOW_DIRECT``) exists *only* for development and
  E2E tests on ephemeral infrastructure.  Production deployments MUST NOT set
  it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_MANIFEST_FILENAME = "MANIFEST.yaml"

# The manifest lives at code/mesh-provision/MANIFEST.yaml.
# We find it by walking up from this file's own location:
#   src/mesh/manifest.py  →  .. (mesh/)  →  .. (src/)  →  .. (mesh-provision/)  →  MANIFEST.yaml
_MANIFEST_PATH = (Path(__file__).resolve().parent.parent.parent / _MANIFEST_FILENAME).resolve()

# ---------------------------------------------------------------------------
# Bypass
# ---------------------------------------------------------------------------

_BYPASS_ENV_VAR = "MESH_PROVISION_ALLOW_DIRECT"

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_manifest: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_manifest() -> dict[str, Any]:
    """Load and cache ``MANIFEST.yaml``.

    Returns the parsed YAML as a dict, or raises ``FileNotFoundError``.
    """
    global _manifest
    if _manifest is not None:
        return _manifest

    if not _MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            f"Cannot find {_MANIFEST_FILENAME} — expected at {_MANIFEST_PATH}. "
            f"If you have moved the project, set {_BYPASS_ENV_VAR}=1 to bypass."
        )

    with open(_MANIFEST_PATH) as f:
        _manifest = yaml.safe_load(f)

    if not isinstance(_manifest, dict):
        raise ValueError(f"{_MANIFEST_FILENAME} did not parse as a YAML mapping")

    return _manifest


def is_direct_use_forbidden() -> bool:
    """Return ``True`` if the manifest declares ``direct_use: false``."""
    manifest = load_manifest()
    val = manifest.get("direct_use", True)
    # Treat explicit false / "false" / "no" as forbidden.
    if isinstance(val, bool):
        return not val
    if isinstance(val, str):
        return val.strip().lower() in ("false", "no", "0")
    return True  # treat anything else as forbidden


def warn_forbidden_command(command: str) -> None:
    """Print a structured warning to stderr and exit 1.

    Called by ``entrypoint.py`` when a forbidden command is invoked directly
    through the stdin CLI.
    """
    manifest = load_manifest()
    warning = manifest.get("warning", "Command is FORBIDDEN when called directly")

    sys.stderr.write(
        yaml.dump(
            {
                "error": {
                    "code": "direct_use_forbidden",
                    "message": (
                        f"Command {command!r} is FORBIDDEN via the stdin CLI.\n\n"
                        f"{warning}\n\n"
                        f"mesh-provision must only be called through agent-bodies, "
                        f"which proxies to the HTTP API on port 8100. "
                        f"Calling the CLI directly bypasses Auth0, database tracking, "
                        f"config generation, and audit logging — creating orphan VMs "
                        f"that have no DB row, no cluster_id, and no daemon_config.\n\n"
                        f"To bypass this guard for local development, set:\n"
                        f"  {_BYPASS_ENV_VAR}=1"
                    ),
                }
            },
            default_flow_style=False,
        ).strip()
        + "\n"
    )
    sys.exit(1)


def guard_command(command: str) -> None:
    """Check whether *command* may be run via the stdin CLI.

    Exits with a structured error if the command is forbidden and no bypass
    is active.

    Logic
    -----
    1. If ``MESH_PROVISION_ALLOW_DIRECT`` is set → allow.
    2. If MANIFEST.yaml declares ``direct_use: false`` → block *all* commands
       (this is the blanket policy — ``direct_cli_use: FORBIDDEN`` on individual
       capabilities is documentary but redundant).
    3. If MANIFEST.yaml is missing and the command is mutating (init, destroy,
       add-worker, remove-worker) → block (fail-closed).
    4. If MANIFEST.yaml declares ``direct_use`` true → allow.

    Bypass
    ------
    Set ``MESH_PROVISION_ALLOW_DIRECT=1`` in the environment to bypass the
    guard for local development and E2E tests.
    """
    # ---- bypass check ----------------------------------------------------
    if os.environ.get(_BYPASS_ENV_VAR, "").strip() in ("1", "true", "yes"):
        return

    # ---- manifest check --------------------------------------------------
    try:
        if is_direct_use_forbidden():
            # Blanket policy: direct_use: false blocks ALL commands.
            warn_forbidden_command(command)
    except (FileNotFoundError, ValueError):
        # Fail-closed: if MANIFEST can't be loaded, block mutating commands.
        if command in ("init", "destroy", "add-worker", "remove-worker"):
            warn_forbidden_command(command)
        # Read-only commands (status) are allowed when MANIFEST is missing.
        return
