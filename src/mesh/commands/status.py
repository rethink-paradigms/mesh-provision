"""
status command — query whether a cluster exists and list its nodes.

Contract §3c:
  Required params: provider, cluster_name, api_key
  Success output:  {cluster_name, exists, nodes[{id, ip, role}]}
"""

from __future__ import annotations

from typing import Any

from mesh.commands.output import (
    print_json_error,
    print_json_success,
    require_args,
    status_success,
)
from mesh.providers import is_provider_usable, USABLE_PROVIDERS
from mesh.provisioning.direct import query_cluster


def handle_status(params: dict[str, Any]) -> None:
    """Entry point called by entrypoint.py for the 'status' command."""

    require_args("status", params, "provider", "cluster_name", "api_key")

    provider     = params["provider"].lower()
    cluster_name = params["cluster_name"]
    api_key      = params["api_key"]
    region       = params.get("region", "")

    if not is_provider_usable(provider):
        print_json_error(
            code="unknown_provider",
            message=f"Provider {provider!r} is not supported. "
                    f"Available: {', '.join(sorted(USABLE_PROVIDERS))}",
            available_providers=sorted(USABLE_PROVIDERS),
        )

    try:
        result = query_cluster(
            provider=provider,
            api_key=api_key,
            cluster_name=cluster_name,
            region=region,
        )
    except Exception as exc:
        print_json_error(code="status_failed", message=str(exc), phase="query_status")

    print_json_success(
        status_success(
            cluster_name=result["cluster_name"],
            exists=result["exists"],
            nodes=result["nodes"],
        )
    )
