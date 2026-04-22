"""Centralized environment variable registry for Mesh.

All env var lookups should go through this module.
This is the single source of truth for variable names.

Usage:
    from mesh.infrastructure.config.env import EnvVars, get_env

    token = get_env(EnvVars.DIGITALOCEAN_API_TOKEN, required=True)
    nomad_addr = get_env(EnvVars.NOMAD_ADDR, default="http://127.0.0.1:4646")
"""

import os
from pathlib import Path
from typing import Optional


class EnvVars:
    """Canonical environment variable names.

    Every env var used anywhere in the codebase is listed here.
    Use these constants instead of raw strings in os.getenv() calls.
    """

    # -- Tailscale --
    TAILSCALE_KEY = "TAILSCALE_KEY"  # Auth key for mesh init (tskey-auth-...)
    TAILSCALE_TAILNET = "TAILSCALE_TAILNET"  # Account name (user@example.com)

    # -- DigitalOcean --
    DIGITALOCEAN_API_TOKEN = "DIGITALOCEAN_API_TOKEN"  # Primary DO token (dop_v1_...)

    # -- AWS --
    AWS_ACCESS_KEY_ID = "AWS_ACCESS_KEY_ID"
    AWS_SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY"
    AWS_REGION = "AWS_REGION"

    # -- Google Cloud --
    GOOGLE_CREDENTIALS = "GOOGLE_CREDENTIALS"  # Service account JSON content
    GOOGLE_APPLICATION_CREDENTIALS = "GOOGLE_APPLICATION_CREDENTIALS"  # Path to JSON
    GOOGLE_PROJECT = "GOOGLE_PROJECT"
    GOOGLE_ZONE = "GOOGLE_ZONE"

    # -- Azure --
    AZURE_CLIENT_ID = "AZURE_CLIENT_ID"
    AZURE_CLIENT_SECRET = "AZURE_CLIENT_SECRET"
    AZURE_TENANT_ID = "AZURE_TENANT_ID"
    AZURE_SUBSCRIPTION_ID = "AZURE_SUBSCRIPTION_ID"

    # -- Linode --
    LINODE_API_KEY = "LINODE_API_KEY"

    # -- Vultr --
    VULTR_API_KEY = "VULTR_API_KEY"

    # -- UpCloud --
    UPCLOUD_USERNAME = "UPCLOUD_USERNAME"
    UPCLOUD_PASSWORD = "UPCLOUD_PASSWORD"

    # -- Exoscale --
    EXOSCALE_API_KEY = "EXOSCALE_API_KEY"
    EXOSCALE_API_SECRET = "EXOSCALE_API_SECRET"

    # -- Scaleway --
    SCALEWAY_ACCESS_KEY = "SCALEWAY_ACCESS_KEY"
    SCALEWAY_SECRET_KEY = "SCALEWAY_SECRET_KEY"

    # -- OVHcloud --
    OVH_ENDPOINT = "OVH_ENDPOINT"
    OVH_APPLICATION_KEY = "OVH_APPLICATION_KEY"
    OVH_APPLICATION_SECRET = "OVH_APPLICATION_SECRET"
    OVH_CONSUMER_KEY = "OVH_CONSUMER_KEY"

    # -- Equinix Metal --
    EQUINIXMETAL_API_KEY = "EQUINIXMETAL_API_KEY"
    EQUINIXMETAL_PROJECT_ID = "EQUINIXMETAL_PROJECT_ID"

    # -- Nomad --
    NOMAD_ADDR = "NOMAD_ADDR"
    NOMAD_TOKEN = "NOMAD_TOKEN"

    # -- Consul --
    CONSUL_ADDR = "CONSUL_ADDR"

    # -- Database --
    DATABASE_URL = "DATABASE_URL"

    # -- E2E Test Variables --
    E2E_LEADER_IP = "E2E_LEADER_IP"
    E2E_TARGET_ENV = "E2E_TARGET_ENV"
    E2E_CROSS_CLOUD = "E2E_CROSS_CLOUD"
    E2E_AWS_LEADER = "E2E_AWS_LEADER"
    E2E_HETZNER_WORKER = "E2E_HETZNER_WORKER"
    E2E_WORKER_IPS = "E2E_WORKER_IPS"

    # -- DigitalOcean Region (convenience) --
    DO_REGION = "DO_REGION"


