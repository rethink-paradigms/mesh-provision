"""Mesh Snapshot Management - Application State Capture and Restore.

This module provides TDD-defined API for creating, restoring, listing, and
deleting filesystem snapshots of Nomad applications.

Public API Functions:
    create_snapshot: Capture application state as tar + JSON metadata
    restore_snapshot: Restore application state from snapshot
    list_snapshots: List all snapshots or filter by app_name
    delete_snapshot: Remove snapshot files (tar + JSON)

Storage Functions (merged from storage.py):
    ensure_snapshot_dir: Create snapshot directory if it doesn't exist
    save_snapshot: Write snapshot metadata JSON with atomic write
    load_snapshot_metadata: Read and parse a single snapshot metadata file
    list_all_metadata: Scan directory for all snapshot metadata files
    delete_snapshot_files: Remove snapshot tar and JSON files
    check_disk_space: Verify sufficient disk space for operations

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
import shutil
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone

import requests

from mesh.shared import SnapshotMetadata, SnapshotStatus, SNAPSHOT_DIR, NOMAD_DATA_DIR


# ---------------------------------------------------------------------------
# Storage helpers (atomic write, disk check, file management)
# ---------------------------------------------------------------------------

def ensure_snapshot_dir(snapshot_dir: str = SNAPSHOT_DIR) -> str:
    """Create snapshot directory if it doesn't exist.

    Args:
        snapshot_dir: Path to snapshot directory.

    Returns:
        The snapshot directory path.

    Raises:
        PermissionError: If directory cannot be created due to permissions.
    """
    try:
        os.makedirs(snapshot_dir, exist_ok=True)
    except PermissionError:
        raise
    return snapshot_dir


def save_snapshot(
    tar_path: str,
    metadata: SnapshotMetadata,
    snapshot_dir: str = SNAPSHOT_DIR,
) -> str:
    """Write snapshot metadata JSON file using atomic write.

    Writes to a temporary file first, then renames to the final path
    to avoid partial writes on crash.

    Args:
        tar_path: Path to the tar archive (not written here, just recorded).
        metadata: SnapshotMetadata to serialize.
        snapshot_dir: Directory to write metadata file into.

    Returns:
        Path to the written JSON metadata file.
    """
    ensure_snapshot_dir(snapshot_dir)
    json_path = f"{snapshot_dir}{metadata.id}.json"

    # Atomic write: write to temp file in same directory, then rename
    fd, tmp_path = tempfile.mkstemp(
        dir=snapshot_dir, prefix=".snap_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(metadata.to_dict(), f)
        os.replace(tmp_path, json_path)
    except BaseException:
        # Clean up temp file on any error
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return json_path


def load_snapshot_metadata(
    snapshot_id: str,
    snapshot_dir: str = SNAPSHOT_DIR,
) -> SnapshotMetadata | None:
    """Read and parse a single snapshot metadata file.

    Args:
        snapshot_id: Snapshot identifier.
        snapshot_dir: Directory containing metadata files.

    Returns:
        SnapshotMetadata if file exists and is valid, None otherwise.
    """
    json_path = f"{snapshot_dir}{snapshot_id}.json"

    if not os.path.isfile(json_path):
        return None

    try:
        with open(json_path) as f:
            data = json.load(f)
        data["status"] = SnapshotStatus(data["status"])
        return SnapshotMetadata(**data)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def list_all_metadata(
    snapshot_dir: str = SNAPSHOT_DIR,
) -> list[SnapshotMetadata]:
    """Scan snapshot directory for all metadata files.

    Reads all *.json files in the snapshot directory, parses them into
    SnapshotMetadata objects, and silently skips any corrupted files.

    Args:
        snapshot_dir: Directory to scan for metadata files.

    Returns:
        List of valid SnapshotMetadata objects.
    """
    try:
        files = os.listdir(snapshot_dir)
    except FileNotFoundError:
        return []

    results = []
    for filename in files:
        if not filename.endswith(".json"):
            continue
        json_path = os.path.join(snapshot_dir, filename)
        if not os.path.isfile(json_path):
            continue
        try:
            with open(json_path) as f:
                data = json.load(f)
            data["status"] = SnapshotStatus(data["status"])
            metadata = SnapshotMetadata(**data)
            results.append(metadata)
        except Exception:
            continue

    return results


def delete_snapshot_files(
    snapshot_id: str,
    snapshot_dir: str = SNAPSHOT_DIR,
) -> bool:
    """Remove snapshot tar archive and JSON metadata files.

    Args:
        snapshot_id: Snapshot identifier to delete.
        snapshot_dir: Directory containing snapshot files.

    Returns:
        True if deletion succeeded.

    Raises:
        FileNotFoundError: If snapshot files don't exist.
    """
    tar_path = f"{snapshot_dir}{snapshot_id}.tar.gz"
    json_path = f"{snapshot_dir}{snapshot_id}.json"

    if not os.path.exists(tar_path) or not os.path.exists(json_path):
        raise FileNotFoundError(f"Snapshot '{snapshot_id}' not found")

    os.remove(tar_path)
    os.remove(json_path)
    return True


def check_disk_space(
    required_bytes: int,
    snapshot_dir: str = SNAPSHOT_DIR,
) -> bool:
    """Check if snapshot directory has enough disk space.

    Args:
        required_bytes: Minimum bytes required.
        snapshot_dir: Directory to check (uses parent mount point).

    Returns:
        True if enough space available, False otherwise.
    """
    check_dir = snapshot_dir.rstrip(os.sep)
    if not os.path.exists(check_dir):
        check_dir = os.path.dirname(check_dir) or "."

    try:
        usage = shutil.disk_usage(check_dir)
        return usage.free >= required_bytes
    except (OSError, FileNotFoundError):
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_snapshot(app_name: str, nomad_addr: str) -> SnapshotMetadata:
    """Create a filesystem snapshot of a Nomad application.

    Captures application state by:
    1. Querying Nomad API for job allocations
    2. Discovering volume mount paths from allocation details
    3. Creating tar archive of volume data
    4. Writing JSON metadata file (atomic write)

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

    ensure_snapshot_dir(SNAPSHOT_DIR)

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

    # Atomic write: temp file + rename to avoid partial writes on crash
    save_snapshot(tar_path, metadata)

    return metadata


