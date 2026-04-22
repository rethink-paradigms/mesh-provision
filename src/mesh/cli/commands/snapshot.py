"""
mesh snapshot — Manage application volume snapshots.

Create, restore, list, and delete filesystem snapshots of
Nomad application volumes via the mesh snapshot engine.

Usage:
    mesh snapshot create <app>
    mesh snapshot restore <app> <snapshot-id>
    mesh snapshot list [--app <app>]
    mesh snapshot delete <snapshot-id>
"""

from typing import Optional

import typer
from rich.table import Table

from mesh.cli.ui.panels import console, show_success, show_error, show_info
from mesh.cli.ui.themes import MESH_GREEN, MESH_ORANGE, MESH_DIM, MESH_CYAN, MESH_PURPLE
from mesh.infrastructure.config.env import get_nomad_addr
from mesh.snapshots import create_snapshot, restore_snapshot, list_snapshots, delete_snapshot

snapshot_app = typer.Typer(
    name="snapshot",
    help="Manage application volume snapshots.",
    no_args_is_help=True,
)


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


@snapshot_app.command("create")
def create(
    app_name: str = typer.Argument(..., help="Application name to snapshot"),
):
    """
    Create a snapshot of an application's volumes.

    Captures application state as a tar archive with JSON metadata.

    Example:
        mesh snapshot create my-app
    """
    nomad_addr = get_nomad_addr()

    try:
        metadata = create_snapshot(app_name, nomad_addr)
    except ValueError as e:
        show_error(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        show_error(f"Failed to create snapshot: {e}")
        raise typer.Exit(code=1)

    show_success(f"Snapshot created for '{app_name}'")
    console.print(f"  [dim]ID:     [/dim][bold {MESH_CYAN}]{metadata.id}")
    console.print(f"  [dim]Size:   [/dim]{_format_size(metadata.size_bytes)}")
    console.print(f"  [dim]Status: [/dim][{MESH_GREEN}]{metadata.status.value}")
    console.print()


@snapshot_app.command("restore")
def restore(
    app_name: str = typer.Argument(..., help="Application name to restore"),
    snapshot_id: str = typer.Argument(..., help="Snapshot ID to restore"),
):
    """
    Restore an application from a snapshot.

    Stops running allocations, restores volume data, and restarts.

    Example:
        mesh snapshot restore my-app snap-20260422-abc123
    """
    nomad_addr = get_nomad_addr()

    try:
        restore_snapshot(app_name, snapshot_id, nomad_addr)
    except FileNotFoundError:
        show_error(f"Snapshot '{snapshot_id}' not found")
        raise typer.Exit(code=1)
    except Exception as e:
        show_error(f"Failed to restore snapshot: {e}")
        raise typer.Exit(code=1)

    show_success(f"Restored '{app_name}' from snapshot {snapshot_id}")
    console.print(f"  [dim]View status: [bold]mesh status[/bold][/dim]")
    console.print()


@snapshot_app.command("list")
def list_cmd(
    app: Optional[str] = typer.Option(None, "--app", "-a", help="Filter by application name"),
):
    """
    List available snapshots.

    Shows a table of all snapshots, optionally filtered by app.

    Example:
        mesh snapshot list
        mesh snapshot list --app my-app
    """
    snapshots = list_snapshots(app_name=app)

    if not snapshots:
        if app:
            show_info(f"No snapshots found for '{app}'")
        else:
            show_info("No snapshots found")
        console.print()
        return

    table = Table(
        title=f"[bold {MESH_PURPLE}]\U0001f4be Snapshots[/]",
        border_style=MESH_DIM,
        show_header=True,
        header_style=f"bold {MESH_CYAN}",
        padding=(0, 1),
    )
    table.add_column("ID", style=f"bold {MESH_CYAN}")
    table.add_column("App", style=f"bold {MESH_PURPLE}")
    table.add_column("Created", style="dim")
    table.add_column("Size", justify="right")
    table.add_column("Status", justify="center")

    for snap in snapshots:
        status_display = snap.status.value
        table.add_row(
            snap.id,
            snap.app_name,
            snap.created_at,
            _format_size(snap.size_bytes),
            status_display,
        )

    console.print()
    console.print(table)
    console.print()


@snapshot_app.command("delete")
def delete(
    snapshot_id: str = typer.Argument(..., help="Snapshot ID to delete"),
):
    """
    Delete a snapshot.

    Removes both the tar archive and JSON metadata.

    Example:
        mesh snapshot delete snap-20260422-abc123
    """
    try:
        delete_snapshot(snapshot_id)
    except FileNotFoundError:
        show_error(f"Snapshot '{snapshot_id}' not found")
        raise typer.Exit(code=1)
    except Exception as e:
        show_error(f"Failed to delete snapshot: {e}")
        raise typer.Exit(code=1)

    show_success(f"Snapshot '{snapshot_id}' deleted")
    console.print()
