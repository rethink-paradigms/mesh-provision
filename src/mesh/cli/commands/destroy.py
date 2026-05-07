"""
mesh destroy — Teardown a mesh cluster.
"""

from __future__ import annotations

from typing import Optional

import questionary
from questionary import Style as QStyle

from mesh.cli.ui.themes import MESH_RED
from mesh.cli.ui.panels import console, show_success, show_info, show_step

PROMPT_STYLE = QStyle(
    [
        ("qmark", "fg:#ff4444 bold"),
        ("question", "fg:#e0e0e0 bold"),
        ("answer", "fg:#ff4444 bold"),
    ]
)


def _run_destroy_json(
    cluster_name: str,
    api_key: Optional[str],
    demo: bool,
) -> None:
    """Handle destroy --output json."""
    from mesh.cli.commands.json_output import (
        build_demo_destroy_json,
        print_json_error,
        print_json_success,
        require_json_mode_args,
        to_brief_destroy_shape,
    )

    # Demo mode
    if demo:
        result = build_demo_destroy_json(cluster_name)
        print_json_success(result)
        return

    # Validate required args
    require_json_mode_args(api_key=api_key)

    # Use direct Libcloud destroy (single-token providers only per Guardrail G6)
    from mesh.infrastructure.provision_node.provision_direct import (
        destroy_resources_direct,
    )

    try:
        result = destroy_resources_direct(
            provider="digitalocean",
            api_key=api_key,  # type: ignore[arg-type]  # validated by require_json_mode_args
            region="",
            cluster_name=cluster_name,
        )
        transformed = to_brief_destroy_shape(result, cluster_name)
        transformed["demo"] = False
        print_json_success(transformed)
    except Exception as e:
        print_json_error(
            code="provision_failed",
            message=str(e),
            phase="destroy_resources",
        )


def run_destroy(
    cluster_name: str = "mesh-cluster",
    demo: bool = False,
    yes: bool = False,
    output: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Destroy a mesh cluster with confirmation."""
    if output == "json":
        _run_destroy_json(cluster_name=cluster_name, api_key=api_key, demo=demo)
        return

    console.print()
    console.print(f"  [bold {MESH_RED}]⚠️  Destroy cluster '{cluster_name}'?[/]")
    console.print(
        f"  [dim]This will terminate all nodes and stop all running apps.[/dim]"
    )
    console.print()

    if demo:
        show_info("Demo mode — skipping confirmation prompt.")
        console.print()
    elif yes:
        show_info("Skipping confirmation (--yes flag provided).")
        console.print()
    else:
        import sys

        if not sys.stdin.isatty():
            show_info(
                "Cancelled. Non-interactive terminal — use --yes to skip confirmation."
            )
            return

        confirm = questionary.confirm(
            "Are you sure? This cannot be undone.",
            default=False,
            style=PROMPT_STYLE,
        ).ask()

        if not confirm:
            show_info("Cancelled.")
            return

        console.print()

    if demo:
        import time

        show_step(1, 4, "Stopping all running apps...")
        time.sleep(0.5)
        show_step(2, 4, "Draining nodes...")
        time.sleep(0.5)
        show_step(3, 4, "Terminating nodes...")
        time.sleep(0.5)
        show_step(4, 4, "Cleaning up network...")
        time.sleep(0.3)
    else:
        import subprocess
        import shutil
        import os

        pulumi_cmd = shutil.which("pulumi")
        pulumi_project_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "infrastructure",
            "provision_cloud_cluster",
        )
        pulumi_project_dir = os.path.realpath(pulumi_project_dir)
        stack_exists = False
        if pulumi_cmd:
            result = subprocess.run(
                [pulumi_cmd, "stack", "ls", "--non-interactive"],
                capture_output=True,
                text=True,
                env={**os.environ, "PULUMI_SKIP_UPDATE_CHECK": "1"},
                cwd=pulumi_project_dir,
            )
            if result.returncode == 0 and cluster_name in result.stdout:
                stack_exists = True

        if stack_exists:
            from mesh.infrastructure.provision_cloud_cluster.automation import (
                destroy_cluster_stack,
            )

            try:
                show_step(1, 2, "Destroying cloud cluster stack...")
                destroy_cluster_stack(stack_name=cluster_name)
                show_step(2, 2, "Cleanup complete")
            except Exception as exc:
                from mesh.cli.ui.panels import show_error

                show_error(f"Failed to destroy cloud cluster: {exc}")
                return
        else:
            multipass_cmd = shutil.which("multipass")
            if multipass_cmd:
                show_step(1, 3, "Stopping Multipass VMs...")
                for suffix in ["leader", "worker-1", "worker-2", "worker-3"]:
                    name = f"{cluster_name}-{suffix}"
                    subprocess.run(
                        [multipass_cmd, "delete", name, "--purge"],
                        capture_output=True,
                    )
                show_step(2, 3, "Purging deleted VMs...")
                subprocess.run([multipass_cmd, "purge"], capture_output=True)
                show_step(3, 3, "Cleanup complete")
            else:
                from mesh.cli.ui.panels import show_error

                show_error("No Pulumi stack or Multipass found. Nothing to destroy.")
                return

    console.print()
    show_success(f"Cluster '{cluster_name}' destroyed")
    console.print()
