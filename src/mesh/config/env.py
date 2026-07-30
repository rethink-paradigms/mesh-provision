"""
Environment variable registry for mesh-provision.

All env var lookups go through get_env(). EnvVars holds the canonical names
as constants so there are no raw strings scattered across the codebase.

Usage:
    from mesh.config.env import EnvVars, get_env

    token = get_env(EnvVars.DIGITALOCEAN_API_TOKEN)
    key   = get_env(EnvVars.AWS_ACCESS_KEY_ID, required=True)
"""

import os
from typing import Optional


class EnvVars:
    """Canonical names for every environment variable this tool reads."""

    # Cloud providers
    DIGITALOCEAN_API_TOKEN = "DIGITALOCEAN_API_TOKEN"
    DO_PAT                 = "DO_PAT"
    DO_API_TOKEN           = "DO_API_TOKEN"

    AWS_ACCESS_KEY_ID      = "AWS_ACCESS_KEY_ID"
    AWS_SECRET_ACCESS_KEY  = "AWS_SECRET_ACCESS_KEY"
    AWS_REGION             = "AWS_REGION"

    LINODE_API_KEY         = "LINODE_API_KEY"
    VULTR_API_KEY          = "VULTR_API_KEY"

    # Tailscale (used for standard-tier clusters)
    TAILSCALE_KEY          = "TAILSCALE_KEY"

    # Daemon install URL override (for testing / staging releases)
    MESH_DAEMON_INSTALL_URL = "MESH_DAEMON_INSTALL_URL"

    # E2E test helpers
    E2E_LEADER_IP = "E2E_LEADER_IP"


def get_env(
    name: str,
    required: bool = False,
    default: Optional[str] = None,
) -> Optional[str]:
    """Read an environment variable.

    Args:
        name:     Variable name — use EnvVars constants.
        required: Raise ValueError if the variable is not set.
        default:  Return this if the variable is not set.

    Returns:
        The value string, or default/None.
    """
    value = os.environ.get(name, default)
    if required and not value:
        raise ValueError(f"Required environment variable {name!r} is not set.")
    return value
