"""
mesh — Infrastructure Platform CLI

Deploy containerized applications across any compute, from a local
laptop to a multi-cloud cluster. Zero-SSH deployment. Auto-HTTPS. Multi-cloud.

Usage:
    mesh init                    Initialize a new cluster
    mesh status                  View cluster health
    mesh logs                    View application logs
    mesh ssh                     Connect to a node
    mesh destroy                 Tear down cluster

Quick start:
    mesh init                    # Interactive wizard
    mesh status
"""

import typer
from typing import Optional

from importlib.metadata import version as pkg_version

from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from mesh.cli.commands.init_cmd import run_init
from mesh.cli.commands.status import run_status
from mesh.cli.commands.destroy import run_destroy
from mesh.cli.commands.logs import run_logs
from mesh.cli.commands.ssh import run_ssh
from mesh.cli.commands.doctor import run_doctor
from mesh.cli.commands.snapshot import snapshot_app
from mesh.cli.ui.panels import (
    console,
    show_banner,
    show_resource_comparison,
    show_vision_roadmap,
    show_provisioning_progress,
)
from mesh.cli.ui.themes import MESH_CYAN, MESH_GREEN, MESH_DIM, STATUS_ICONS
from mesh.cli.plugins import discover_plugins

# Create the main app
app = typer.Typer(
    name="mesh",
    help="Infrastructure Platform — Deploy containers across any cloud. Zero-SSH deployment.",
    no_args_is_help=True,
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
    add_completion=False,
)


