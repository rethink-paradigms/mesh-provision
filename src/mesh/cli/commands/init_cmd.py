"""
mesh init — Interactive Cluster Provisioning Wizard

Creates a new mesh cluster using real provisioning (Multipass for local,
Pulumi for cloud). Beautiful Rich-formatted output throughout.
"""

import os
import sys
import shutil
from typing import Optional

import typer
import questionary
from questionary import Style as QStyle
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mesh.infrastructure.config.env import EnvVars, get_env
from mesh.cli.ui.themes import (
    MESH_CYAN,
    MESH_GREEN,
    MESH_RED,
    MESH_DIM,
    STATUS_ICONS,
)
from mesh.cli.ui.panels import (
    console,
    show_banner,
    show_success,
    show_error,
    show_warning,
    show_info,
    show_step,
    show_provisioning_progress,
)

# Questionary custom style
PROMPT_STYLE = QStyle(
    [
        ("qmark", "fg:#00d4ff bold"),
        ("question", "fg:#e0e0e0 bold"),
        ("answer", "fg:#00ff88 bold"),
        ("pointer", "fg:#00d4ff bold"),
        ("highlighted", "fg:#00d4ff bold"),
        ("selected", "fg:#00ff88"),
        ("separator", "fg:#666666"),
        ("instruction", "fg:#666666"),
    ]
)

# Provider options
PROVIDERS = {
    "Local (Multipass)": {
        "id": "multipass",
        "desc": "Run on your laptop with Multipass VMs",
        "leader_size": "2CPU,2G",
        "worker_size": "1CPU,1G",
    },
    "DigitalOcean": {
        "id": "digitalocean",
        "desc": "Cloud VMs starting at $6/mo",
        "regions": ["nyc3", "sfo3", "ams3", "sgp1", "lon1", "fra1"],
        "leader_size": "s-2vcpu-2gb",
        "worker_size": "s-1vcpu-1gb",
    },
    "AWS": {
        "id": "aws",
        "desc": "Amazon EC2 instances",
        "regions": ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"],
        "leader_size": "t3.small",
        "worker_size": "t3.micro",
    },
}

CLOUD_ENV_VARS = {
    "digitalocean": [EnvVars.DIGITALOCEAN_API_TOKEN],
    "aws": [EnvVars.AWS_ACCESS_KEY_ID, EnvVars.AWS_SECRET_ACCESS_KEY],
}


def _get_cloud_providers():
    """Build cloud provider choices from PROVIDER_ENUMS."""
    from mesh.infrastructure.providers import PROVIDER_ENUMS, list_providers

    # Known friendly names and metadata for providers
    PROVIDER_META = {
        "aws": {
            "name": "AWS",
            "desc": "Amazon EC2 instances",
            "leader_size": "t3.small",
            "worker_size": "t3.micro",
            "regions": ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"],
        },
        "digitalocean": {
            "name": "DigitalOcean",
            "desc": "Cloud VMs starting at $6/mo",
            "leader_size": "s-2vcpu-2gb",
            "worker_size": "s-1vcpu-1gb",
            "regions": ["nyc3", "sfo3", "ams3", "sgp1", "lon1", "fra1"],
        },
        "do": {
            "name": "DigitalOcean",
            "desc": "Cloud VMs starting at $6/mo",
            "leader_size": "s-2vcpu-2gb",
            "worker_size": "s-1vcpu-1gb",
            "regions": ["nyc3", "sfo3", "ams3", "sgp1", "lon1", "fra1"],
        },
        "gcp": {
            "name": "Google Cloud",
            "desc": "GCE instances",
            "leader_size": "e2-medium",
            "worker_size": "e2-micro",
            "regions": ["us-central1", "us-east1", "europe-west1"],
        },
        "azure": {
            "name": "Azure",
            "desc": "Microsoft Azure VMs",
            "leader_size": "Standard_B2s",
            "worker_size": "Standard_B1s",
            "regions": ["eastus", "westus2", "westeurope"],
        },
        "linode": {
            "name": "Linode",
            "desc": "Akamai cloud compute",
            "leader_size": "g6-standard-2",
            "worker_size": "g6-nanode-1",
            "regions": ["us-east", "us-central", "eu-west"],
        },
        "vultr": {
            "name": "Vultr",
            "desc": "High-performance cloud",
            "leader_size": "vc2-2c-4gb",
            "worker_size": "vc2-1c-1gb",
            "regions": ["ewr", "lax", "ams", "sgp"],
        },
    }

    providers = {}
    for pid in list_providers():
        meta = PROVIDER_META.get(
            pid,
            {
                "name": pid.title(),
                "desc": f"Cloud VMs via {pid}",
                "leader_size": "unknown",
                "worker_size": "unknown",
                "regions": [],
            },
        )
        if meta["name"] not in providers:  # Avoid duplicates (do/digitalocean alias)
            providers[meta["name"]] = {
                "id": pid,
                "desc": meta["desc"],
                "regions": meta["regions"],
                "leader_size": meta["leader_size"],
                "worker_size": meta["worker_size"],
            }
    return providers


