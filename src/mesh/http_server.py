"""
mesh-provision HTTP server.

Provides an HTTP API for cluster lifecycle management, wrapping the same
business logic used by the stdin/stdout CLI protocol.

Usage:
    # Via the mesh CLI:
    mesh serve

    # Directly with uvicorn:
    uvicorn mesh.http_server:app --port 8100

    # Or as a module:
    python -m mesh.http_server

Design:
    - Zero changes to existing CLI handlers (commands/*.py) — they keep working.
    - The HTTP server has its own _handle_* functions that call the same
      underlying business logic (provision_cluster, query_cluster, etc.)
      but raise HTTPException for errors instead of calling sys.exit().
    - POST /api/provision accepts the same JSON envelope as the stdin protocol
      making the migration from subprocess to HTTP a pure transport swap.
"""

from __future__ import annotations

import asyncio
import hmac
import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Reuse all business logic — no changes to existing CLI code
from mesh.commands.output import (
    add_worker_success,
    destroy_success,
    init_success,
    remove_worker_success,
    status_success,
)
from mesh.providers import USABLE_PROVIDERS, is_provider_usable
from mesh.provisioning.boot import generate_cloud_init
from mesh.provisioning.direct import (
    destroy_cluster,
    poll_daemon_health,
    provision_cluster,
    provision_node,
    query_cluster,
    remove_worker as remove_worker_fn,
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="mesh-provision",
    version="0.4.0",
    description="Lightweight cluster provisioner — HTTP API",
)

# ---------------------------------------------------------------------------
# Stale-code detection — warn if .py files were modified after process start
# ---------------------------------------------------------------------------

import os as _os
from datetime import datetime as _datetime
from pathlib import Path as _Path

_START_TIME = _datetime.now()


def _check_stale_code():
    """Log a warning if any .py file in this package is newer than the process."""
    import logging as _logging
    try:
        pkg_root = _Path(__file__).parent
        newer: list[str] = []
        for f in pkg_root.rglob("*.py"):
            mtime = _datetime.fromtimestamp(f.stat().st_mtime)
            if mtime > _START_TIME:
                newer.append(str(f.relative_to(pkg_root)))
        if newer:
            _logging.warning(
                "mesh-provision started at %s but %d file(s) were modified later. "
                "You may be running stale code. Run 'make restart-mesh-provision' to reload. "
                "Stale files: %s",
                _START_TIME.isoformat(),
                len(newer),
                ", ".join(newer[:5]) + ("..." if len(newer) > 5 else ""),
            )
    except Exception:
        pass  # Non-fatal — fallback if anything goes wrong


@app.on_event("startup")
async def _startup():
    _check_stale_code()


# ---------------------------------------------------------------------------
# Authentication
#
# Production: set MESH_PROVISION_API_KEY to a strong random value.
#   agent-bodies sends it as:  Authorization: Bearer <key>
#   mesh-provision validates via constant-time comparison.
# Development: leave MESH_PROVISION_API_KEY unset (no auth).
#   Optionally set DEV_TEST_AUTH_SECRET for dev bypass matching
#   the agent-bodies pattern (send X-Dev-Test-Auth header).
# ---------------------------------------------------------------------------

_AUTH_KEY = os.environ.get("MESH_PROVISION_API_KEY", "")
_DEV_TEST_SECRET = os.environ.get("DEV_TEST_AUTH_SECRET", "")


@app.middleware("http")
async def _verify_auth_header(request: Request, call_next):
    # Health check is always public.
    if request.url.path == "/health":
        return await call_next(request)

    # No configured key → auth is disabled (dev mode).
    if not _AUTH_KEY:
        return await call_next(request)

    # Dev bypass — matches agent-bodies X-Dev-Test-Auth pattern.
    dev_header = request.headers.get("x-dev-test-auth", "")
    if _DEV_TEST_SECRET and hmac.compare_digest(dev_header, _DEV_TEST_SECRET):
        return await call_next(request)

    # Production auth: validate Authorization: Bearer <key>
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "unauthorized",
                    "message": "Missing or invalid Authorization header",
                }
            },
        )

    token = auth_header.removeprefix("Bearer ")
    if not hmac.compare_digest(token, _AUTH_KEY):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "unauthorized",
                    "message": "Invalid API key",
                }
            },
        )

    return await call_next(request)

# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class ProvisionRequest(BaseModel):
    """Matches the stdin JSON envelope format from the v1 protocol."""

    version: str = "1"
    command: str
    params: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _validate_provider(provider: str) -> None:
    if not is_provider_usable(provider):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unknown_provider",
                "message": (
                    f"Provider {provider!r} is not supported. "
                    f"Available: {', '.join(sorted(USABLE_PROVIDERS))}"
                ),
                "available_providers": sorted(USABLE_PROVIDERS),
            },
        )


def _require_params(command: str, params: dict[str, Any], *names: str) -> None:
    missing = [n for n in names if not params.get(n)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "missing_required_args",
                "message": f"[{command}] Required parameters missing: {', '.join(missing)}",
                "missing_args": missing,
            },
        )


