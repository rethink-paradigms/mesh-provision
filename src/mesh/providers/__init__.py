"""
Cloud provider registry and driver initialization.

Supported providers (usable via get_driver):
    digitalocean / do   — single API token
    aws                 — access key + secret key
    linode              — single API key
    vultr               — single API key

Registered but not usable:
    gcp / google        — requires service account JSON (not a simple token)
    azure               — ARM driver unverified

Usage:
    from mesh.providers import get_driver, is_provider_usable, USABLE_PROVIDERS

    driver = get_driver("digitalocean", api_key="dop_v1_...")
    driver = get_driver("aws", api_key="AKIA...:secretkey")
"""

from __future__ import annotations

from typing import Optional
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver as _libcloud_get_driver

from mesh.config.env import get_env


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# All registered provider IDs → Libcloud enum
PROVIDER_ENUMS: dict[str, Provider] = {
    "digitalocean": Provider.DIGITAL_OCEAN,
    "do":           Provider.DIGITAL_OCEAN,
    "aws":          Provider.EC2,
    "linode":       Provider.LINODE,
    "vultr":        Provider.VULTR,
    # Registered but blocked — auth requirements differ
    "gcp":          Provider.GCE,
    "google":       Provider.GCE,
    "azure":        Provider.AZURE_ARM,
}

# Providers that are registered above but cannot be instantiated via get_driver()
# because their auth is more complex than a simple key/token.
_UNSUPPORTED: frozenset[str] = frozenset({"gcp", "google", "azure"})

# Friendly set of providers that actually work
USABLE_PROVIDERS: frozenset[str] = frozenset(PROVIDER_ENUMS.keys()) - _UNSUPPORTED


# Env var fallbacks per provider (tried in order if api_key not passed)
_ENV_FALLBACKS: dict[str, list[str]] = {
    "digitalocean": ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"],
    "do":           ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"],
    "aws":          ["AWS_ACCESS_KEY_ID"],       # secret resolved separately
    "linode":       ["LINODE_API_KEY"],
    "vultr":        ["VULTR_API_KEY"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_provider_usable(provider_id: str) -> bool:
    """Return True only if the provider is registered AND can be instantiated.

    Explicitly returns False for gcp/google/azure even though they are
    registered in PROVIDER_ENUMS.
    """
    return provider_id in USABLE_PROVIDERS


def list_providers() -> list[str]:
    """Return sorted list of usable provider IDs."""
    return sorted(USABLE_PROVIDERS)


def get_driver(provider_id: str, api_key: str, region: str = ""):
    """Initialize and return a Libcloud NodeDriver.

    Args:
        provider_id: Provider identifier. Must be in USABLE_PROVIDERS.
        api_key:     API key/token. For AWS: "ACCESS_KEY_ID:SECRET_ACCESS_KEY".
                     If empty, falls back to environment variables.
        region:      Region string (required for AWS; optional for others).

    Returns:
        Initialized Libcloud NodeDriver.

    Raises:
        ValueError: If provider is unknown, unsupported, credentials missing,
                    or driver init fails.
    """
    pid = provider_id.lower()

    if pid not in PROVIDER_ENUMS:
        raise ValueError(
            f"Unknown provider {provider_id!r}. "
            f"Usable providers: {', '.join(sorted(USABLE_PROVIDERS))}"
        )

    if pid in _UNSUPPORTED:
        raise ValueError(
            f"Provider {provider_id!r} is not supported. "
            f"GCP requires service-account JSON auth; Azure ARM is unverified. "
            f"Usable providers: {', '.join(sorted(USABLE_PROVIDERS))}"
        )

    resolved_key = _resolve_key(pid, api_key)
    DriverClass = _libcloud_get_driver(PROVIDER_ENUMS[pid])

    try:
        if pid == "aws":
            key, secret = _split_aws_creds(pid, resolved_key, region)
            return DriverClass(key, secret, region=region or "us-east-1")

        elif pid in ("digitalocean", "do"):
            return DriverClass(resolved_key)

        else:
            # Linode, Vultr, etc. — single token
            return DriverClass(resolved_key)

    except Exception as exc:
        raise ValueError(
            f"Failed to initialize {provider_id!r} driver: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_key(provider_id: str, api_key: str) -> str:
    """Return api_key if given, otherwise check env var fallbacks."""
    if api_key:
        return api_key

    for var in _ENV_FALLBACKS.get(provider_id, []):
        value = get_env(var)
        if value:
            return value

    raise ValueError(
        f"No API key provided for {provider_id!r} and no matching "
        f"environment variable found ({', '.join(_ENV_FALLBACKS.get(provider_id, []))})"
    )


def _split_aws_creds(provider_id: str, api_key: str, region: str) -> tuple[str, str]:
    """Split 'ACCESS_KEY_ID:SECRET_ACCESS_KEY' into (key, secret).

    Also checks AWS_SECRET_ACCESS_KEY env var if no colon in api_key.
    """
    if ":" in api_key:
        key, _, secret = api_key.partition(":")
        return key.strip(), secret.strip()

    # api_key is just the access key ID — look for secret in env
    secret = get_env("AWS_SECRET_ACCESS_KEY") or ""
    if not secret:
        raise ValueError(
            "AWS requires both access key and secret. "
            "Pass as 'ACCESS_KEY_ID:SECRET_ACCESS_KEY' or set AWS_SECRET_ACCESS_KEY env var."
        )
    return api_key, secret
