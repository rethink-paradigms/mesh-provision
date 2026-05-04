"""
Direct Libcloud VM Provisioning (No Pulumi)

This module provides direct VM provisioning via Apache Libcloud API calls,
bypassing Pulumi entirely. It is used by the JSON-mode CLI and other
non-Pulumi consumers that need to create/destroy cloud VMs imperatively.

Key Features:
- Direct Libcloud driver usage (no Pulumi imports)
- IP polling with timeout
- Cluster provisioning (leader + workers)
- Resource cleanup by cluster name prefix

Usage:
    from mesh.infrastructure.provision_node.provision_direct import (
        provision_node_direct,
        provision_cluster_direct,
        destroy_resources_direct,
    )

    # Provision a single node
    node = provision_node_direct(
        name="my-node",
        provider="digitalocean",
        region="nyc3",
        size_id="s-2vcpu-4gb",
        api_key="dop_v1_...",
        boot_script="#cloud-init...",
    )

    # Provision a cluster
    cluster = provision_cluster_direct(
        name="prod",
        provider="digitalocean",
        region="nyc3",
        leader_size="s-2vcpu-4gb",
        worker_size="s-1vcpu-1gb",
        workers=2,
        api_key="dop_v1_...",
        leader_boot_script="#cloud-init...",
        worker_boot_script="#cloud-init...",
    )

    # Destroy all resources for a cluster
    result = destroy_resources_direct(
        provider="digitalocean",
        api_key="dop_v1_...",
        region="nyc3",
        cluster_name="prod",
    )
"""

import time
import logging
from typing import Dict, Any, Optional, List

from mesh.infrastructure.providers import get_driver, is_provider_supported
from mesh.infrastructure.providers.discovery import (
    get_size,
    get_region,
    find_ubuntu_image,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_driver_direct(provider: str, api_key: str, region: str):
    """Get a Libcloud driver using the provided API key.

    Args:
        provider: Provider identifier (e.g., "digitalocean", "aws")
        api_key: API key / token for the provider
        region: Target region

    Returns:
        Initialized Libcloud NodeDriver instance
    """
    if not is_provider_supported(provider):
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Supported: {', '.join(sorted(list_providers()))}"
        )

    # Build credentials dict — for token-based providers the key is "key"
    credentials = {"key": api_key}
    if provider == "aws":
        credentials["region"] = region

    return get_driver(provider, credentials=credentials, region=region)


