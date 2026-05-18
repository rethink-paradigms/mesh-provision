"""
add-worker command — provision and attach a new worker node to an existing cluster.

Contract §3d:
  Required params: provider, region, cluster_name, worker_size, leader_ip, api_key
  Optional params: tailscale_key
  Success output:  {node: {ip, id, role}}
"""

from __future__ import annotations

from typing import Any

from mesh.commands.output import (
    print_json_error,
    print_json_success,
    require_args,
    add_worker_success,
    demo_add_worker,
)
from mesh.providers import is_provider_usable, USABLE_PROVIDERS
from mesh.provisioning.boot import generate_cloud_init
from mesh.provisioning.direct import provision_node


def handle_add_worker(params: dict[str, Any]) -> None:
    """Entry point called by entrypoint.py for the 'add-worker' command."""

    if params.get("demo"):
        print_json_success(demo_add_worker())
        return

    require_args(
        "add-worker", params,
        "provider", "region", "cluster_name", "worker_size", "leader_ip", "api_key",
    )

    provider     = params["provider"].lower()
    region       = params["region"]
    cluster_name = params["cluster_name"]
    worker_size  = params["worker_size"]
    leader_ip    = params["leader_ip"]
    api_key      = params["api_key"]
    tailscale_key = params.get("tailscale_key", "")

    # Workers always join a cluster — tier is cluster by definition
    cluster_tier = "cluster"

    if not is_provider_usable(provider):
        print_json_error(
            code="unknown_provider",
            message=f"Provider {provider!r} is not supported. "
                    f"Available: {', '.join(sorted(USABLE_PROVIDERS))}",
            available_providers=sorted(USABLE_PROVIDERS),
        )

    # Build worker boot script with leader IP injected
    try:
        boot_script = generate_cloud_init(
            role="client",
            cluster_tier=cluster_tier,
            tailscale_key=tailscale_key,
            leader_ip=leader_ip,
            daemon_config=None,   # workers never run the daemon
        )
    except Exception as exc:
        print_json_error(
            code="provision_failed",
            message=f"Worker boot script generation failed: {exc}",
            phase="boot_script_worker",
        )

    # Use a timestamp-based suffix so multiple add-worker calls don't collide
    import time
    worker_name = f"{cluster_name}-worker-{int(time.time())}"

    try:
        node = provision_node(
            name=worker_name,
            provider=provider,
            region=region,
            size_id=worker_size,
            api_key=api_key,
            boot_script=boot_script,
        )
    except Exception as exc:
        print_json_error(
            code="provision_failed",
            message=str(exc),
            phase="create_worker_vm",
        )

    print_json_success(
        add_worker_success(
            node_ip=node.get("public_ip") or node.get("private_ip") or "",
            node_id=node.get("instance_id", ""),
        )
    )