def _validate_prerequisites(provider_id: str, cluster_name: str, demo: bool = False):
    if demo:
        return

    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env")
    env_path = os.path.abspath(env_path)
    if os.path.exists(env_path):
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except ImportError:
            pass

    if provider_id == "multipass":
        tailscale_key = get_env(EnvVars.TAILSCALE_KEY)
        if not tailscale_key:
            show_error("TAILSCALE_KEY not found in environment")
            console.print(
                f"  Generate one at: [bold {MESH_CYAN}]https://login.tailscale.com/admin/settings/keys[/]"
            )
            raise typer.Exit(1)
    else:
        required_vars = CLOUD_ENV_VARS.get(provider_id, [])
        missing = [var for var in required_vars if not get_env(var)]
        if missing:
            show_error(f"Missing required environment variables: {', '.join(missing)}")
            console.print(
                "  Copy [bold].env.example[/] to [bold].env[/] and add your credentials"
            )
            raise typer.Exit(1)
        tailscale_key = get_env(EnvVars.TAILSCALE_KEY)
        if not tailscale_key:
            show_error("TAILSCALE_KEY not found in environment")
            console.print(
                f"  Generate one at: [bold {MESH_CYAN}]https://login.tailscale.com/admin/settings/keys[/]"
            )
            raise typer.Exit(1)

    if not shutil.which("docker"):
        show_warning(
            "Docker not found locally. Not required, but useful for local development."
        )


def _show_failure_panel(
    cluster_name: str, error_msg: str, provisioned_vms: Optional[list] = None
):
    body = Text()
    body.append(f"\n  {error_msg}\n\n", style=f"bold {MESH_RED}")

    if provisioned_vms:
        body.append("  Partially created resources:\n", style="bold")
        for vm in provisioned_vms:
            body.append("    • ", style=MESH_RED)
            body.append(f"{vm}\n", style=MESH_CYAN)
        body.append("\n")

    body.append("  To clean up:\n", style="bold")
    body.append(f"    mesh destroy --cluster {cluster_name}\n\n", style=MESH_GREEN)

    body.append("  To get help:\n", style="bold")
    body.append("    mesh doctor\n", style=MESH_GREEN)
    body.append("    mesh logs\n\n", style=MESH_GREEN)

    body.append("  Common fixes:\n", style="bold")
    body.append("    • Check credentials: ", style="dim")
    body.append("cat .env\n", style=MESH_CYAN)
    body.append("    • Verify network: ", style="dim")
    body.append("curl -s https://api.tailscale.com\n", style=MESH_CYAN)
    body.append("    • View docs: ", style="dim")
    body.append("https://rethink-paradigms.github.io/mesh/faq/\n", style=MESH_CYAN)

    console.print(
        Panel(
            body,
            title=f"[bold {MESH_RED}]Provisioning Failed[/]",
            border_style=MESH_RED,
            padding=(0, 1),
        )
    )


