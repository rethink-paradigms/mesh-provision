from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from mesh.cli.commands.add_worker import _run_add_worker_json
from mesh.cli.commands.destroy import _run_destroy_json
from mesh.cli.commands.json_output import (
    build_demo_init_json,
    print_json_error,
    print_json_success,
    require_json_mode_args,
    to_brief_shape,
)
from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import (
    generate_cloud_init_yaml,
)
from mesh.infrastructure.config.env import EnvVars, get_env
from mesh.infrastructure.providers import PROVIDER_ENUMS, UNSUPPORTED_PROVIDERS
from mesh.infrastructure.provision_node.provision_direct import (
    provision_cluster_direct,
    query_cluster_status,
)

_PROVIDER_ENV_MAP: dict[str, str] = {
    "digitalocean": EnvVars.DIGITALOCEAN_API_TOKEN,
    "aws": EnvVars.AWS_ACCESS_KEY_ID,
    "linode": EnvVars.LINODE_API_KEY,
    "vultr": EnvVars.VULTR_API_KEY,
    "google": EnvVars.GOOGLE_CREDENTIALS,
    "gcp": EnvVars.GOOGLE_CREDENTIALS,
    "azure": EnvVars.AZURE_CLIENT_SECRET,
    "upcloud": EnvVars.UPCLOUD_PASSWORD,
    "exoscale": EnvVars.EXOSCALE_API_SECRET,
    "scaleway": EnvVars.SCALEWAY_SECRET_KEY,
    "ovh": EnvVars.OVH_APPLICATION_SECRET,
    "equinixmetal": EnvVars.EQUINIXMETAL_API_KEY,
}


def _resolve_api_key(provider: str, api_key: str) -> str:
    if api_key:
        return api_key

    env_var = _PROVIDER_ENV_MAP.get(provider)
    if env_var:
        value = get_env(env_var)
        if value:
            return value

    print_json_error(
        code="missing_credentials",
        message="No API key provided and none found in .env",
    )
    raise SystemExit(1)


def _poll_health(leader_ip: str, timeout: int = 120, interval: int = 5) -> str:
    """Poll the leader's health endpoint until it responds or timeout.

    Returns "ready" if health check passes, "provisioned" otherwise.
    """
    import time

    import requests

    elapsed = 0
    health_url = f"http://{leader_ip}:80/health"

    while elapsed < timeout:
        time.sleep(interval)
        elapsed += interval
        try:
            resp = requests.get(health_url, timeout=5)
            if resp.status_code == 200:
                return "ready"
        except Exception:
            pass  # Connection refused, timeout, DNS not resolved yet — keep polling

    return "provisioned"


