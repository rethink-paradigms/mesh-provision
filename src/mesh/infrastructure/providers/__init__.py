"""
Multi-Cloud Provider Support Package

This package provides cloud-agnostic infrastructure provisioning using Apache Libcloud.
It supports 50+ cloud providers through a unified interface without hardcoded configuration.

Key Principles:
    - Query providers at runtime for available options (sizes, regions, images)
    - Use exact provider values (no size tier abstractions)
    - Follow cloud provider conventions for credentials

Usage:
    from mesh.infrastructure.providers import get_driver, get_credentials, list_sizes
    from libcloud.compute.types import Provider

    # List available options for a provider
    sizes = list_sizes("aws", "us-east-1")
    regions = list_regions("aws")

    # Provision with exact values
    driver = get_driver("aws")
    node = driver.create_node(...)

Available Providers:
    aws, digitalocean, hetzner, gcp, azure, linode, vultr, upcloud, and 40+ more
    (see: https://libcloud.readthedocs.io/en/stable/compute/supported_providers.html)
"""

import os
from typing import Dict, List
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver as libcloud_get_driver

from mesh.infrastructure.config.env import get_env


# =============================================================================
# Provider Enum Mappings
# =============================================================================

"""
Maps provider identifiers to Libcloud Provider enums.

Libcloud supports 50+ providers out of the box. This mapping only needs to include
providers you actually use. To add a new provider, add one line:

    "provider-id": Provider.PROVIDER_ENUM,

See full list: https://libcloud.readthedocs.io/en/stable/compute/supported_providers.html
"""
PROVIDER_ENUMS: Dict[str, Provider] = {
    # Amazon Web Services
    "aws": Provider.EC2,
    # DigitalOcean
    "digitalocean": Provider.DIGITAL_OCEAN,
    "do": Provider.DIGITAL_OCEAN,  # Alias
    # Google Cloud Platform — UNSUPPORTED: driver requires service account JSON auth,
    # not the key/secret pair passed here. Do not use until GCE auth is reworked.
    "gcp": Provider.GCE,  # UNSUPPORTED: requires service account JSON auth
    "google": Provider.GCE,  # UNSUPPORTED: requires service account JSON auth (alias)
    # Microsoft Azure — UNSUPPORTED: Azure ARM driver init not verified against live API.
    "azure": Provider.AZURE_ARM,  # UNSUPPORTED: Azure ARM driver not verified
    # Linode (Akamai Connected Cloud)
    "linode": Provider.LINODE,
    # Vultr
    "vultr": Provider.VULTR,
    # UpCloud
    "upcloud": Provider.UPCLOUD,
    # Exoscale
    "exoscale": Provider.EXOSCALE,
    # Scaleway
    "scaleway": Provider.SCALEWAY,
    # OVHcloud
    "ovh": Provider.OVH,
    # Equinix Metal
    "equinixmetal": Provider.EQUINIXMETAL,
    # Gridscale and Cloudscale removed: zero credential env vars, zero tests,
    # not used in any deployment. Re-add if officially adopted.
    # Note: Hetzner (Hetzner Cloud) may not be available in all Libcloud versions
    # If available, add: "hetzner": Provider.HETZNER
    # Add more providers as needed - see Libcloud docs
}

# Providers that are enumerated above but cannot be used via get_driver() because
# their authentication requirements differ from what the current driver init provides.
UNSUPPORTED_PROVIDERS: frozenset = frozenset({"gcp", "google", "azure"})


# =============================================================================
# Credential Resolution
# =============================================================================

"""
Standard environment variable names for cloud provider credentials.

These follow cloud provider conventions. Most providers use a single API token
or key pair. Override programmatically via the credentials parameter if needed.

To add credentials for a new provider, simply follow the provider's documentation
for environment variable names.
"""
CREDENTIAL_ENV_VARS: Dict[str, List[str]] = {
    "aws": [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
    ],
    "digitalocean": ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"],
    "do": ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"],  # Alias
    "gcp": [
        "GOOGLE_CREDENTIALS",  # Service account JSON content
        "GOOGLE_APPLICATION_CREDENTIALS",  # Path to JSON file
    ],
    "azure": [
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
    ],
    "linode": ["LINODE_API_KEY"],
    "vultr": ["VULTR_API_KEY"],
    "upcloud": ["UPCLOUD_USERNAME", "UPCLOUD_PASSWORD"],
    "exoscale": ["EXOSCALE_API_KEY", "EXOSCALE_API_SECRET"],
    "scaleway": ["SCALEWAY_ACCESS_KEY", "SCALEWAY_SECRET_KEY"],
    "ovh": [
        "OVH_ENDPOINT",
        "OVH_APPLICATION_KEY",
        "OVH_APPLICATION_SECRET",
        "OVH_CONSUMER_KEY",
    ],
    "equinixmetal": ["EQUINIXMETAL_API_KEY", "EQUINIXMETAL_PROJECT_ID"],
}