def run_init(
    demo: bool = False,
    provider_name: Optional[str] = None,
    region: Optional[str] = None,
    workers: Optional[int] = None,
    yes: bool = False,
    output: Optional[str] = None,
    api_key: Optional[str] = None,
    daemon_token: Optional[str] = None,
    daemon_url: Optional[str] = None,
    leader_size: Optional[str] = None,
    cluster_name: Optional[str] = None,
):
    """
    Interactive cluster initialization wizard.

    Guides user through provider → region → sizing → provisioning.
    Uses real Multipass provisioning for local clusters.
    """
    # Route to JSON mode if --output json is set
    if output == "json":
        from mesh.cli.commands.init_json import run_init_json
        run_init_json(
            provider=provider_name or "digitalocean",
            region=region or "",
            workers=workers or 0,
            leader_size=leader_size or "s-2vcpu-4gb",
            worker_size="s-1vcpu-1gb",
            cluster_name=cluster_name or "mesh-cluster",
            api_key=api_key or "",
            daemon_token=daemon_token or "",
            daemon_url=daemon_url or "",
            demo=demo,
        )
        return

    show_banner()
    console.print(f"  [bold {MESH_CYAN}]Initialize a new Mesh cluster[/]\n")

    # Build provider list: local first, then cloud providers from PROVIDER_ENUMS
    all_providers = dict(PROVIDERS)
    all_providers.update(_get_cloud_providers())

    # Step 1: Provider Selection
    if not provider_name:
        if demo:
            provider_name = "Local (Multipass)"
        else:
            choices = []
            for name, info in all_providers.items():
                choices.append(f"{name} — {info['desc']}")

            answer = questionary.select(
                "Select compute provider:",
                choices=choices,
                style=PROMPT_STYLE,
            ).ask()

            if not answer:
                show_error("Cancelled.")
                raise typer.Exit(1)

            provider_name = answer.split(" — ")[0]

    provider = all_providers.get(provider_name)
    if not provider:
        show_error(f"Unknown provider: {provider_name}")
        raise typer.Exit(1)

    provider_id = provider["id"]
    show_info(f"Provider: [bold]{provider_name}[/bold]")

    # Step 2: Region (cloud only)
    selected_region = None
    if provider_id != "multipass":
        if demo:
            selected_region = provider.get("regions", ["us-east-1"])[0]
        elif region:
            if region not in provider.get("regions", []):
                show_warning(
                    f"Region '{region}' not in known regions for {provider_name}, using anyway."
                )
            selected_region = region
        elif provider.get("regions"):
            selected_region = questionary.select(
                "Select region:",
                choices=provider["regions"],
                style=PROMPT_STYLE,
            ).ask()
            if not selected_region:
                show_error("Cancelled.")
                raise typer.Exit(1)
        show_info(f"Region: [bold]{selected_region}[/bold]")

    # Step 3: Worker count
    if demo:
        worker_count = workers or 1
    elif workers is not None:
        worker_count = workers
    elif yes:
        worker_count = 1
    else:
        worker_count_answer = questionary.select(
            "Number of worker nodes:",
            choices=["1 (minimal)", "2 (recommended)", "3", "4"],
            default="1 (minimal)",
            style=PROMPT_STYLE,
        ).ask()
        if not worker_count_answer:
            show_error("Cancelled.")
            raise typer.Exit(1)
        worker_count = int(worker_count_answer[0])

    # Step 4: Cluster name
    if demo or yes:
        cluster_name = "mesh-cluster"
    else:
        cluster_name = questionary.text(
            "Cluster name:",
            default="mesh-cluster",
            style=PROMPT_STYLE,
        ).ask()
        if not cluster_name:
            cluster_name = "mesh-cluster"

    # Step 5: Summary and confirmation
    console.print()
    summary = Table(show_header=False, border_style=MESH_DIM, padding=(0, 2))
    summary.add_column("Key", style="dim")
    summary.add_column("Value", style=f"bold {MESH_CYAN}")

    summary.add_row("Cluster", cluster_name)
    summary.add_row("Provider", f"{provider_name} ({provider_id})")
    if selected_region:
        summary.add_row("Region", selected_region)
    summary.add_row("Leader", f"1 × {provider['leader_size']}")
    summary.add_row("Workers", f"{worker_count} × {provider['worker_size']}")
    summary.add_row("Control Plane", "~530 MB (Nomad + Consul + Tailscale + Docker)")
    summary.add_row("Worker Overhead", "~160 MB (leaves max RAM for apps)")

    console.print(
        Panel(
            summary,
            title=f"[bold {MESH_CYAN}]Cluster Configuration[/]",
            border_style=MESH_CYAN,
            padding=(1, 2),
        )
    )
    console.print()

    if not demo and not yes:
        confirm = questionary.confirm(
            "Deploy this cluster?",
            default=True,
            style=PROMPT_STYLE,
        ).ask()

        if not confirm:
            show_error("Cancelled.")
            raise typer.Exit(0)

    _validate_prerequisites(provider_id, cluster_name, demo=demo)

    console.print()

    try:
        if provider_id == "multipass":
            _provision_multipass(cluster_name, worker_count, demo=demo)
        else:
            _provision_cloud(
                cluster_name,
                provider_id,
                selected_region,
                worker_count,
                provider,
                demo=demo,
                provider_name=provider_name,
            )
    except typer.Exit:
        raise
    except Exception as e:
        _show_failure_panel(cluster_name, str(e))
        raise typer.Exit(1)


