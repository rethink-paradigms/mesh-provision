"""
remove-worker command — destroy a single worker node from an existing cluster.

Contract:
  Required params: provider, cluster_name, api_key
  One of:         node_id  OR  node_name
  Optional params: region
  Success output:  {node_id, node_name, removed: true}

Safety: refuses to remove the leader or nodes from a different cluster.
"""

from __future__ import annotations

from typing import Any

from mesh.commands.output import (
    print_json_error,
    print_json_success,
    require_args,
    remove_worker_success,
    demo_remove_worker,
)
from mesh.providers import is_provider_usable, USABLE_PROVIDERS
from mesh.provisioning.direct import remove_worker


def handle_remove_worker(params: dict[str, Any]) -> None:
    """Entry point called by entrypoint.py for the 'remove-worker' command."""

    if params.get("demo"):
        print_json_success(demo_remove_worker())
        return

    require_args("remove-worker", params, "provider", "cluster_name", "api_key")

    provider     = params["provider"].lower()
    cluster_name = params["cluster_name"]
    api_key      = params["api_key"]
    region       = params.get("region", "")
    node_id      = params.get("node_id", "")
    node_name    = params.get("node_name", "")

    if not node_id and not node_name:
        print_json_error(
            code="missing_required_args",
            message="remove-worker requires either 'node_id' or 'node_name'.",
            missing_args=["node_id or node_name"],
        )

    if not is_provider_usable(provider):
        print_json_error(
            code="unknown_provider",
            message=f"Provider {provider!r} is not supported. "
                    f"Available: {', '.join(sorted(USABLE_PROVIDERS))}",
            available_providers=sorted(USABLE_PROVIDERS),
        )

    try:
        result = remove_worker(
            provider=provider,
            api_key=api_key,
            region=region,
            cluster_name=cluster_name,
            node_id=node_id,
            node_name=node_name,
        )
    except ValueError as exc:
        print_json_error(code="provision_failed", message=str(exc), phase="remove_worker_validate")
    except Exception as exc:
        print_json_error(code="provision_failed", message=str(exc), phase="remove_worker")

    print_json_success(
        remove_worker_success(
            node_id=result["node_id"],
            node_name=result["node_name"],
        )
    )
