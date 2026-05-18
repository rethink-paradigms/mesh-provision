"""
Direct VM provisioning via Apache Libcloud.

This is the core engine. No Pulumi, no state files, no plan/apply.
One function call → one cloud API call → one VM.

Public API:
    provision_node(...)          → create one VM, return {name, public_ip, instance_id, ...}
    provision_cluster(...)       → create leader + N workers
    destroy_cluster(...)         → destroy all VMs with cluster name prefix
    query_cluster(...)           → list VMs with cluster name prefix
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from mesh.providers import get_driver as _providers_get_driver, is_provider_usable


def _get_driver(provider: str, api_key: str, region: str):
    """Module-level driver factory (patchable in tests)."""
    return _providers_get_driver(provider, api_key=api_key, region=region)
from mesh.providers.discovery import get_region, get_size, find_ubuntu_image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single node
# ---------------------------------------------------------------------------


def provision_node(
    name: str,
    provider: str,
    region: str,
    size_id: str,
    api_key: str,
    boot_script: str,
    image_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create one cloud VM and return its details.

    Args:
        name:        VM hostname / resource name.
        provider:    Provider ID (e.g. "digitalocean", "aws").
        region:      Region slug (e.g. "nyc3", "us-east-1").
        size_id:     Exact size slug (e.g. "s-2vcpu-4gb", "t3.small").
        api_key:     API token. For AWS: "ACCESS_KEY_ID:SECRET".
        boot_script: Full cloud-init YAML string injected as userdata.
        image_id:    Optional explicit image ID. Auto-discovers Ubuntu 22.04 if omitted.

    Returns:
        {name, public_ip, private_ip, instance_id, size_id}

    Raises:
        ValueError:   Unknown provider, invalid region/size/image, missing creds.
        RuntimeError: Cloud API rejected the create request.
    """
    if not is_provider_usable(provider):
        raise ValueError(f"Provider {provider!r} is not usable.")

    driver = _get_driver(provider, api_key=api_key, region=region)

    location = get_region(provider, region, api_key=api_key, region=region)
    if location is None:
        raise ValueError(f"Region {region!r} not found for provider {provider!r}.")

    size = get_size(provider, size_id, api_key=api_key, region=region)
    if size is None:
        raise ValueError(f"Size {size_id!r} not found for provider {provider!r}.")

    if image_id:
        from libcloud.compute.base import NodeImage
        image = NodeImage(id=image_id, name=image_id, driver=driver)
    else:
        image = find_ubuntu_image(provider, api_key=api_key, region=region)
        if image is None:
            raise ValueError(
                f"Could not find Ubuntu 22.04 image for provider {provider!r}. "
                f"Specify image_id explicitly."
            )

    # DigitalOcean: inject account SSH keys so operator can SSH in if needed
    create_kwargs: dict[str, Any] = {
        "name": name,
        "size": size,
        "image": image,
        "location": location,
        "ex_user_data": boot_script,
    }
    if provider in ("digitalocean", "do"):
        ex_create_attr: dict[str, Any] = {}
        if tags:
            ex_create_attr["tags"] = tags
        ssh_keys = _do_list_ssh_key_ids(api_key)
        if ssh_keys:
            ex_create_attr["ssh_keys"] = ssh_keys
        if ex_create_attr:
            create_kwargs["ex_create_attr"] = ex_create_attr

    try:
        node = driver.create_node(**create_kwargs)
    except Exception as exc:
        raise RuntimeError(f"Failed to create VM {name!r} on {provider}: {exc}") from exc

    public_ip = node.public_ips[0] if node.public_ips else None
    private_ip = node.private_ips[0] if node.private_ips else None

    if public_ip is None:
        public_ip, private_ip = _poll_for_ip(driver, node.id)

    logger.info("Provisioned %s → public_ip=%s instance_id=%s", name, public_ip, node.id)

    return {
        "name": name,
        "public_ip": public_ip,
        "private_ip": private_ip,
        "instance_id": node.id,
        "size_id": size_id,
    }


# ---------------------------------------------------------------------------
# Cluster (leader + workers)
# ---------------------------------------------------------------------------


