"""
mesh status — Cluster health and app topology overview.

Displays a tree of nodes → apps with health indicators,
resource usage, and uptime.
"""

from rich.panel import Panel
from rich.text import Text

from mesh.cli.ui.themes import (
    MESH_GREEN,
    MESH_PURPLE,
    MESH_DIM,
    MESH_ORANGE,
    MESH_YELLOW,
)
from mesh.cli.ui.panels import (
    console,
    show_banner,
    show_cluster_status,
    show_error,
    show_resource_comparison,
    show_vision_roadmap,
    show_info,
)


# Mock data for demo mode
MOCK_NODES = [
    {
        "name": "mesh-leader",
        "role": "server",
        "status": "running",
        "ip": "100.64.0.1",
        "memory": "2 GB",
        "cpu": "2 vCPU",
    },
    {
        "name": "mesh-worker-1",
        "role": "client",
        "status": "running",
        "ip": "100.64.0.2",
        "memory": "2 GB",
        "cpu": "1 vCPU",
    },
    {
        "name": "mesh-worker-2",
        "role": "client",
        "status": "running",
        "ip": "100.64.0.3",
        "memory": "4 GB",
        "cpu": "2 vCPU",
    },
]

MOCK_APPS = [
    {
        "name": "web-api",
        "image": "ghcr.io/team/web-api:latest",
        "node": "mesh-worker-1",
        "status": "running",
        "memory": "512 MB",
        "uptime": "2h 34m",
    },
    {
        "name": "frontend",
        "image": "ghcr.io/team/frontend:latest",
        "node": "mesh-worker-1",
        "status": "running",
        "memory": "256 MB",
        "uptime": "1h 12m",
    },
    {
        "name": "worker",
        "image": "ghcr.io/team/worker:latest",
        "node": "mesh-worker-2",
        "status": "running",
        "memory": "384 MB",
        "uptime": "45m",
    },
    {
        "name": "redis",
        "image": "redis:7-alpine",
        "node": "mesh-worker-2",
        "status": "running",
        "memory": "128 MB",
        "uptime": "3h 01m",
    },
]


def run_status(
    demo: bool = False,
    show_comparison: bool = False,
    show_roadmap: bool = False,
):
    """
    Display cluster status with node topology and app overview.
    """
    show_banner()

    if demo:
        nodes = MOCK_NODES
        apps = MOCK_APPS
    else:
        nodes, apps = _get_live_status()
        if not nodes:
            show_error("[red]No Mesh cluster found.[/red]")
            console.print()
            show_info("Run [bold]mesh-install.sh[/bold] on a VM or set [bold]NOMAD_ADDR[/bold] environment variable.")
            console.print()
            return

        nodes = nodes or []
        apps = apps or []

    show_cluster_status(
        cluster_name="mesh-cluster",
        provider="multipass",
        region="local",
        nodes=nodes,
        apps=apps,
    )

    # Summary stats
    total_apps = len(apps)
    running = sum(1 for a in apps if a.get("status") == "running")
    total_nodes = len(nodes)

    stats = Text()
    stats.append(f"  Nodes: ", style="dim")
    stats.append(f"{total_nodes}", style=f"bold {MESH_ORANGE}")
    stats.append(f"  │  Apps: ", style="dim")
    stats.append(f"{running}/{total_apps} running", style=f"bold {MESH_PURPLE}")
    stats.append(f"  │  Control Plane: ", style="dim")
    stats.append(f"530 MB", style=f"bold {MESH_GREEN}")

    console.print(Panel(stats, border_style=MESH_DIM, padding=(0, 1)))
    console.print()

    if show_comparison:
        show_resource_comparison()

    if show_roadmap:
        show_vision_roadmap()


def _get_live_status():
    """Attempt to get live cluster status from Nomad + Consul."""
    try:
        import requests
        from mesh.infrastructure.config.env import get_nomad_addr

        nomad_addr = get_nomad_addr()

        # Get nodes
        nodes_resp = requests.get(f"{nomad_addr}/v1/nodes", timeout=3)
        nodes = []
        if nodes_resp.status_code == 200:
            for n in nodes_resp.json():
                role = "server" if n.get("NodeClass") == "server" else "client"
                nodes.append(
                    {
                        "name": n.get("Name", "unknown"),
                        "role": role,
                        "status": n.get("Status", "unknown"),
                        "ip": n.get("Address", "?"),
                        "memory": f"{n.get('NodeResources', {}).get('Memory', {}).get('MemoryMB', '?')} MB",
                        "cpu": f"{n.get('NodeResources', {}).get('Cpu', {}).get('CpuShares', '?')} MHz",
                    }
                )

        # Get jobs as apps
        jobs_resp = requests.get(f"{nomad_addr}/v1/jobs", timeout=3)
        apps = []
        if jobs_resp.status_code == 200:
            for j in jobs_resp.json():
                apps.append(
                    {
                        "name": j.get("Name", "unknown"),
                        "image": "—",
                        "node": "—",
                        "status": j.get("Status", "unknown"),
                        "memory": "—",
                        "uptime": "—",
                    }
                )

        return nodes, apps

    except Exception:
        return None, None