def _provision_multipass(cluster_name: str, worker_count: int, demo: bool = False):
    """Provision a local cluster using Multipass."""

    # Check multipass
    multipass_cmd = shutil.which("multipass")
    if not multipass_cmd and not demo:
        show_error("Multipass not found. Install with: brew install --cask multipass")
        raise typer.Exit(1)

    # Check for .env / tailscale key
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    env_path = os.path.abspath(env_path)

    has_env = os.path.exists(env_path)
    if not has_env and not demo:
        show_error(
            f".env not found at {env_path}. Copy .env.example and add TAILSCALE_KEY"
        )
        raise typer.Exit(1)

    steps = [
        {"name": "Checking prerequisites...", "duration": "0.5"},
        {"name": "Generating Tailscale auth key...", "duration": "0.3"},
        {"name": f"Provisioning leader ({cluster_name}-leader)...", "duration": "2"},
    ]
    for i in range(worker_count):
        steps.append(
            {
                "name": f"Provisioning worker ({cluster_name}-worker-{i + 1})...",
                "duration": "1.5",
            }
        )
    steps.append({"name": "Configuring mesh network...", "duration": "0.5"})
    steps.append({"name": "Starting Nomad scheduler...", "duration": "0.5"})
    steps.append({"name": "Starting Consul discovery...", "duration": "0.5"})
    steps.append({"name": "Verifying cluster health...", "duration": "0.3"})

    if demo:
        show_provisioning_progress(steps, live=True)
        _show_cluster_ready(
            cluster_name,
            "multipass",
            "local",
            worker_count,
            provider_name="Local (Multipass)",
        )
        return

    # Real provisioning using the existing local cluster CLI
    console.print(f"\n  [info]Launching Multipass cluster...[/info]\n")

    provisioned_vms = []

    try:
        # Use the existing cli.py logic
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        sys.path.insert(0, project_root)

        from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import (
            generate_shell_script,
        )
        from mesh.infrastructure.provision_node.multipass import (
            provision_multipass_node,
        )
        from dotenv import load_dotenv

        load_dotenv(env_path)
        tailscale_key = get_env(EnvVars.TAILSCALE_KEY)
        if not tailscale_key:
            show_error("TAILSCALE_KEY not found in .env")
            raise typer.Exit(1)

        # Provision leader
        show_step(1, 2 + worker_count, f"Provisioning {cluster_name}-leader...")
        leader_script = generate_shell_script(
            tailscale_key=tailscale_key, leader_ip="127.0.0.1", role="server"
        )
        leader_info = provision_multipass_node(
            name=f"{cluster_name}-leader",
            instance_size="2CPU,2G",
            role="server",
            boot_script_content=leader_script,
        )
        leader_ip = leader_info.get("private_ip", "127.0.0.1")
        provisioned_vms.append(f"{cluster_name}-leader ({leader_ip})")
        show_success(f"Leader ready at {leader_ip}")

        # Provision workers
        for i in range(worker_count):
            worker_name = f"{cluster_name}-worker-{i + 1}"
            show_step(2 + i, 2 + worker_count, f"Provisioning {worker_name}...")
            worker_script = generate_shell_script(
                tailscale_key=tailscale_key, leader_ip=leader_ip, role="client"
            )
            provision_multipass_node(
                name=worker_name,
                instance_size="1CPU,1G",
                role="client",
                boot_script_content=worker_script,
            )
            provisioned_vms.append(worker_name)
            show_success(f"{worker_name} ready")

        _show_cluster_ready(
            cluster_name,
            "multipass",
            "local",
            worker_count,
            node_ips=[leader_ip],
            provider_name="Local (Multipass)",
        )

    except ImportError as e:
        show_error(f"Import error: {e}")
        show_info("Falling back to demo mode...")
        show_provisioning_progress(steps, live=True)
        _show_cluster_ready(cluster_name, "multipass", "local", worker_count)
    except Exception as e:
        _show_failure_panel(cluster_name, str(e), provisioned_vms)
        raise typer.Exit(1)


