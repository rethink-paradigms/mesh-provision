"""
init command — provision a cluster (leader VM + optional workers).

Contract §3a:
  Required params: provider, region, cluster_name, leader_size, api_key
  Optional params: workers (default 0), worker_size, daemon_config, tailscale_key
  Success output:  {cluster_id, leader_ip, status, nodes[]}
"""

from __future__ import annotations

import time
from typing import Any, Optional

from mesh.commands.output import (
    print_json_error,
    print_json_success,
    require_args,
    init_success,
    demo_init,
)
from mesh.providers import is_provider_usable, USABLE_PROVIDERS
from mesh.provisioning.boot import generate_cloud_init
from mesh.provisioning.direct import provision_cluster, query_cluster, poll_daemon_health


def handle_init(params: dict[str, Any]) -> None:
    """Entry point called by entrypoint.py for the 'init' command."""

    # Demo mode — return synthetic response immediately
    if params.get("demo"):
        result = demo_init(
            cluster_name=params.get("cluster_name", "demo-cluster"),
            provider=params.get("provider", "digitalocean"),
            region=params.get("region", "nyc3"),
            workers=int(params.get("workers", 0)),
            leader_size=params.get("leader_size", "s-2vcpu-4gb"),
        )
        print_json_success(result)
        return

    # Validate required params
    require_args("init", params, "provider", "region", "cluster_name", "leader_size", "api_key")

    provider     = params["provider"].lower()
    region       = params["region"]
    cluster_name = params["cluster_name"]
    leader_size  = params["leader_size"]
    api_key      = params["api_key"]
    workers      = int(params.get("workers", 0))
    worker_size  = params.get("worker_size", "s-1vcpu-1gb")
    daemon_config: Optional[str] = params.get("daemon_config") or None
    tailscale_key: str = params.get("tailscale_key", "")
    bootstrap_expect: int = int(params.get("bootstrap_expect", 1))

    # Validate provider
    if not is_provider_usable(provider):
        print_json_error(
            code="unknown_provider",
            message=f"Provider {provider!r} is not supported. "
                    f"Available: {', '.join(sorted(USABLE_PROVIDERS))}",
            available_providers=sorted(USABLE_PROVIDERS),
        )

    cluster_tier = "lite" if workers == 0 else "standard"

    # Build leader boot script
    try:
        leader_boot = generate_cloud_init(
            role="server",
            cluster_tier=cluster_tier,
            tailscale_key=tailscale_key,
            leader_ip="",          # leader doesn't need to know its own IP at boot
            daemon_config=daemon_config,
            bootstrap_expect=bootstrap_expect,
        )
    except Exception as exc:
        print_json_error(
            code="provision_failed",
            message=f"Leader boot script generation failed: {exc}",
            phase="boot_script_leader",
        )

    # Worker boot script is a factory: called after leader IP is known
    def _make_worker_boot(leader_ip: str) -> str:
        return generate_cloud_init(
            role="client",
            cluster_tier=cluster_tier,
            tailscale_key=tailscale_key,
            leader_ip=leader_ip,
            daemon_config=None,    # daemon runs on leader only
            bootstrap_expect=bootstrap_expect,
        )

    # Provision
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
        )
    except Exception as exc:
        print_json_error(
            code="provision_failed",
            message=str(exc),
            phase="create_vm",
        )

    leader = cluster["leader"]
    leader_ip = leader.get("public_ip") or leader.get("private_ip") or ""

    # Health poll
    health_status = ("ready" if poll_daemon_health(leader_ip) else "provisioned") if leader_ip else "provisioned"

    # Build nodes list
    nodes = [{"id": leader.get("instance_id", ""), "ip": leader_ip, "role": "leader"}]
    for w in cluster.get("workers", []):
        nodes.append({
            "id": w.get("instance_id", ""),
            "ip": w.get("public_ip") or w.get("private_ip") or "",
            "role": "worker",
        })

    print_json_success(
        init_success(
            cluster_name=cluster_name,
            leader_ip=leader_ip,
            status=health_status,
            nodes=nodes,
        )
    )