def _resolve_api_key(provider: str, api_key: str) -> str:
    """Fall back to environment variables if no api_key was provided."""
    if api_key:
        return api_key
    from mesh.config.env import get_env

    _ENV_FALLBACKS = {
        "digitalocean": ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"],
        "do": ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"],
        "aws": ["AWS_ACCESS_KEY_ID"],
        "linode": ["LINODE_API_KEY"],
        "vultr": ["VULTR_API_KEY"],
    }
    for var in _ENV_FALLBACKS.get(provider, []):
        value = get_env(var)
        if value:
            return value
    raise HTTPException(
        status_code=400,
        detail={
            "code": "missing_credentials",
            "message": (
                f"No API key provided for {provider!r} "
                f"and no matching environment variable found."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Command handlers  (mirror the CLI handlers but use HTTPException)
# ---------------------------------------------------------------------------


def _handle_init(params: dict[str, Any]) -> dict[str, Any]:
    """Provision a cluster — mirrors handle_init in commands/init.py."""

    if params.get("demo"):
        from mesh.commands.output import demo_init

        return demo_init(
            cluster_name=params.get("cluster_name", "demo-cluster"),
            provider=params.get("provider", "digitalocean"),
            region=params.get("region", "nyc3"),
            workers=int(params.get("workers", 0)),
            leader_size=params.get("leader_size", "s-2vcpu-4gb"),
        )

    _require_params(
        "init", params, "provider", "region", "cluster_name", "leader_size", "api_key"
    )

    provider = params["provider"].lower()
    region = params["region"]
    cluster_name = params["cluster_name"]
    leader_size = params["leader_size"]
    api_key = params["api_key"]
    workers = int(params.get("workers", 0))
    worker_size = params.get("worker_size", "s-1vcpu-1gb")
    daemon_config: str | None = params.get("daemon_config") or None
    tailscale_key: str = params.get("tailscale_key", "")
    cluster_id: str = params.get("cluster_id", "")

    _validate_provider(provider)

    cluster_tier = "solo" if workers == 0 else "cluster"

    try:
        leader_boot = generate_cloud_init(
            role="server",
            cluster_tier=cluster_tier,
            tailscale_key=tailscale_key,
            leader_ip="",
            daemon_config=daemon_config,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "provision_failed",
                "message": f"Leader boot script generation failed: {exc}",
                "phase": "boot_script_leader",
            },
        )

    def _make_worker_boot(leader_ip: str) -> str:
        return generate_cloud_init(
            role="client",
            cluster_tier=cluster_tier,
            tailscale_key=tailscale_key,
            leader_ip=leader_ip,
            daemon_config=None,
        )

    try:
        cluster = provision_cluster(
            name=cluster_name,
            provider=provider,
            region=region,
            leader_size=leader_size,
            worker_size=worker_size,
            workers=workers,
            api_key=api_key,
            leader_boot_script=leader_boot,
            worker_boot_script_fn=_make_worker_boot,
            tags=[cluster_name, "e2e", f"cluster:{cluster_id}"] if cluster_id else [cluster_name, "e2e"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "provision_failed",
                "message": str(exc),
                "phase": "create_vm",
            },
        )

    leader = cluster["leader"]
    leader_ip = leader.get("public_ip") or leader.get("private_ip") or ""

    health_status = (
        "ready" if leader_ip and poll_daemon_health(leader_ip) else "provisioned"
    )

    nodes = [{"id": leader.get("instance_id", ""), "ip": leader_ip, "role": "leader"}]
    for w in cluster.get("workers", []):
        nodes.append(
            {
                "id": w.get("instance_id", ""),
                "ip": w.get("public_ip") or w.get("private_ip") or "",
                "role": "worker",
            }
        )

    return init_success(
        cluster_name=cluster_name,
        leader_ip=leader_ip,
        status=health_status,
        nodes=nodes,
    )


def _handle_destroy(params: dict[str, Any]) -> dict[str, Any]:
    """Tear down a cluster — mirrors handle_destroy in commands/destroy.py."""

    if params.get("demo"):
        from mesh.commands.output import demo_destroy

        return demo_destroy(params.get("cluster_name", "demo-cluster"))

    _require_params("destroy", params, "cluster_name")

    cluster_name = params["cluster_name"]
    provider = (params.get("provider") or "digitalocean").lower()
    region = params.get("region", "")
    cleanup_all = bool(params.get("cleanup_all", False))
    api_key = _resolve_api_key(provider, params.get("api_key", ""))
    node_ids: list[str] | None = params.get("node_ids")

    _validate_provider(provider)

    try:
        result = destroy_cluster(
            provider=provider,
            api_key=api_key,
            region=region,
            cluster_name=cluster_name,
            cleanup_all=cleanup_all,
            node_ids=node_ids,
        )
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=501,
            detail={
                "code": "provision_failed",
                "message": str(exc),
                "phase": "destroy",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "provision_failed",
                "message": str(exc),
                "phase": "destroy_resources",
            },
        )

    return destroy_success(
        cluster_name=cluster_name,
        resources_cleaned=result.get("resources_cleaned", []),
    )


def _handle_status(params: dict[str, Any]) -> dict[str, Any]:
    """Query cluster status — mirrors handle_status in commands/status.py."""

    _require_params("status", params, "provider", "cluster_name", "api_key")

    provider = params["provider"].lower()
    cluster_name = params["cluster_name"]
    api_key = params["api_key"]
    region = params.get("region", "")

    _validate_provider(provider)

    try:
        result = query_cluster(
            provider=provider,
            api_key=api_key,
            cluster_name=cluster_name,
            region=region,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "status_failed",
                "message": str(exc),
                "phase": "query_status",
            },
        )

    return status_success(
        cluster_name=result["cluster_name"],
        exists=result["exists"],
        nodes=result["nodes"],
    )


