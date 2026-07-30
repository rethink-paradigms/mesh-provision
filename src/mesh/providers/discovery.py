"""
Cloud provider resource discovery — sizes, regions, images.

All functions make live API calls and cache results for the duration of
the process (one provisioning invocation). The cache is a simple module-level
dict keyed by (provider_id, resource_type).

Usage:
    from mesh.providers.discovery import get_size, get_region, find_ubuntu_image

    location = get_region("digitalocean", "nyc3", api_key="dop_v1_...")
    size     = get_size("digitalocean", "s-2vcpu-4gb", api_key="dop_v1_...")
    image    = find_ubuntu_image("digitalocean", api_key="dop_v1_...")
"""

from __future__ import annotations

import re
from typing import Optional

from libcloud.compute.base import NodeSize, NodeImage, NodeLocation

from mesh.providers import get_driver


# ---------------------------------------------------------------------------
# Session-level cache  {(provider_id, resource_type) → list}
# ---------------------------------------------------------------------------
_CACHE: dict[tuple[str, str], list] = {}


def _cached(provider_id: str, resource_type: str, api_key: str, region: str, loader):
    key = (provider_id, resource_type)
    if key not in _CACHE:
        driver = get_driver(provider_id, api_key=api_key, region=region)
        _CACHE[key] = loader(driver)
    return _CACHE[key]


def clear_cache() -> None:
    """Clear the session cache (useful between test cases)."""
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------


def list_regions(provider_id: str, api_key: str = "", region: str = "") -> list[NodeLocation]:
    return _cached(provider_id, "regions", api_key, region, lambda d: d.list_locations())


def get_region(
    provider_id: str, region_id: str, api_key: str = "", region: str = ""
) -> Optional[NodeLocation]:
    """Return the NodeLocation for region_id, or None if not found."""
    for loc in list_regions(provider_id, api_key=api_key, region=region):
        if loc.id == region_id:
            return loc
    return None


# ---------------------------------------------------------------------------
# Sizes
# ---------------------------------------------------------------------------


def list_sizes(provider_id: str, api_key: str = "", region: str = "") -> list[NodeSize]:
    return _cached(provider_id, "sizes", api_key, region, lambda d: d.list_sizes())


def get_size(
    provider_id: str, size_id: str, api_key: str = "", region: str = ""
) -> Optional[NodeSize]:
    """Return the NodeSize for size_id, or None if not found."""
    for sz in list_sizes(provider_id, api_key=api_key, region=region):
        if sz.id == size_id:
            return sz
    return None


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def find_ubuntu_image(
    provider_id: str,
    version: str = "22.04",
    api_key: str = "",
    region: str = "",
) -> Optional[NodeImage]:
    """Find an Ubuntu image for the given provider and version.

    Provider-specific strategies:
      DigitalOcean — uses slug IDs like "ubuntu-22-04-x64". Direct slug lookup,
                     no need to list all images.
      AWS          — filtered list_images with owner=amazon and name pattern.
                     Never calls list_images() unfiltered (returns ~100k results).
      Others       — name-based search over list_images().
    """
    pid = provider_id.lower()

    if pid in ("digitalocean", "do"):
        return _do_ubuntu_image(version, api_key)

    if pid == "aws":
        return _aws_ubuntu_image(version, api_key, region)

    return _generic_ubuntu_image(pid, version, api_key, region)


def _do_ubuntu_image(version: str, api_key: str) -> Optional[NodeImage]:
    """DigitalOcean images use slug IDs: ubuntu-22-04-x64."""
    slug = "ubuntu-" + version.replace(".", "-") + "-x64"
    driver = get_driver("digitalocean", api_key=api_key)
    # DO supports filtering by slug directly
    try:
        images = driver.list_images(ex_type="distribution")
        for img in images:
            if img.id == slug or img.name.lower().startswith(slug):
                return img
    except Exception:
        pass
    # Fallback: construct a minimal NodeImage from the known slug
    from libcloud.compute.base import NodeImage as _NI
    return _NI(id=slug, name=f"Ubuntu {version} x64", driver=None, extra={})


def _aws_ubuntu_image(version: str, api_key: str, region: str) -> Optional[NodeImage]:
    """AWS: use filtered list_images (Canonical owner) to avoid listing all AMIs."""
    # Ubuntu version → codename for name filter
    codenames = {"22.04": "jammy", "20.04": "focal", "18.04": "bionic"}
    codename = codenames.get(version, version.replace(".", ""))

    driver = get_driver("aws", api_key=api_key, region=region)
    try:
        images = driver.list_images(ex_filters={
            "owner-id": ["099720109477"],   # Canonical's AWS account
            "name": [f"ubuntu/images/hvm-ssd/ubuntu-{codename}-{version}-amd64-server-*"],
            "state": ["available"],
            "architecture": ["x86_64"],
        })
        if not images:
            return None
        # Sort by name descending (date is embedded in name) → latest first
        images.sort(key=lambda img: img.name or "", reverse=True)
        return images[0]
    except Exception:
        return None


def _generic_ubuntu_image(
    provider_id: str, version: str, api_key: str, region: str
) -> Optional[NodeImage]:
    """Name-based search for providers without slug/filter support."""
    codenames = {"22.04": "jammy", "20.04": "focal", "18.04": "bionic"}
    search_terms = [version, codenames.get(version, "")]

    all_images = _cached(provider_id, "images", api_key, region, lambda d: d.list_images())
    candidates = []
    for img in all_images:
        name = (img.name or "").lower()
        if "ubuntu" not in name:
            continue
        if not any(term in name for term in search_terms if term):
            continue
        if "amd64" in name or "x86_64" in name or "x64" in name:
            candidates.append(img)

    if not candidates:
        return None

    # Try to pick the most recent by date embedded in name (YYYYMMDD pattern)
    def _date_key(img):
        m = re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", img.name or "")
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 0)

    candidates.sort(key=_date_key, reverse=True)
    return candidates[0]
