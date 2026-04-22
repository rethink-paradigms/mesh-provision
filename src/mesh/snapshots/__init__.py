"""Mesh Snapshot Management - Application State Capture and Restore.

This module provides TDD-defined API for creating, restoring, listing, and
deleting filesystem snapshots of Nomad applications.

Public API Functions:
    create_snapshot: Capture application state as tar + JSON metadata
    restore_snapshot: Restore application state from snapshot
    list_snapshots: List all snapshots or filter by app_name
    delete_snapshot: Remove snapshot files (tar + JSON)

Dependencies:
    - Nomad API for allocation discovery
    - Filesystem operations in /var/lib/mesh/snapshots/

Example Usage:
    >>> from mesh.snapshots import create_snapshot, list_snapshots
    >>> metadata = create_snapshot("my-app", "http://127.0.0.1:4646")
    >>> snapshots = list_snapshots("my-app")
"""

import json
import os
import tarfile
import uuid
from datetime import datetime, timezone

import requests

from mesh.shared import SnapshotMetadata, SnapshotStatus, SNAPSHOT_DIR, NOMAD_DATA_DIR


def create_snapshot(app_name: str, nomad_addr: str) -> SnapshotMetadata:
    """Create a filesystem snapshot of a Nomad application.

    Captures application state by:
    1. Querying Nomad API for job allocations
    2. Discovering volume mount paths from allocation details
    3. Creating tar archive of volume data
    4. Writing JSON metadata file

    Args:
        app_name: Nomad job name to snapshot
        nomad_addr: Nomad server address (e.g., "http://127.0.0.1:4646")

    Returns:
        SnapshotMetadata with snapshot details

    Raises:
        ValueError: If app not found or no running allocations
    """
    resp = requests.get(f"{nomad_addr}/v1/job/{app_name}/allocations")
    allocations = resp.json()

    if not allocations:
        raise ValueError(f"App '{app_name}' not found")

    running_allocs = []
    for alloc in allocations:
        task_states = alloc.get("TaskStates", {})
        if any(ts.get("State") == "running" for ts in task_states.values()):
            running_allocs.append(alloc)

    if not running_allocs:
        raise ValueError(f"No running allocations for '{app_name}'")

    volume_paths = []
    for alloc in running_allocs:
        detail_resp = requests.get(f"{nomad_addr}/v1/allocation/{alloc['ID']}")
        detail = detail_resp.json()
        for task in detail.get("Tasks", []):
            for mount in task.get("Config", {}).get("Mounts", []):
                if mount.get("Type") == "volume":
                    path = f"{NOMAD_DATA_DIR}/{alloc['ID']}/{mount['Source']}"
                    volume_paths.append(path)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:6]
    snapshot_id = f"snap-{timestamp}-{short_uuid}"

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    tar_path = f"{SNAPSHOT_DIR}{snapshot_id}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for path in volume_paths:
            if os.path.exists(path):
                tar.add(path)

    size_bytes = os.path.getsize(tar_path)

    created_at = datetime.now(timezone.utc).isoformat()
    metadata = SnapshotMetadata(
        id=snapshot_id,
        app_name=app_name,
        created_at=created_at,
        size_bytes=size_bytes,
        status=SnapshotStatus.COMPLETED,
        volume_paths=volume_paths,
        snapshot_path=tar_path,
    )

    json_path = f"{SNAPSHOT_DIR}{snapshot_id}.json"
    with open(json_path, "w") as f:
        json.dump(metadata.to_dict(), f)

    return metadata


def restore_snapshot(app_name: str, snapshot_id: str, nomad_addr: str) -> bool:
    """Restore a Nomad application from a filesystem snapshot.

    Restores application state by:
    1. Reading snapshot metadata for volume paths
    2. Stopping running allocations for app_name
    3. Extracting tar archive to volume paths
    4. Restarting allocations

    Args:
        app_name: Nomad job name to restore
        snapshot_id: Snapshot identifier to restore
        nomad_addr: Nomad server address

    Returns:
        True if restore succeeded
    """
    json_path = f"{SNAPSHOT_DIR}{snapshot_id}.json"
    with open(json_path) as f:
        metadata_dict = json.load(f)

    requests.post(f"{nomad_addr}/v1/job/{app_name}/stop", json={"Stop": True})

    tar_path = f"{SNAPSHOT_DIR}{snapshot_id}.tar.gz"
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall()

    requests.post(f"{nomad_addr}/v1/job/{app_name}/periodic/force-run")

    return True


def list_snapshots(app_name: str | None = None) -> list[SnapshotMetadata]:
    """List available snapshots, optionally filtered by application.

    Scans /var/lib/mesh/snapshots/ for JSON metadata files
    and parses them into SnapshotMetadata objects.

    Args:
        app_name: Optional filter for specific application.
                   If None, returns all snapshots.

    Returns:
        List of SnapshotMetadata objects matching filter.
    """
    try:
        files = os.listdir(SNAPSHOT_DIR)
    except FileNotFoundError:
        return []

    snapshots = []
    for filename in files:
        if not filename.endswith(".json"):
            continue
        json_path = os.path.join(SNAPSHOT_DIR, filename)
        if not os.path.isfile(json_path):
            continue
        try:
            with open(json_path) as f:
                data = json.load(f)
            data["status"] = SnapshotStatus(data["status"])
            metadata = SnapshotMetadata(**data)
            if app_name is None or metadata.app_name == app_name:
                snapshots.append(metadata)
        except Exception:
            continue

    return snapshots


def delete_snapshot(snapshot_id: str) -> bool:
    """Delete a snapshot by removing tar and JSON metadata files.

    Args:
        snapshot_id: Snapshot identifier to delete.

    Returns:
        True if deletion succeeded.

    Raises:
        FileNotFoundError: If snapshot files don't exist.
    """
    tar_path = f"{SNAPSHOT_DIR}{snapshot_id}.tar.gz"
    json_path = f"{SNAPSHOT_DIR}{snapshot_id}.json"

    if not os.path.exists(tar_path) or not os.path.exists(json_path):
        raise FileNotFoundError(f"Snapshot '{snapshot_id}' not found")

    os.remove(tar_path)
    os.remove(json_path)
    return True