def provision_cluster(
    name: str,
    provider: str,
    region: str,
    leader_size: str,
    worker_size: str,
    workers: int,
    api_key: str,
    leader_boot_script: str,
    worker_boot_script_fn,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a cluster: one leader and N workers.

    Args:
        name:                  Cluster name prefix (VMs named {name}-leader, {name}-worker-N).
        worker_boot_script_fn: Callable(leader_ip: str) → str.
                               Called AFTER the leader is up so it can embed the leader IP.
                               For solo tier (workers=0) this is never called.

    Returns:
        {cluster_name, provider, region, leader: {...}, workers: [{...}]}
    """
    leader = provision_node(
        name=f"{name}-leader",
        provider=provider,
        region=region,
        size_id=leader_size,
        api_key=api_key,
        boot_script=leader_boot_script,
        tags=tags,
    )

    leader_ip = leader.get("public_ip") or leader.get("private_ip") or ""

    worker_nodes: list[dict[str, Any]] = []
    for i in range(workers):
        # Generate the worker boot script now that we have the leader IP
        worker_script = worker_boot_script_fn(leader_ip)
        worker = provision_node(
            name=f"{name}-worker-{i}",
            provider=provider,
            region=region,
            size_id=worker_size,
            api_key=api_key,
            boot_script=worker_script,
            tags=tags,
        )
        worker_nodes.append(worker)

    return {
        "cluster_name": name,
        "provider": provider,
        "region": region,
        "leader": leader,
        "workers": worker_nodes,
    }


# ---------------------------------------------------------------------------
# Destroy
# ---------------------------------------------------------------------------


def destroy_cluster(
    provider: str,
    api_key: str,
    region: str,
    cluster_name: str,
    cleanup_all: bool = False,
) -> dict[str, Any]:
    """Destroy all VMs whose names start with cluster_name + '-'.

    When cleanup_all=True also removes auxiliary DigitalOcean resources
    (volumes, firewalls, floating IPs, SSH keys) that are TAGGED with the
    cluster name. Never removes resources that don't match the cluster.

    Returns:
        {cluster_name, destroyed: True, resources_cleaned: [str]}
    """
    if cleanup_all and provider not in ("digitalocean", "do"):
        raise NotImplementedError(
            f"cleanup_all is only supported for DigitalOcean, not {provider!r}."
        )

    driver = _get_driver(provider, api_key=api_key, region=region)
    prefix = f"{cluster_name}-"
    cleaned: list[str] = []

    # Phase 1: auxiliary DO resources — filtered by cluster name prefix
    if cleanup_all:
        cleaned += _do_cleanup_aux(driver, prefix)

    # Phase 2: compute nodes — filtered by name prefix
    try:
        all_nodes = driver.list_nodes()
    except Exception as exc:
        raise RuntimeError(f"Failed to list nodes on {provider}: {exc}") from exc

    for node in all_nodes:
        if node.name and node.name.startswith(prefix):
            try:
                driver.destroy_node(node)
                if node.id:
                    cleaned.append(node.id)
                logger.info("Destroyed node %s (id=%s)", node.name, node.id)
            except Exception as exc:
                logger.warning("Failed to destroy node %s: %s", node.name, exc)

    return {
        "cluster_name": cluster_name,
        "destroyed": True,
        "resources_cleaned": cleaned,
    }


# ---------------------------------------------------------------------------
# Remove single worker
# ---------------------------------------------------------------------------


def remove_worker(
    provider: str,
    api_key: str,
    region: str,
    cluster_name: str,
    node_id: str = "",
    node_name: str = "",
) -> dict[str, Any]:
    """Destroy a single worker node by node_id or node_name.

    Either node_id or node_name must be provided. If both are given,
    node_id takes precedence.

    The node must belong to the cluster (its name must start with
    '{cluster_name}-worker-') — safety guard against removing the leader
    or nodes from a different cluster.

    Returns:
        {node_id, node_name, removed: True}

    Raises:
        ValueError:   Node not found, or node is the leader, or doesn't belong to cluster.
        RuntimeError: Cloud API call failed.
    """
    if not node_id and not node_name:
        raise ValueError("Either node_id or node_name must be provided.")

    driver = _get_driver(provider, api_key=api_key, region=region)
    prefix = f"{cluster_name}-worker-"

    try:
        all_nodes = driver.list_nodes()
    except Exception as exc:
        raise RuntimeError(f"Failed to list nodes on {provider}: {exc}") from exc

    target = None
    for node in all_nodes:
        if node_id and node.id == node_id:
            target = node
            break
        if node_name and node.name == node_name:
            target = node
            break

    if target is None:
        identifier = node_id or node_name
        raise ValueError(f"Node {identifier!r} not found on {provider}.")

    # Safety: refuse to remove the leader or anything outside this cluster
    if not (target.name and target.name.startswith(prefix)):
        raise ValueError(
            f"Node {target.name!r} is not a worker of cluster {cluster_name!r}. "
            f"Expected name starting with {prefix!r}. Refusing to remove."
        )

    try:
        driver.destroy_node(target)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to destroy node {target.name!r} (id={target.id}): {exc}"
        ) from exc

    logger.info("Removed worker %s (id=%s) from cluster %s", target.name, target.id, cluster_name)
    return {
        "node_id": target.id or node_id,
        "node_name": target.name or node_name,
        "removed": True,
    }


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def query_cluster(
    provider: str,
    api_key: str,
    cluster_name: str,
    region: str = "",
) -> dict[str, Any]:
    """Return cluster existence and node list by matching name prefix.

    Returns:
        {cluster_name, exists: bool, nodes: [{id, ip, role}]}
    """
    driver = _get_driver(provider, api_key=api_key, region=region)
    prefix = f"{cluster_name}-"

    try:
        all_nodes = driver.list_nodes()
    except Exception as exc:
        raise RuntimeError(f"Failed to list nodes on {provider}: {exc}") from exc

    nodes = []
    for node in all_nodes:
        if not (node.name and node.name.startswith(prefix)):
            continue
        if node.name.endswith("-leader"):
            role = "leader"
        elif "-worker-" in node.name:
            role = "worker"
        else:
            role = "unknown"

        ip = ""
        if node.public_ips:
            ip = node.public_ips[0]
        elif node.private_ips:
            ip = node.private_ips[0]

        nodes.append({"id": node.id or "", "ip": ip, "role": role})

    return {
        "cluster_name": cluster_name,
        "exists": len(nodes) > 0,
        "nodes": nodes,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def poll_daemon_health(
    leader_ip: str,
    port: int = 8080,
    timeout: int = 300,
    interval: int = 5,
) -> bool:
    """Poll http://{leader_ip}:{port}/healthz every `interval` seconds.

    Returns True on first HTTP 200 response.
    Returns False if `timeout` seconds elapse with no 200.
    Uses urllib.request — no extra dependencies.
    Swallows all per-attempt exceptions (connection refused, timeout, etc.).

    Note: Default timeout of 300s (5 min) accommodates 3-5 min VM boot + daemon
    startup via cloud-init before /healthz responds.
    """
    import urllib.request as _urllib_req
    import urllib.error as _urllib_err

    url = f"http://{leader_ip}:{port}/healthz"
    elapsed = 0
    while elapsed < timeout:
        time.sleep(interval)
        elapsed += interval
        logger.debug("poll_daemon_health: attempt %s/%s %s", elapsed, timeout, url)
        try:
            with _urllib_req.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    logger.info("poll_daemon_health: daemon ready at %s (elapsed=%ss)", url, elapsed)
                    return True
        except Exception:
            pass
    logger.info("poll_daemon_health: timed out after %ss waiting for %s", timeout, url)
    return False


def _poll_for_ip(
    driver, node_id: str, timeout: int = 120, interval: int = 5
) -> tuple[Optional[str], Optional[str]]:
    """Poll until a node has a public IP or timeout expires."""
    elapsed = 0
    while elapsed < timeout:
        time.sleep(interval)
        elapsed += interval
        try:
            node = driver.ex_get_node_details(node_id)
        except Exception:
            node = None
            try:
                for n in driver.list_nodes():
                    if n.id == node_id:
                        node = n
                        break
            except Exception:
                break

        if node is None:
            break
        if node.public_ips:
            return node.public_ips[0], (node.private_ips[0] if node.private_ips else None)

    return None, None


def _do_list_ssh_key_ids(api_key: str) -> list[int]:
    """Fetch SSH key IDs from the DigitalOcean account (for injection at VM creation)."""
    import json as _json
    import urllib.request as _req

    try:
        request = _req.Request(
            "https://api.digitalocean.com/v2/account/keys",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with _req.urlopen(request, timeout=10) as resp:
            body = _json.loads(resp.read().decode())
            return [k["id"] for k in body.get("ssh_keys", []) if k.get("id")]
    except Exception as exc:
        logger.warning("Could not fetch DO SSH keys (non-fatal): %s", exc)
        return []


def _do_cleanup_aux(driver, prefix: str) -> list[str]:
    """Destroy DigitalOcean auxiliary resources whose names start with prefix.

    Only removes resources matching the cluster prefix — never touches
    unrelated resources.
    """
    cleaned: list[str] = []

    # Volumes
    if hasattr(driver, "ex_list_volumes"):
        try:
            for vol in driver.ex_list_volumes():
                vol_name = getattr(vol, "name", "") or ""
                if vol_name.startswith(prefix):
                    try:
                        driver.ex_destroy_volume(vol)
                        cleaned.append(f"volume:{vol.id}")
                    except Exception as exc:
                        logger.warning("Failed to destroy volume %s: %s", vol.id, exc)
        except Exception as exc:
            logger.warning("Failed to list volumes: %s", exc)

    # Firewalls
    if hasattr(driver, "ex_list_firewalls"):
        try:
            for fw in driver.ex_list_firewalls():
                fw_name = getattr(fw, "name", "") or ""
                if fw_name.startswith(prefix):
                    try:
                        driver.ex_delete_firewall(fw)
                        cleaned.append(f"firewall:{fw.id}")
                    except Exception as exc:
                        logger.warning("Failed to delete firewall %s: %s", fw.id, exc)
        except Exception as exc:
            logger.warning("Failed to list firewalls: %s", exc)

    # Floating IPs — DO floating IPs don't have names, skip
    # (they're attached to droplets which are destroyed in phase 2)

    # SSH keys
    if hasattr(driver, "ex_list_ssh_keys"):
        try:
            for key in driver.ex_list_ssh_keys():
                key_name = getattr(key, "name", "") or ""
                if key_name.startswith(prefix):
                    try:
                        driver.ex_delete_ssh_key(key)
                        cleaned.append(f"ssh_key:{key.id}")
                    except Exception as exc:
                        logger.warning("Failed to delete SSH key %s: %s", key.id, exc)
        except Exception as exc:
            logger.warning("Failed to list SSH keys: %s", exc)

    return cleaned
