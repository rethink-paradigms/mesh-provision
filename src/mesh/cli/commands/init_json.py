from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from mesh.cli.commands.json_output import (
    build_demo_init_json,
    print_json_error,
    print_json_success,
    require_json_mode_args,
    to_brief_shape,
)
from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import (
    generate_shell_script,
)
from mesh.infrastructure.config.env import EnvVars, get_env
from mesh.infrastructure.provision_node.provision_direct import (
    provision_cluster_direct,
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
    daemon_token: str,
    daemon_url: str,
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
        leader_boot_script = generate_shell_script(
            tailscale_key=tailscale_key,
            leader_ip="",
            role="server",
            cluster_tier=tier,
            daemon_token=daemon_token,
            daemon_url=daemon_url,
            cluster_id=cluster_name,
        )
    except Exception as exc:
        print_json_error(
            code="provision_failed",
            message=f"Leader boot script generation failed: {exc}",
            phase="boot_script_leader",
        )
        return

    try:
        worker_boot_script = generate_shell_script(
            tailscale_key=tailscale_key,
            leader_ip="",
            role="client",
            cluster_tier=tier,
            daemon_token=daemon_token,
            daemon_url=daemon_url,
            cluster_id=cluster_name,
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
        "daemon_url": daemon_url or f"https://daemon-{cluster_name}.agentbodies.com",
        "daemon_token": daemon_token,
        "caddy_admin": "http://127.0.0.1:2019",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    brief = to_brief_shape(result, status=health_status)
    print_json_success(brief)