@app.command("init")
def init(
    demo: bool = typer.Option(
        False, "--demo", help="Run in demo mode (simulated provisioning)"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Skip provider prompt"
    ),
    region: Optional[str] = typer.Option(
        None, "--region", "-r", help="Cloud region (skip prompt)"
    ),
    workers: Optional[int] = typer.Option(
        None, "--workers", "-w", help="Number of worker nodes"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    output: Optional[str] = typer.Option(
        None, "--output", help="Output format: 'json' for machine-readable (default: rich)"
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="Cloud provider API key/token (overrides .env, required when --output json)"
    ),

    leader_size: Optional[str] = typer.Option(
        None, "--leader-size", help="VM size for leader node (required when --output json)"
    ),
    cluster_name: Optional[str] = typer.Option(
        None, "--cluster-name", help="Cluster name (required when --output json)"
    ),
    post_boot_script: Optional[str] = typer.Option(
        None, "--post-boot-script", help="URL of a post-boot script to download and run after infrastructure is ready"
    ),
    input: Optional[str] = typer.Option(
        None, "--input", help="Input mode: 'stdin' to read JSON from stdin (default: CLI args)"
    ),
):
    """
    Initialize a new mesh cluster.

    Interactive wizard that guides you through provider selection,
    region, sizing, and cluster provisioning.

    Example:
        mesh init
        mesh init --demo
        mesh init --provider "Local (Multipass)" --workers 2
        mesh init --provider DigitalOcean --region nyc3 --workers 1 --yes
    """
    run_init(
        demo=demo,
        provider_name=provider,
        region=region,
        workers=workers,
        yes=yes,
        output=output,
        api_key=api_key,
        leader_size=leader_size,
        cluster_name=cluster_name,
        post_boot_script=post_boot_script,
        input=input,
    )


@app.command("status")
def status(
    demo: bool = typer.Option(False, "--demo", help="Show demo data"),
    compare: bool = typer.Option(False, "--compare", help="Show K8s comparison"),
    roadmap: bool = typer.Option(False, "--roadmap", help="Show capability roadmap"),
):
    """
    View cluster health, node topology, and running apps.

    Shows a tree view of your mesh with nodes, apps, and their status.
    Use --compare to see how the platform compares to Kubernetes.
    Use --roadmap to see the capability timeline.

    Example:
        mesh status
        mesh status --demo --compare --roadmap
    """
    run_status(demo=demo, show_comparison=compare, show_roadmap=roadmap)


@app.command("destroy")
def destroy(
    cluster: str = typer.Option("mesh-cluster", "--cluster", "-c", help="Cluster name"),
    demo: bool = typer.Option(False, "--demo", help="Run in demo mode"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    output: Optional[str] = typer.Option(
        None, "--output", help="Output format: 'json' for machine-readable (default: rich)"
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="Cloud provider API key/token (overrides .env)"
    ),
):
    """
    Tear down a mesh cluster.

    Stops all running apps, then terminates all nodes.
    Requires confirmation (or --yes flag for non-interactive use).

    Example:
        mesh destroy
        mesh destroy --cluster my-cluster
        mesh destroy --yes
    """
    run_destroy(cluster_name=cluster, demo=demo, yes=yes, output=output, api_key=api_key)


@app.command("add-worker")
def add_worker(
    cluster: str = typer.Option("mesh-cluster", "--cluster", "-c", help="Cluster name to add worker to"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Cloud provider"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="Cloud region"),
    size: Optional[str] = typer.Option(None, "--size", "-s", help="VM size for worker"),
    leader_ip: Optional[str] = typer.Option(None, "--leader-ip", help="Leader node public IP"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Cloud provider API key/token"),
    output: Optional[str] = typer.Option(None, "--output", help="Output format: 'json' for machine-readable"),
    demo: bool = typer.Option(False, "--demo", help="Run in demo mode"),
):
    """
    Add a worker node to an existing mesh cluster.

    Example:
        mesh add-worker --cluster my-cluster --provider digitalocean
        mesh add-worker --output json --cluster my-cluster --provider digitalocean --region nyc3 --size s-1vcpu-1gb --api-key $DO_KEY --leader-ip 1.2.3.4
    """
    from mesh.cli.commands.add_worker import run_add_worker
    run_add_worker(
        cluster_name=cluster,
        provider=provider,
        region=region,
        size=size,
        api_key=api_key,
        leader_ip=leader_ip,
        output=output,
        demo=demo,
    )


@app.command("logs")
def logs(
    job_name: Optional[str] = typer.Argument(None, help="Job name to fetch logs for"),
    follow: bool = typer.Option(
        False, "--follow", "-f", help="Stream logs in real-time"
    ),
    tail: int = typer.Option(20, "--tail", "-n", help="Number of lines to show"),
    alloc: Optional[str] = typer.Option(
        None, "--alloc", "-a", help="Specific allocation ID"
    ),
    stderr: bool = typer.Option(
        False, "--stderr", help="Show stderr instead of stdout"
    ),
    demo: bool = typer.Option(
        False, "--demo", help="Run in demo mode (simulated output)"
    ),
):
    """
    View logs from jobs running on the mesh cluster.

    Without a job name, lists all running jobs.
    Use --follow to stream logs in real-time.

    Example:
        mesh logs
        mesh logs my-app
        mesh logs my-app --follow
        mesh logs my-app --tail 50 --stderr
    """
    run_logs(
        job_name=job_name,
        follow=follow,
        tail=tail,
        alloc=alloc,
        stderr=stderr,
        demo=demo,
    )


@app.command("ssh")
def ssh(
    node_name: Optional[str] = typer.Argument(None, help="Node name to connect to"),
    user: Optional[str] = typer.Option(
        None, "--user", "-u", help="SSH user (auto-detected from provider)"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Cloud provider (for default SSH user)"
    ),
    demo: bool = typer.Option(
        False, "--demo", help="Run in demo mode (simulated output)"
    ),
):
    """
    SSH into a cluster node.

    Without a node name, lists all available nodes.
    Tries Tailscale IPs when available.

    Example:
        mesh ssh
        mesh ssh mesh-leader
        mesh ssh mesh-worker-1 --user admin
        mesh ssh mesh-leader --provider digitalocean
    """
    run_ssh(node_name=node_name, user=user, demo=demo, provider=provider)


@app.command("demo")
def demo():
    """
    Run the full mesh experience in demo mode.

    Simulates init, deploy, and status without real infrastructure.
    A quick way to see the platform in action.
    """
    show_banner()
    console.print(f"  [bold {MESH_CYAN}]Running Mesh Demo[/]")
    console.print("  [dim]Simulated — no real infrastructure needed[/dim]")
    console.print()

    init_steps = [
        {"name": "Checking prerequisites...", "duration": "0.4"},
        {"name": "Generating Tailscale auth key...", "duration": "0.3"},
        {"name": "Provisioning leader (mesh-cluster-leader)...", "duration": "1.5"},
        {"name": "Provisioning worker (mesh-cluster-worker-1)...", "duration": "1.2"},
        {"name": "Configuring mesh network...", "duration": "0.5"},
        {"name": "Starting Nomad scheduler...", "duration": "0.4"},
        {"name": "Starting Consul discovery...", "duration": "0.4"},
        {"name": "Verifying cluster health...", "duration": "0.3"},
    ]
    show_provisioning_progress(init_steps, live=True)

    init_body = Text()
    init_body.append(f"\n  {STATUS_ICONS['healthy']} ", style="bold")
    init_body.append("Cluster is ready!\n\n", style=f"bold {MESH_GREEN}")
    init_body.append("  Cluster:  ", style="dim")
    init_body.append("mesh-cluster\n", style=f"bold {MESH_CYAN}")
    init_body.append("  Tier:     ", style="dim")
    init_body.append("Local (Multipass)\n", style=f"bold {MESH_CYAN}")
    init_body.append("  Nodes:    ", style="dim")
    init_body.append("1 leader + 1 worker\n", style=f"bold {MESH_CYAN}")
    init_body.append("  Provider: ", style="dim")
    init_body.append("multipass (local)\n", style=f"bold {MESH_CYAN}")
    console.print(Panel(init_body, border_style=MESH_GREEN, padding=(0, 1)))
    console.print()

    deploy_steps = [
        {"name": "Detecting cluster tier...", "duration": "0.3"},
        {"name": "Building Nomad job specification...", "duration": "0.4"},
        {"name": "Submitting job to cluster...", "duration": "0.5"},
        {"name": "Pulling nginx:latest...", "duration": "1.2"},
        {"name": "Starting container on mesh-cluster-leader...", "duration": "0.6"},
        {"name": "Verifying health check...", "duration": "0.3"},
    ]
    show_provisioning_progress(deploy_steps, live=True)

    deploy_summary = Table(show_header=False, border_style=MESH_DIM, padding=(0, 2))
    deploy_summary.add_column("Key", style="dim")
    deploy_summary.add_column("Value", style=f"bold {MESH_CYAN}")
    deploy_summary.add_row("App", "hello-mesh")
    deploy_summary.add_row("Image", "nginx:latest")
    deploy_summary.add_row("Port", "8080")
    deploy_summary.add_row("CPU", "100 MHz")
    deploy_summary.add_row("Memory", "128 MB")
    deploy_summary.add_row("Replicas", "1")
    deploy_summary.add_row("Node", "mesh-cluster-leader")
    deploy_summary.add_row("Status", f"{STATUS_ICONS['running']} running")
    console.print(
        Panel(
            deploy_summary,
            title=f"[bold {MESH_CYAN}]{STATUS_ICONS['app']} Deployed hello-mesh[/]",
            border_style=MESH_GREEN,
            padding=(1, 2),
        )
    )
    console.print()

    run_status(demo=True)

    next_steps = Text()
    next_steps.append("\n  Demo complete! ", style=f"bold {MESH_GREEN}")
    next_steps.append("Ready to try for real?\n\n", style="dim")
    next_steps.append("  mesh init          ", style=MESH_GREEN)
    next_steps.append("— provision a real cluster\n", style="dim")
    next_steps.append("  mesh doctor        ", style=MESH_GREEN)
    next_steps.append("— check your environment\n", style="dim")
    console.print(Panel(next_steps, border_style=MESH_CYAN, padding=(0, 1)))
    console.print()


@app.command("doctor")
def doctor(
    demo: bool = typer.Option(False, "--demo", help="Show simulated output"),
):
    """
    Check if your environment is ready for mesh.

    Verifies Python version, Docker, Pulumi, Tailscale, environment
    variables, and network connectivity.
    """
    run_doctor(demo=demo)


@app.command("version")
def version():
    """Show the mesh CLI version."""
    try:
        v = pkg_version("mesh")
    except Exception:
        v = "0.3.0 (dev)"
    show_banner()
    from mesh.cli.ui.panels import console
    from mesh.cli.ui.themes import MESH_CYAN

    console.print(f"\n  [bold {MESH_CYAN}]mesh[/] v{v}\n")


@app.command("compare")
def compare():
    """Show resource comparison: Mesh Platform vs Kubernetes."""
    show_banner()
    show_resource_comparison()


@app.command("roadmap")
def roadmap():
    """Show the capability roadmap and future vision."""
    show_banner()
    show_vision_roadmap()


app.add_typer(snapshot_app, name="snapshot")

# Discover and register plugins from installed packages
# Enterprise features (GPU, monitoring, backups, etc.) register here
for _plugin_app, _plugin_name in discover_plugins():
    app.add_typer(_plugin_app, name=_plugin_name)


def main():
    """Entry point for the mesh CLI."""
    app()


if __name__ == "__main__":
    main()