def run_init_json(
    provider: str,
    region: str,
    workers: int,
    leader_size: str,
    worker_size: str,
    cluster_name: str,
    api_key: str,
    daemon_config: str = "",
    demo: bool = False,
) -> None:
    if demo:
        result = build_demo_init_json(
            cluster_name=cluster_name,
            provider=provider,
            region=region,
            workers=workers,
            leader_size=leader_size,
        )
        brief = to_brief_shape(result)
        print_json_success(brief)
        return

    require_json_mode_args(
        provider=provider,
        region=region,
        leader_size=leader_size,
        cluster_name=cluster_name,
        api_key=api_key,
    )

    resolved_key = _resolve_api_key(provider, api_key)

    tier: str = "lite" if workers == 0 else "standard"

    tailscale_key: str = ""
    if tier != "lite":
        try:
            from mesh.infrastructure.configure_tailscale.configure import (
                create_auth_key,
            )

            key_resource = create_auth_key(
                key_name=f"{cluster_name}-leader",
                ephemeral=True,
                reusable=True,
                tags=["tag:mesh"],
            )
            tailscale_key = getattr(key_resource, "key", "") or ""
        except Exception as exc:
            print_json_error(
                code="provision_failed",
                message=f"Tailscale key generation failed: {exc}",
                phase="tailscale_auth",
            )
            return

    try:
        leader_boot_script = generate_cloud_init_yaml(
            tailscale_key=tailscale_key,
            leader_ip="",
            role="server",
            cluster_tier=tier,
            daemon_config=daemon_config,
        )
    except Exception as exc:
        print_json_error(
            code="provision_failed",
            message=f"Leader boot script generation failed: {exc}",
            phase="boot_script_leader",
        )
        return

    try:
        worker_boot_script = generate_cloud_init_yaml(
            tailscale_key=tailscale_key,
            leader_ip="",
            role="client",
            cluster_tier=tier,
            daemon_config=daemon_config,
        )
    except Exception as exc:
        print_json_error(
            code="provision_failed",
            message=f"Worker boot script generation failed: {exc}",
            phase="boot_script_worker",
        )
        return

    try:
        cluster_result = provision_cluster_direct(
            name=cluster_name,
            provider=provider,
            region=region,
            leader_size=leader_size,
            worker_size=worker_size,
            workers=workers,
            api_key=resolved_key,
            leader_boot_script=leader_boot_script,
            worker_boot_script=worker_boot_script,
        )
    except Exception as exc:
        print_json_error(
            code="provision_failed",
            message=str(exc),
            phase="create_vm",
            partial_resources=[],
        )
        return

    leader: Dict[str, Any] = cluster_result["leader"]
    worker_nodes: list[Dict[str, Any]] = cluster_result.get("workers", [])

    # Health check: poll leader's health endpoint
    leader_ip = (
        leader.get("public_ip")
        or leader.get("private_ip")
        or ""
    )
    if leader_ip:
        health_status = _poll_health(leader_ip)
    else:
        health_status = "provisioned"

    result = {
        "cluster_id": cluster_name,
        "provider": provider,
        "region": region,
        "tier": tier,
        "status": health_status,
        "leader": {
            "ip": leader.get("public_ip") or leader.get("private_ip") or "",
            "id": leader.get("instance_id", ""),
            "size": leader_size,
        },
        "workers": [
            {
                "ip": w.get("public_ip") or w.get("private_ip") or "",
                "id": w.get("instance_id", ""),
                "size": worker_size,
            }
            for w in worker_nodes
        ],
        "nomad_addr": "http://127.0.0.1:4646",
        "caddy_admin": "http://127.0.0.1:2019",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    brief = to_brief_shape(result, status=health_status)
    print_json_success(brief)


# ---------------------------------------------------------------------------
# Stdin command handlers (dispatched by run_init_json_from_stdin)
# ---------------------------------------------------------------------------


def _handle_init_stdin(params: dict) -> None:
    """Handle 'init' command from stdin."""
    run_init_json(
        provider=params.get("provider", ""),
        region=params.get("region", ""),
        workers=params.get("workers", 0),
        leader_size=params.get("leader_size", "s-2vcpu-4gb"),
        worker_size=params.get("worker_size", "s-1vcpu-1gb"),
        cluster_name=params.get("cluster_name", "mesh-cluster"),
        api_key=params.get("api_key", ""),
        daemon_config=params.get("daemon_config", ""),
    )


def _handle_destroy_stdin(params: dict) -> None:
    """Handle 'destroy' command from stdin."""
    require_json_mode_args(
        cluster_name=params.get("cluster_name"),
    )
    _run_destroy_json(
        cluster_name=params.get("cluster_name", ""),
        api_key=params.get("api_key", ""),
        demo=False,
        provider=params.get("provider", "digitalocean"),
        region=params.get("region", ""),
        cleanup_all=params.get("cleanup_all", False),
    )


def _handle_add_worker_stdin(params: dict) -> None:
    """Handle 'add-worker' command from stdin."""
    require_json_mode_args(
        provider=params.get("provider"),
        region=params.get("region"),
        cluster_name=params.get("cluster_name"),
        size=params.get("worker_size"),
        leader_ip=params.get("leader_ip"),
    )
    _run_add_worker_json(
        cluster_name=params.get("cluster_name", ""),
        provider=params.get("provider", ""),
        region=params.get("region", ""),
        size=params.get("worker_size", ""),
        api_key=params.get("api_key", ""),
        leader_ip=params.get("leader_ip", ""),
        demo=False,
    )


def _handle_status_stdin(params: dict) -> None:
    provider = params.get("provider", "")
    cluster_name = params.get("cluster_name", "")
    api_key = params.get("api_key", "")

    if not cluster_name:
        print_json_error(
            code="missing_parameter",
            message="cluster_name is required for status command",
        )
        return

    if provider not in PROVIDER_ENUMS or provider in UNSUPPORTED_PROVIDERS:
        available = sorted(
            p for p in PROVIDER_ENUMS if p not in UNSUPPORTED_PROVIDERS
        )
        print_json_error(
            code="unknown_provider",
            message=f"Unknown or unsupported provider '{provider}'. Available: {', '.join(available)}",
            available_providers=available,
        )
        return

    resolved_key = _resolve_api_key(provider, api_key)

    try:
        result = query_cluster_status(
            provider=provider,
            api_key=resolved_key,
            cluster_name=cluster_name,
            region=params.get("region", ""),
        )
        brief = {
            "cluster_name": result["cluster_name"],
            "exists": result["exists"],
            "node_count": len(result.get("nodes", [])),
            "nodes": result.get("nodes", []),
        }
        print_json_success(brief)
    except Exception as exc:
        print_json_error(
            code="status_failed",
            message=str(exc),
            phase="query_status",
        )


COMMAND_HANDLERS = {
    "init": _handle_init_stdin,
    "destroy": _handle_destroy_stdin,
    "add-worker": _handle_add_worker_stdin,
    "status": _handle_status_stdin,
}


def run_init_json_from_stdin() -> None:
    import sys
    import json

    raw = sys.stdin.read()
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        print(
            json.dumps({"version": "1", "status": "error", "error": {"code": "invalid_json", "message": f"Invalid JSON: {e}"}}),
            file=sys.stderr,
        )
        sys.exit(1)

    if not isinstance(msg, dict) or msg.get("version") != "1":
        print(
            json.dumps({"version": "1", "status": "error", "error": {"code": "unsupported_version", "message": "Expected version: 1"}}),
            file=sys.stderr,
        )
        sys.exit(1)

    command = msg.get("command")
    params = msg.get("params", {})

    handler = COMMAND_HANDLERS.get(command)
    if handler is None:
        print(
            json.dumps({"version": "1", "status": "error", "error": {"code": "unknown_command", "message": f"Unknown command: {command}"}}),
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        handler(params)
    except SystemExit:
        raise
    except Exception as e:
        print_json_error(code="provision_failed", message=str(e))