def _poll_for_ip(driver, node_id: str, timeout: int = 120, interval: int = 5) -> tuple:
    """Poll a node until it has a public IP (or timeout).

    Args:
        driver: Libcloud NodeDriver instance
        node_id: The node's provider ID
        timeout: Maximum seconds to wait
        interval: Seconds between polls

    Returns:
        Tuple of (public_ip, private_ip) — either may be None
    """
    elapsed = 0
    public_ip = None
    private_ip = None

    while elapsed < timeout:
        time.sleep(interval)
        elapsed += interval

        try:
            refreshed = driver.ex_get_node_details(node_id)
        except Exception:
            # Fallback: list all nodes and match by ID
            refreshed = None
            try:
                for n in driver.list_nodes():
                    if n.id == node_id:
                        refreshed = n
                        break
            except Exception:
                break

        if refreshed is None:
            break

        if refreshed.public_ips:
            public_ip = refreshed.public_ips[0]
        if refreshed.private_ips:
            private_ip = refreshed.private_ips[0]

        if public_ip:
            logger.info("Node %s got public IP %s after %ds", node_id, public_ip, elapsed)
            break

    return public_ip, private_ip


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def provision_node_direct(
    name: str,
    provider: str,
    region: str,
    size_id: str,
    api_key: str,
    boot_script: str,
    image_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Provision a single cloud node via direct Libcloud API calls.

    This function does NOT use Pulumi — it calls Libcloud drivers directly.

    Args:
        name: Node name (used as the hostname / resource name)
        provider: Provider identifier (e.g., "digitalocean", "aws")
        region: Target region (e.g., "nyc3", "us-east-1")
        size_id: Exact provider size ID (e.g., "s-2vcpu-4gb", "t3.medium")
        api_key: API token / key for the provider
        boot_script: Cloud-init / userdata script (plain text)
        image_id: Optional explicit image ID. If omitted, auto-discovers
                  Ubuntu 22.04.

    Returns:
        Dictionary with keys:
            - name (str)
            - public_ip (str | None)
            - private_ip (str | None)
            - instance_id (str)
            - size_id (str)

    Raises:
        ValueError: If provider is unsupported, size/region invalid, or
                    credentials missing.
        RuntimeError: If Libcloud create_node fails.
    """
    # Validate provider
    if not is_provider_supported(provider):
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Supported: {', '.join(sorted(list_providers()))}"
        )

    # Resolve region
    location = get_region(provider, region)
    if location is None:
        raise ValueError(
            f"Invalid region '{region}' for provider '{provider}'."
        )

    # Resolve size
    size = get_size(provider, size_id, region=region)
    if size is None:
        raise ValueError(
            f"Invalid size_id '{size_id}' for provider '{provider}'."
        )

    # Resolve image
    if image_id:
        from mesh.infrastructure.providers.discovery import get_image

        image = get_image(provider, image_id)
        if image is None:
            raise ValueError(
                f"Invalid image_id '{image_id}' for provider '{provider}'."
            )
    else:
        image = find_ubuntu_image(provider, version="22.04")
        if image is None:
            raise ValueError(
                f"Could not auto-discover Ubuntu 22.04 image for provider '{provider}'."
            )

    # Get driver
    driver = _get_driver_direct(provider, api_key, region)

    # Create node
    try:
        node = driver.create_node(
            name=name,
            size=size,
            image=image,
            location=location,
            ex_user_data=boot_script,  # type: ignore[call-arg]
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to create node '{name}' on {provider}: {exc}"
        ) from exc

    # Extract initial IPs (some providers assign synchronously)
    public_ip = node.public_ips[0] if node.public_ips else None
    private_ip = node.private_ips[0] if node.private_ips else None

    # Poll for public IP if not immediately available
    if public_ip is None:
        public_ip, private_ip = _poll_for_ip(driver, node.id)

    return {
        "name": name,
        "public_ip": public_ip,
        "private_ip": private_ip,
        "instance_id": node.id,
        "size_id": size_id,
    }


def provision_cluster_direct(
    name: str,
    provider: str,
    region: str,
    leader_size: str,
    worker_size: str,
    workers: int,
    api_key: str,
    leader_boot_script: str,
    worker_boot_script: str,
) -> Dict[str, Any]:
    """Provision a cluster: one leader node + N worker nodes.

    The worker boot script is passed verbatim; the caller is responsible for
    embedding the leader's public IP inside the script if workers need it.

    Args:
        name: Cluster name prefix (e.g., "prod" → "prod-leader", "prod-worker-0")
        provider: Provider identifier
        region: Target region
        leader_size: Size ID for the leader node
        worker_size: Size ID for each worker node
        workers: Number of worker nodes (may be 0)
        api_key: API token / key
        leader_boot_script: Cloud-init script for the leader
        worker_boot_script: Cloud-init script for workers

    Returns:
        Dictionary with keys:
            - cluster_name (str)
            - provider (str)
            - region (str)
            - leader (dict): output of provision_node_direct
            - workers (list[dict]): outputs of provision_node_direct
    """
    leader_name = f"{name}-leader"
    leader = provision_node_direct(
        name=leader_name,
        provider=provider,
        region=region,
        size_id=leader_size,
        api_key=api_key,
        boot_script=leader_boot_script,
    )

    worker_nodes: List[Dict[str, Any]] = []
    for i in range(workers):
        worker_name = f"{name}-worker-{i}"
        worker = provision_node_direct(
            name=worker_name,
            provider=provider,
            region=region,
            size_id=worker_size,
            api_key=api_key,
            boot_script=worker_boot_script,
        )
        worker_nodes.append(worker)

    return {
        "cluster_name": name,
        "provider": provider,
        "region": region,
        "leader": leader,
        "workers": worker_nodes,
    }


def destroy_resources_direct(
    provider: str,
    api_key: str,
    region: str,
    cluster_name: str,
) -> Dict[str, Any]:
    """Destroy all nodes whose names start with the cluster name prefix.

    Args:
        provider: Provider identifier
        api_key: API token / key
        region: Target region
        cluster_name: Cluster name prefix to match against node names

    Returns:
        Dictionary with keys:
            - cluster_name (str)
            - destroyed (bool)
            - resources_cleaned (list[str]): instance IDs that were destroyed
    """
    driver = _get_driver_direct(provider, api_key, region)

    try:
        all_nodes = driver.list_nodes()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to list nodes on {provider}: {exc}"
        ) from exc

    cleaned: List[str] = []
    prefix = f"{cluster_name}-"

    for node in all_nodes:
        if node.name and node.name.startswith(prefix):
            try:
                driver.destroy_node(node)
                if node.id:
                    cleaned.append(node.id)
                logger.info("Destroyed node %s (id=%s)", node.name, node.id)
            except Exception as exc:
                logger.warning(
                    "Failed to destroy node %s (id=%s): %s",
                    node.name,
                    node.id,
                    exc,
                )

    return {
        "cluster_name": cluster_name,
        "destroyed": True,
        "resources_cleaned": cleaned,
    }


# Re-export list_providers for convenience
from mesh.infrastructure.providers import list_providers  # noqa: E402,F401
