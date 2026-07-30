"""
destroy command — tear down a cluster.

Contract §3b:
  Required params: cluster_name
  Optional params: provider (default digitalocean), region, api_key, cleanup_all
  Success output:  {cluster_id, status, destroyed, resources_cleaned[]}
"""

from __future__ import annotations

from typing import Any

from mesh.commands.output import (
    print_json_error,
    print_json_success,
    require_args,
    destroy_success,
    demo_destroy,
)
from mesh.providers import get_driver, is_provider_usable, USABLE_PROVIDERS
from mesh.config.env import get_env
from mesh.provisioning.direct import destroy_cluster


def handle_destroy(params: dict[str, Any]) -> None:
    """Entry point called by entrypoint.py for the 'destroy' command."""

    if params.get("demo"):
        print_json_success(demo_destroy(params.get("cluster_name", "demo-cluster")))
        return

    require_args("destroy", params, "cluster_name")

    cluster_name = params["cluster_name"]
    provider     = (params.get("provider") or "digitalocean").lower()
    region       = params.get("region", "")
    cleanup_all  = bool(params.get("cleanup_all", False))
    node_ids     = params.get("node_ids")

    # api_key is optional — fall back to env vars
    api_key = _resolve_api_key(provider, params.get("api_key", ""))

    if not is_provider_usable(provider):
        print_json_error(
            code="unknown_provider",
            message=f"Provider {provider!r} is not supported. "
                    f"Available: {', '.join(sorted(USABLE_PROVIDERS))}",
            available_providers=sorted(USABLE_PROVIDERS),
        )

    try:
        result = destroy_cluster(
            provider=provider,
            api_key=api_key,
            region=region,
            cluster_name=cluster_name,
            cleanup_all=cleanup_all,
            node_ids=node_ids,
        )
    except NotImplementedError as exc:
        print_json_error(code="provision_failed", message=str(exc), phase="destroy")
    except Exception as exc:
        print_json_error(code="provision_failed", message=str(exc), phase="destroy_resources")

    print_json_success(
        destroy_success(
            cluster_name=cluster_name,
            resources_cleaned=result.get("resources_cleaned", []),
        )
    )


def _resolve_api_key(provider: str, api_key: str) -> str:
    if api_key:
        return api_key
    _ENV_FALLBACKS = {
        "digitalocean": ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"],
        "do":           ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"],
        "aws":          ["AWS_ACCESS_KEY_ID"],
        "linode":       ["LINODE_API_KEY"],
        "vultr":        ["VULTR_API_KEY"],
    }
    for var in _ENV_FALLBACKS.get(provider, []):
        value = get_env(var)
        if value:
            return value
    print_json_error(
        code="missing_credentials",
        message=f"No API key provided for {provider!r} and no matching environment variable found.",
    )