def restore_snapshot(app_name: str, snapshot_id: str, nomad_addr: str) -> bool:
    """Restore a Nomad application from a filesystem snapshot.

    Restores application state by:
    1. Reading snapshot metadata for volume paths
    2. Stopping running allocations for app_name
    3. Validating tar member paths against NOMAD_DATA_DIR (path traversal guard)
    4. Extracting tar archive to NOMAD_DATA_DIR
    5. Restarting allocations

    Args:
        app_name: Nomad job name to restore
        snapshot_id: Snapshot identifier to restore
        nomad_addr: Nomad server address

    Returns:
        True if restore succeeded

    Raises:
        ValueError: If a tar member would extract outside NOMAD_DATA_DIR
    """
    json_path = f"{SNAPSHOT_DIR}{snapshot_id}.json"
    with open(json_path) as f:
        metadata_dict = json.load(f)

    requests.post(f"{nomad_addr}/v1/job/{app_name}/stop", json={"Stop": True})

    tar_path = f"{SNAPSHOT_DIR}{snapshot_id}.tar.gz"
    extract_dir = os.path.realpath(NOMAD_DATA_DIR)
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = os.path.realpath(os.path.join(extract_dir, member.name))
            if not member_path.startswith(extract_dir):
                raise ValueError(f"Path traversal detected: {member.name}")
        tar.extractall(path=extract_dir)

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
    return delete_snapshot_files(snapshot_id, SNAPSHOT_DIR)
