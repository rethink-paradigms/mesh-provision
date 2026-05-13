"""
JSON output helpers for all commands.

Rules:
  - Success  → stdout, exit 0   (call print_json_success)
  - Error    → stderr, exit 1   (call print_json_error)
  - These functions never return — they always call sys.exit.
  - All other code in commands/ calls these and nothing else for I/O.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Core I/O
# ---------------------------------------------------------------------------


def print_json_success(data: dict[str, Any]) -> None:
    """Write JSON to stdout and exit 0."""
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
    """Write structured JSON error to stderr and exit 1."""
    body: dict[str, Any] = {"code": code, "message": message}
    if phase is not None:
        body["phase"] = phase
    if partial_resources is not None:
        body["partial_resources"] = partial_resources
    if available_providers is not None:
        body["available_providers"] = available_providers
    if missing_args is not None:
        body["missing_args"] = missing_args

    sys.stderr.write(json.dumps({"error": body}, indent=2) + "\n")
    sys.exit(1)


def require_args(context: str, params: dict[str, Any], *names: str) -> None:
    """Exit with missing_required_args error if any named param is absent/empty.

    Args:
        context: Command name for error messages (e.g. "init").
        params:  The params dict from the request envelope.
        *names:  Required param names to check.
    """
    missing = [n for n in names if not params.get(n)]
    if missing:
        print_json_error(
            code="missing_required_args",
            message=f"[{context}] Required parameters missing: {', '.join(missing)}",
            missing_args=missing,
        )


# ---------------------------------------------------------------------------
# Response shape builders
# ---------------------------------------------------------------------------


def init_success(
    cluster_name: str,
    leader_ip: str,
    status: str,
    nodes: list[dict[str, str]],
) -> dict[str, Any]:
    """Build the canonical init success response (matches contract §3a)."""
    return {
        "cluster_id": cluster_name,
        "leader_ip": leader_ip,
        "status": status,
        "nodes": nodes,
    }


def destroy_success(
    cluster_name: str,
    resources_cleaned: list[str],
) -> dict[str, Any]:
    """Build the canonical destroy success response (matches contract §3b)."""
    return {
        "cluster_id": cluster_name,
        "status": "destroyed",
        "destroyed": True,
        "resources_cleaned": resources_cleaned,
    }


def add_worker_success(node_ip: str, node_id: str) -> dict[str, Any]:
    """Build the canonical add-worker success response (matches contract §3d)."""
    return {
        "node": {
            "ip": node_ip,
            "id": node_id,
            "role": "worker",
        }
    }


def status_success(
    cluster_name: str,
    exists: bool,
    nodes: list[dict[str, str]],
) -> dict[str, Any]:
    """Build the canonical status success response (matches contract §3c)."""
    return {
        "cluster_name": cluster_name,
        "exists": exists,
        "nodes": nodes,
    }


# ---------------------------------------------------------------------------
# Demo builders (structurally identical to real responses, demo=True marker)
# ---------------------------------------------------------------------------


def demo_init(
    cluster_name: str,
    provider: str,
    region: str,
    workers: int,
    leader_size: str,
) -> dict[str, Any]:
    """Synthetic init response using RFC 5737 test IPs."""
    nodes = [{"id": f"demo-{cluster_name}-leader", "ip": "192.0.2.1", "role": "leader"}]
    nodes += [
        {"id": f"demo-{cluster_name}-worker-{i}", "ip": f"192.0.2.{2 + i}", "role": "worker"}
        for i in range(workers)
    ]
    return {
        "cluster_id": cluster_name,
        "leader_ip": "192.0.2.1",
        "status": "ready",
        "nodes": nodes,
        "demo": True,
    }


def demo_destroy(cluster_name: str) -> dict[str, Any]:
    return {
        "cluster_id": cluster_name,
        "status": "destroyed",
        "destroyed": True,
        "resources_cleaned": [],
        "demo": True,
    }


def demo_add_worker() -> dict[str, Any]:
    return {
        "node": {"ip": "192.0.2.99", "id": "demo-worker-new", "role": "worker"},
        "demo": True,
    }
