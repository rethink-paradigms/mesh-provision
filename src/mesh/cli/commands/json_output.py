"""
JSON output serializers and error handlers for JSON mode commands.

These pure functions handle all structured output for --output json mode,
keeping stdout (success) and stderr (errors) cleanly separated so that
automated tooling can parse results reliably.

Usage
-----
    from mesh.cli.commands.json_output import (
        print_json_success,
        print_json_error,
        require_json_mode_args,
    )

    # Validate required args — exits with JSON error if any missing
    args = require_json_mode_args(
        provider=provider,
        workers=workers,
        daemon_url=daemon_url,
    )

    # ... do the work ...

    # Success — writes to stdout, exits 0
    print_json_success({"status": "ok", "leader_ip": "10.0.0.1"})

    # Error — writes to stderr, exits 1
    print_json_error(code="provision_failed", message="No VMs available")
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any, Optional


def print_json_success(data: dict[str, Any]) -> None:
    """Print JSON data to stdout and exit 0.

    Used for all successful JSON-mode command completions.

    Parameters
    ----------
    data : dict
        The JSON-serialisable result payload.
    """
    sys.stdout.write(json.dumps(data, indent=2) + "\n")
    sys.exit(0)


def print_json_error(
    *,
    code: str,
    message: str,
    phase: Optional[str] = None,
    partial_resources: Optional[list[Any]] = None,
    available_providers: Optional[list[str]] = None,
    missing_args: Optional[list[str]] = None,
) -> None:
    """Print a structured JSON error to stderr and exit 1.

    All parameters are keyword-only so callers are explicit about which
    error shape they are producing.

    Parameters
    ----------
    code : str
        Machine-readable error code.  Supported values:
        ``missing_required_args``, ``unknown_provider``,
        ``missing_credentials``, ``provision_failed``.
    message : str
        Human-readable error description.
    phase : str, optional
        The provisioning phase where the error occurred.
    partial_resources : list, optional
        Resources that were successfully created before failure.
    available_providers : list[str], optional
        List of supported provider names (for ``unknown_provider``).
    missing_args : list[str], optional
        Names of missing required arguments (for ``missing_required_args``).
    """
    error_body: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if phase is not None:
        error_body["phase"] = phase
    if partial_resources is not None:
        error_body["partial_resources"] = partial_resources
    if available_providers is not None:
        error_body["available_providers"] = available_providers
    if missing_args is not None:
        error_body["missing_args"] = missing_args

    error_dict = {"error": error_body}
    sys.stderr.write(json.dumps(error_dict, indent=2) + "\n")
    sys.exit(1)


def require_json_mode_args(**kwargs: Any) -> dict[str, Any]:
    """Validate required keyword arguments for JSON-mode commands.

    Every argument whose value is ``None`` or the empty string ``""`` is
    treated as *missing*.  If any are missing the function calls
    :func:`print_json_error` with ``code="missing_required_args"`` and
    exits immediately.

    Parameters
    ----------
    **kwargs : Any
        Named arguments to validate (e.g. ``provider=..., workers=...``).

    Returns
    -------
    dict
        A merged dict of all non-None, non-empty-string argument values,
        ready to be destructured with ``**`` or inspected directly.
    """
    missing: list[str] = []

    cleaned: dict[str, Any] = {}
    for name, value in kwargs.items():
        if value is None or value == "":
            missing.append(name)
        else:
            cleaned[name] = value

    if missing:
        print_json_error(
            code="missing_required_args",
            message=f"Required arguments missing: {', '.join(missing)}",
            missing_args=missing,
        )
        # print_json_error calls sys.exit(1), so this line is unreachable
        # but it's here to satisfy type-checkers.
        raise SystemExit(1)

    return cleaned


# ---------------------------------------------------------------------------
# Demo mode JSON factories
# ---------------------------------------------------------------------------


def build_demo_init_json(
    cluster_name: str,
    provider: str,
    region: str,
    workers: int,
    leader_size: str,
) -> dict[str, Any]:
    """Build synthetic init JSON for demo mode. Uses RFC 5737 test IPs.

    Produces structurally identical JSON to real mode — same keys, types, and
    nesting — but with ``"demo": true`` and no cloud API calls.

    Parameters
    ----------
    cluster_name : str
        Cluster name supplied via ``--cluster-name``.
    provider : str
        Cloud provider slug (e.g. ``"digitalocean"``).
    region : str
        Provider region (e.g. ``"nyc3"``).
    workers : int
        Number of worker nodes to simulate.
    leader_size : str
        VM size for the leader (e.g. ``"s-2vcpu-4gb"``).

    Returns
    -------
    dict
        JSON-serialisable payload matching spec §6.2 init shape.
    """
    tier = "lite" if workers == 0 else "standard"
    return {
        "cluster_id": cluster_name,
        "provider": provider,
        "region": region,
        "tier": tier,
        "leader": {
            "ip": "192.0.2.1",
            "id": f"demo-{cluster_name}-leader",
            "size": leader_size,
        },
        "workers": [
            {
                "ip": f"192.0.2.{2 + i}",
                "id": f"demo-{cluster_name}-worker-{i}",
                "size": "s-1vcpu-1gb",
            }
            for i in range(workers)
        ],
        "nomad_addr": "http://127.0.0.1:4646",
        "daemon_url": f"https://daemon-{cluster_name}.agentbodies.com",
        "daemon_token": "demo-token-placeholder",
        "caddy_admin": "http://127.0.0.1:2019",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "demo": True,
    }


def to_brief_shape(result: dict, status: str = "ready") -> dict:
    """Transform rich init JSON result into BRIEF-compliant flat shape.

    Pure function — no side effects, no ``sys.exit``.

    Parameters
    ----------
    result : dict
        Rich init JSON result (as produced by ``build_demo_init_json`` or
        the real provisioning path).
    status : str, optional
        Cluster health status. Defaults to ``"ready"``.

    Returns
    -------
    dict
        Flat shape with ``cluster_id``, ``leader_ip``, ``status``, and
        ``nodes`` (list of ``{id, ip, role}`` dicts).
    """
    leader = result.get("leader", {})
    if isinstance(leader, dict):
        leader_ip = leader.get("ip", "")
    else:
        leader_ip = ""

    nodes = []
    if isinstance(leader, dict) and (leader.get("id") or leader.get("ip")):
        nodes.append({
            "id": leader.get("id", ""),
            "ip": leader.get("ip", ""),
            "role": "leader",
        })

    workers = result.get("workers", [])
    if isinstance(workers, list):
        for w in workers:
            if isinstance(w, dict) and (w.get("id") or w.get("ip")):
                nodes.append({
                    "id": w.get("id", ""),
                    "ip": w.get("ip", ""),
                    "role": "worker",
                })

    return {
        "cluster_id": result.get("cluster_id", ""),
        "leader_ip": leader_ip,
        "status": status,
        "nodes": nodes,
    }


def build_demo_destroy_json(cluster_name: str) -> dict[str, Any]:
    """Build synthetic destroy JSON for demo mode.

    Parameters
    ----------
    cluster_name : str
        Cluster name supplied via ``--cluster``.

    Returns
    -------
    dict
        JSON-serialisable payload matching spec §6.2 destroy shape.
    """
    return {
        "cluster_id": cluster_name,
        "status": "destroyed",
        "destroyed": True,
        "resources_cleaned": [],
        "demo": True,
    }


def to_brief_destroy_shape(result: dict, cluster_name: str) -> dict:
    """Transform destroy result into BRIEF-compliant flat shape.

    Pure function — no side effects, no ``sys.exit``.

    Parameters
    ----------
    result : dict
        Destroy result (from ``destroy_resources_direct`` or demo builder).
    cluster_name : str
        Cluster name.

    Returns
    -------
    dict
        Flat shape with ``cluster_id``, ``status``, ``destroyed``, and
        ``resources_cleaned`` keys.
    """
    return {
        "cluster_id": cluster_name,
        "status": "destroyed",
        "destroyed": True,
        "resources_cleaned": result.get("resources_cleaned", []),
    }


def build_demo_add_worker_json() -> dict[str, Any]:
    """Build synthetic add-worker JSON for demo mode.

    Returns a realistic fake worker node with an RFC 5737 test IP and the
    ``"demo": true`` marker.  No cloud API calls are made.

    Returns
    -------
    dict
        JSON-serialisable payload matching spec §6.2 add-worker shape.
    """
    return {
        "node": {
            "ip": "192.0.2.99",
            "id": "demo-worker-new",
            "role": "worker",
        },
        "demo": True,
    }