def get_credentials(
    provider_id: str, region: str = None, **overrides
) -> Dict[str, str]:
    """
    Resolve credentials for a provider from environment variables.

    Args:
        provider_id: The provider identifier (e.g., "aws", "digitalocean")
        region: Optional region for providers that require it (e.g., AWS)
        **overrides: Optional credential overrides (bypasses env vars)

    Returns:
        Dictionary of credential parameters for the Libcloud driver

    Raises:
        ValueError: If required credentials are missing

    Examples:
        >>> get_credentials("aws")
        {'key': 'AKIA...', 'secret': 'abcd...'}

        >>> get_credentials("digitalocean")
        {'key': 'dop_v1_...'}

        >>> get_credentials("aws", key="custom", secret="custom")
        {'key': 'custom', 'secret': 'custom'}
    """
    # If overrides provided, use them directly
    if overrides:
        return overrides

    # Get expected env vars for this provider
    env_vars = CREDENTIAL_ENV_VARS.get(provider_id, [])

    if not env_vars:
        # Fallback: try common patterns
        env_vars = [f"{provider_id.upper()}_API_KEY", f"{provider_id.upper()}_TOKEN"]

    # Resolve values from environment
    # Group env vars by their mapped key name — vars mapping to the same key
    # are alternatives (any one is sufficient)
    credentials = {}
    key_groups: Dict[str, List[str]] = {}

    for env_var in env_vars:
        key = _map_credential_key(provider_id, env_var)
        key_groups.setdefault(key, []).append(env_var)

    missing_keys = []
    for key, alternatives in key_groups.items():
        # Try each alternative env var for this key
        found = False
        for env_var in alternatives:
            value = get_env(env_var)
            if value:
                credentials[key] = value
                found = True
                break  # First match wins
        if not found:
            missing_keys.append(f"{key} ({' or '.join(alternatives)})")

    # AWS-specific: handle region
    if provider_id == "aws" and region:
        credentials["region"] = region

    if missing_keys:
        raise ValueError(
            f"Missing required credentials for '{provider_id}': "
            f"{', '.join(missing_keys)}. "
            f"Set these environment variables or pass credentials parameter."
        )

    return credentials


def _map_credential_key(provider_id: str, env_var: str) -> str:
    """
    Map environment variable name to Libcloud driver parameter name.

    Libcloud drivers expect specific parameter names. This function maps
    environment variable names to the expected parameter names.

    Args:
        provider_id: The provider identifier
        env_var: The environment variable name

    Returns:
        The parameter name expected by the Libcloud driver
    """
    # AWS-specific mappings
    if provider_id == "aws":
        if env_var == "AWS_ACCESS_KEY_ID":
            return "key"
        elif env_var == "AWS_SECRET_ACCESS_KEY":
            return "secret"

    # For most providers, use the last part of the env var name
    # e.g., DIGITALOCEAN_API_TOKEN -> key
    # e.g., LINODE_API_KEY -> key
    parts = env_var.lower().split("_")
    if (
        "api_key" in env_var.lower()
        or "token" in env_var.lower()
        or "pat" in env_var.lower().split("_")
    ):
        return "key"
    elif "secret" in env_var.lower():
        return "secret"
    else:
        # Default: use the last part
        return parts[-1] if parts else "value"


# =============================================================================
# Driver Initialization
# =============================================================================


def get_driver(
    provider_id: str, credentials: Dict[str, str] = None, region: str = None
):
    """
    Initialize a Libcloud driver for the specified provider.

    This is a convenience wrapper around libcloud.compute.providers.get_driver
    that handles credential resolution automatically.

    Args:
        provider_id: The provider identifier (e.g., "aws", "digitalocean")
        credentials: Optional credential dictionary (auto-resolved from env if None)
        region: Optional region for providers that require it

    Returns:
        Initialized Libcloud NodeDriver instance

    Raises:
        ValueError: If provider_id is not supported or credentials are missing

    Examples:
        >>> driver = get_driver("aws", region="us-east-1")
        >>> driver.list_sizes()

        >>> driver = get_driver("digitalocean")
        >>> driver.list_locations()
    """
    # Get provider enum
    if provider_id not in PROVIDER_ENUMS:
        supported = ", ".join(sorted(PROVIDER_ENUMS.keys()))
        raise ValueError(
            f"Unknown provider '{provider_id}'. "
            f"Supported providers: {supported}. "
            f"See https://libcloud.readthedocs.io/en/stable/compute/supported_providers.html"
        )

    if provider_id in UNSUPPORTED_PROVIDERS:
        raise ValueError(
            f"Provider '{provider_id}' is currently UNSUPPORTED. "
            f"GCP requires service account JSON auth; Azure ARM driver is unverified. "
            f"Remove '{provider_id}' from UNSUPPORTED_PROVIDERS once auth is correctly implemented."
        )

    provider_enum = PROVIDER_ENUMS[provider_id]

    # Get credentials
    if credentials is None:
        credentials = get_credentials(provider_id, region)

    # Initialize driver
    try:
        DriverClass = libcloud_get_driver(provider_enum)

        # Build driver args based on provider
        if provider_id == "aws":
            driver = DriverClass(
                credentials.get("key"),
                credentials.get("secret"),
                region or credentials.get("region", "us-east-1"),
            )
        elif provider_id in ("digitalocean", "do"):
            driver = DriverClass(credentials.get("key"))
        else:
            driver = DriverClass(*credentials.values())

        return driver

    except Exception as e:
        raise ValueError(f"Failed to initialize {provider_id} driver: {str(e)}")


# =============================================================================
# Provider Discovery
# =============================================================================


def list_providers() -> List[str]:
    """
    Get list of all configured provider identifiers.

    Returns:
        List of provider IDs that can be used with get_driver()
    """
    return sorted(PROVIDER_ENUMS.keys())


def is_provider_supported(provider_id: str) -> bool:
    """
    Check if a provider is supported.

    Args:
        provider_id: The provider identifier to check

    Returns:
        True if the provider is supported, False otherwise
    """
    return provider_id in PROVIDER_ENUMS
