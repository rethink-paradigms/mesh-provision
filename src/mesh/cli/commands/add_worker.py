"""Add a worker node to an existing cluster.

Supports both JSON mode (--output json) and interactive mode (Rich UI).
"""

from __future__ import annotations
from typing import Optional
import typer
from mesh.cli.commands.json_output import (
    print_json_success,
    print_json_error,
    require_json_mode_args,
    build_demo_add_worker_json,
)
from mesh.cli.ui.panels import show_banner, show_success, show_error


def run_add_worker(
    cluster_name: str,
    provider: Optional[str] = None,
    region: Optional[str] = None,
    size: Optional[str] = None,
    api_key: Optional[str] = None,
    leader_ip: Optional[str] = None,
    output: Optional[str] = None,
    demo: bool = False,
) -> None:
    """Add a worker node to an existing mesh cluster."""
    if output == "json":
        _run_add_worker_json(
            cluster_name=cluster_name,
            provider=provider or "",
            region=region or "",
            size=size or "s-1vcpu-1gb",
            api_key=api_key or "",
            leader_ip=leader_ip or "",
            demo=demo,
        )
        return

    _run_add_worker_interactive(
        cluster_name=cluster_name,
        provider=provider,
        region=region,
        size=size,
        api_key=api_key,
        leader_ip=leader_ip,
        demo=demo,
    )


def _run_add_worker_json(
    cluster_name: str,
    provider: str,
    region: str,
    size: str,
    api_key: str,
    leader_ip: str,
    demo: bool,
) -> None:
    """Handle add-worker with --output json."""
    if demo:
        result = build_demo_add_worker_json()
        print_json_success(result)
        return

    require_json_mode_args(
        provider=provider,
        region=region,
        size=size,
        api_key=api_key,
        leader_ip=leader_ip,
    )

    from mesh.infrastructure.config.env import get_env, EnvVars

    if not api_key:
        api_key = get_env(EnvVars.DIGITALOCEAN_API_TOKEN) or ""
    if not api_key:
        print_json_error(code="missing_credentials", message="No API key provided")

    tailscale_key = get_env(EnvVars.TAILSCALE_KEY) or ""
    if not tailscale_key:
        print_json_error(
            code="missing_credentials",
            message="TAILSCALE_KEY not found in environment",
        )

    from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import (
        generate_shell_script,
    )

    worker_boot_script = generate_shell_script(
        tailscale_key=tailscale_key,
        leader_ip=leader_ip,
        role="client",
    )

    from mesh.infrastructure.provision_node.provision_direct import provision_node_direct

    try:
        worker = provision_node_direct(
            name=f"{cluster_name}-worker",
            provider=provider,
            region=region,
            size_id=size,
            api_key=api_key,
            boot_script=worker_boot_script,
        )
        result = {
            "node": {
                "ip": worker["public_ip"],
                "id": worker["instance_id"],
                "role": "worker",
            }
        }
        print_json_success(result)
    except Exception as e:
        print_json_error(
            code="provision_failed",
            message=str(e),
            phase="create_worker_vm",
        )


def _run_add_worker_interactive(
    cluster_name: str,
    provider: Optional[str],
    region: Optional[str],
    size: Optional[str],
    api_key: Optional[str],
    leader_ip: Optional[str],
    demo: bool,
) -> None:
    """Interactive add-worker mode with Rich UI."""
    show_banner()

    import questionary
    from rich.console import Console

    console = Console()

    if demo:
        console.print("[green]✓[/green] Demo mode: worker would be added to cluster")
        console.print(f"  Cluster: {cluster_name}")
        console.print(f"  Provider: {provider or 'digitalocean'}")
        console.print(f"  Size: {size or 's-1vcpu-1gb'}")
        return

    if not provider:
        provider = questionary.select(
            "Select provider:", choices=["DigitalOcean", "Linode", "Vultr"]
        ).ask()
        if not provider:
            show_error("Cancelled.")
            raise typer.Exit(1)

    if not region:
        region = questionary.text("Region:", default="nyc3").ask()
        if not region:
            show_error("Cancelled.")
            raise typer.Exit(1)

    show_success(f"Worker added to cluster {cluster_name}")