def get_env(
    name: str, required: bool = False, default: Optional[str] = None
) -> Optional[str]:
    """Get env var with optional validation.

    Args:
        name: Environment variable name (use EnvVars constants).
        required: If True, raises ValueError when the variable is not set.
        default: Default value when the variable is not set.

    Returns:
        The env var value, or default/None if not set.

    Raises:
        ValueError: When required=True and the variable is not set.
    """
    value = os.environ.get(name, default)
    if required and not value:
        raise ValueError(f"Required environment variable '{name}' is not set")
    return value


def get_tailscale_key() -> Optional[str]:
    """Get the Tailscale auth key."""
    return get_env(EnvVars.TAILSCALE_KEY)


def get_tailscale_tailnet() -> Optional[str]:
    """Get the Tailscale tailnet name."""
    return get_env(EnvVars.TAILSCALE_TAILNET)


MESH_CONFIG_DIR = os.path.expanduser("~/.mesh")
MESH_CONFIG_FILE = os.path.join(MESH_CONFIG_DIR, "config")


def get_config_file_path() -> str:
    """Return the path to the mesh config file."""
    return MESH_CONFIG_FILE


def _parse_config_value(file_path: str, key: str) -> Optional[str]:
    """Parse a shell-style key=value line from a config file.

    Handles formats:
        NOMAD_ADDR=http://1.2.3.4:4646
        NOMAD_ADDR="http://1.2.3.4:4646"
        NOMAD_ADDR='http://1.2.3.4:4646'

    Returns the unquoted value or None if key not found / file missing.
    """
    try:
        with open(file_path, "r") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                k, _, v = stripped.partition("=")
                k = k.strip()
                if k != key:
                    continue
                v = v.strip()
                # Remove surrounding quotes (single or double)
                if len(v) >= 2 and (
                    (v.startswith('"') and v.endswith('"'))
                    or (v.startswith("'") and v.endswith("'"))
                ):
                    v = v[1:-1]
                return v
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return None


def get_nomad_addr_from_config() -> Optional[str]:
    """Read NOMAD_ADDR from ~/.mesh/config file.

    Returns the address string or None if not found.
    """
    return _parse_config_value(MESH_CONFIG_FILE, "NOMAD_ADDR")


def get_consul_addr_from_config() -> Optional[str]:
    """Read CONSUL_ADDR from ~/.mesh/config file.

    Returns the address string or None if not found.
    """
    return _parse_config_value(MESH_CONFIG_FILE, "CONSUL_ADDR")


def get_nomad_addr() -> str:
    """Get the Nomad address.

    Resolution order:
        1. NOMAD_ADDR environment variable (primary)
        2. ~/.mesh/config file (written by mesh-install.sh)
        3. http://127.0.0.1:4646 (default for local dev)

    Returns:
        The Nomad address string.
    """
    env_value = os.environ.get(EnvVars.NOMAD_ADDR)
    if env_value:
        return env_value

    config_value = get_nomad_addr_from_config()
    if config_value:
        return config_value

    return "http://127.0.0.1:4646"


def get_nomad_token() -> Optional[str]:
    """Get the Nomad token."""
    return get_env(EnvVars.NOMAD_TOKEN)


def get_consul_addr() -> str:
    """Get the Consul address.

    Resolution order:
        1. CONSUL_ADDR environment variable (primary)
        2. ~/.mesh/config file (written by mesh-install.sh)
        3. http://localhost:8500 (default for local dev)

    Returns:
        The Consul address string.
    """
    env_value = os.environ.get(EnvVars.CONSUL_ADDR)
    if env_value:
        return env_value

    config_value = get_consul_addr_from_config()
    if config_value:
        return config_value

    return "http://localhost:8500"