def _handle_add_worker(params: dict[str, Any]) -> dict[str, Any]:
    """Add a worker node — mirrors handle_add_worker in commands/add_worker.py."""

    if params.get("demo"):
        from mesh.commands.output import demo_add_worker

        return demo_add_worker()

    _require_params(
        "add-worker",
        params,
        "provider",
        "region",
        "cluster_name",
        "worker_size",
        "leader_ip",
        "api_key",
    )

    provider = params["provider"].lower()
    region = params["region"]
    cluster_name = params["cluster_name"]
    worker_size = params["worker_size"]
    leader_ip = params["leader_ip"]
    api_key = params["api_key"]
    tailscale_key = params.get("tailscale_key", "")

    cluster_tier = "cluster"
    _validate_provider(provider)

    try:
        boot_script = generate_cloud_init(
            role="client",
            cluster_tier=cluster_tier,
            tailscale_key=tailscale_key,
            leader_ip=leader_ip,
            daemon_config=None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "provision_failed",
                "message": f"Worker boot script generation failed: {exc}",
                "phase": "boot_script_worker",
            },
        )

    worker_name = f"{cluster_name}-worker-{int(time.time())}"

    try:
        node = provision_node(
            name=worker_name,
            provider=provider,
            region=region,
            size_id=worker_size,
            api_key=api_key,
            boot_script=boot_script,
            tags=[cluster_name, "e2e"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "provision_failed",
                "message": str(exc),
                "phase": "create_worker_vm",
            },
        )

    return add_worker_success(
        node_ip=node.get("public_ip") or node.get("private_ip") or "",
        node_id=node.get("instance_id", ""),
    )


def _handle_remove_worker(params: dict[str, Any]) -> dict[str, Any]:
    """Remove a worker node — mirrors handle_remove_worker in commands/remove_worker.py."""

    if params.get("demo"):
        from mesh.commands.output import demo_remove_worker

        return demo_remove_worker()

    _require_params("remove-worker", params, "provider", "cluster_name", "api_key")

    provider = params["provider"].lower()
    cluster_name = params["cluster_name"]
    api_key = params["api_key"]
    region = params.get("region", "")
    node_id = params.get("node_id", "")
    node_name = params.get("node_name", "")

    if not node_id and not node_name:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "missing_required_args",
                "message": "remove-worker requires either 'node_id' or 'node_name'.",
                "missing_args": ["node_id or node_name"],
            },
        )

    _validate_provider(provider)

    try:
        result = remove_worker_fn(
            provider=provider,
            api_key=api_key,
            region=region,
            cluster_name=cluster_name,
            node_id=node_id,
            node_name=node_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "provision_failed",
                "message": str(exc),
                "phase": "remove_worker_validate",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "provision_failed",
                "message": str(exc),
                "phase": "remove_worker",
            },
        )

    return remove_worker_success(
        node_id=result["node_id"],
        node_name=result["node_name"],
    )


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

COMMAND_MAP: dict[str, callable] = {
    "init": _handle_init,
    "destroy": _handle_destroy,
    "status": _handle_status,
    "add-worker": _handle_add_worker,
    "remove-worker": _handle_remove_worker,
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/api/provision")
async def provision(req: ProvisionRequest):
    """Unified provisioning endpoint — accepts the same envelope as stdin protocol.

    The request body mirrors the stdin JSON format:

        {"version": "1", "command": "init", "params": {...}}

    This makes the migration from subprocess to HTTP a pure transport swap —
    no changes to the request/response contract.
    """
    if req.version != "1":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unsupported_version",
                "message": f'Unsupported version {req.version!r}. Expected: "1"',
            },
        )

    if not isinstance(req.params, dict):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_json",
                "message": '"params" must be a JSON object',
            },
        )

    handler = COMMAND_MAP.get(req.command)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unknown_command",
                "message": (
                    f"Unknown command {req.command!r}. "
                    "Valid commands: init, destroy, add-worker, remove-worker, status"
                ),
            },
        )

    result = await asyncio.get_running_loop().run_in_executor(None, handler, req.params)
    return result


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the HTTP server.

    Usage:
        mesh serve
    """
    import uvicorn

    uvicorn.run(
        "mesh.http_server:app",
        host="0.0.0.0",
        port=8100,
        log_level="info",
    )


if __name__ == "__main__":
    main()