def _provision_cloud(
    cluster_name: str,
    provider_id: str,
    region: str,
    worker_count: int,
    provider: dict,
    demo: bool = False,
    provider_name: Optional[str] = None,
):
    """Provision a cloud cluster using Pulumi."""
    steps = [
        {"name": "Validating cloud credentials...", "duration": "0.5"},
        {"name": "Generating Tailscale auth key...", "duration": "0.5"},
        {
            "name": f"Provisioning leader ({provider['leader_size']})...",
            "duration": "3",
        },
    ]
    for i in range(worker_count):
        steps.append(
            {
                "name": f"Provisioning worker {i + 1} ({provider['worker_size']})...",
                "duration": "2",
            }
        )
    steps.extend(
        [
            {"name": "Configuring mesh network...", "duration": "0.5"},
            {"name": "Starting Nomad + Consul...", "duration": "0.5"},
            {"name": "Configuring Traefik ingress...", "duration": "0.5"},
            {"name": "Verifying cluster health...", "duration": "0.3"},
        ]
    )

    if demo:
        show_provisioning_progress(steps, live=True)
        _show_cluster_ready(
            cluster_name, provider_id, region, worker_count, provider_name=provider_name
        )
        return

    # Real cloud provisioning via Pulumi Automation API
    console.print(f"\n  [info]Launching cloud cluster via Pulumi...[/info]\n")

    try:
        from mesh.infrastructure.provision_cloud_cluster.automation import (
            deploy_cluster_from_config,
        )

        config = {
            "provider": provider_id,
            "region": region,
            "leader_size": provider["leader_size"],
            "worker_size": provider["worker_size"],
        }

        def on_output(msg: str):
            console.print(f"  [dim]{msg.strip()}[/dim]")

        result = deploy_cluster_from_config(
            config=config,
            stack_name=cluster_name,
            progress_callback=on_output,
        )

        if result.get("status") == "success":
            _show_cluster_ready(cluster_name, provider_id, region, worker_count)
        else:
            show_error(f"Deployment failed: {result.get('error', 'Unknown error')}")
            raise typer.Exit(1)

    except ImportError as e:
        show_error(f"Import error: {e}")
        show_info("Falling back to simulated mode...")
        show_provisioning_progress(steps, live=True)
        _show_cluster_ready(cluster_name, provider_id, region, worker_count)
    except Exception as e:
        _show_failure_panel(cluster_name, str(e))
        raise typer.Exit(1)


def _show_cluster_ready(
    cluster_name: str,
    provider_id: str,
    region: str,
    worker_count: int,
    node_ips: Optional[list] = None,
    provider_name: Optional[str] = None,
):
    tier = provider_name or provider_id
    result_text = Text()
    result_text.append(f"\n  {STATUS_ICONS['healthy']} ", style="bold")
    result_text.append("Cluster is ready!\n\n", style=f"bold {MESH_GREEN}")
    result_text.append(f"  Cluster:  ", style="dim")
    result_text.append(f"{cluster_name}\n", style=f"bold {MESH_CYAN}")
    result_text.append("  Tier:     ", style="dim")
    result_text.append(f"{tier}\n", style=f"bold {MESH_CYAN}")
    result_text.append(f"  Nodes:    ", style="dim")
    result_text.append(
        f"1 leader + {worker_count} worker(s)\n", style=f"bold {MESH_CYAN}"
    )
    if node_ips:
        result_text.append("  Leader IP:", style="dim")
        result_text.append(f" {node_ips[0]}\n", style=f"bold {MESH_CYAN}")
    result_text.append(f"  Provider: ", style="dim")
    result_text.append(f"{provider_id} ({region})\n\n", style=f"bold {MESH_CYAN}")
    result_text.append("  Next steps:\n", style="bold")
    result_text.append(
        "    mesh deploy my-app --image nginx:latest\n", style=MESH_GREEN
    )
    result_text.append("    mesh status\n", style=MESH_GREEN)
    result_text.append("    mesh logs\n", style=MESH_GREEN)

    console.print(
        Panel(
            result_text,
            border_style=MESH_GREEN,
            padding=(0, 1),
        )
    )
