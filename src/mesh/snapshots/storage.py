"""Snapshot Storage Backend — Local Filesystem.

Dedicated storage module for snapshot file operations. Handles reading,
writing, listing, and deleting snapshot metadata and archive files on
the local filesystem with proper edge case handling.

Functions:
    ensure_snapshot_dir: Create snapshot directory if it doesn't exist
    save_snapshot: Write snapshot metadata JSON with atomic write
    load_snapshot_metadata: Read and parse a single snapshot metadata file
    list_all_metadata: Scan directory for all snapshot metadata files
    delete_snapshot_files: Remove snapshot tar and JSON files
    check_disk_space: Verify sufficient disk space for operations
"""

import json
import os
import shutil
import tempfile

from mesh.shared import SNAPSHOT_DIR, SnapshotMetadata, SnapshotStatus


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
    # Ensure directory exists or use parent for disk check
    check_dir = snapshot_dir.rstrip(os.sep)
    if not os.path.exists(check_dir):
        check_dir = os.path.dirname(check_dir) or "."

    try:
        usage = shutil.disk_usage(check_dir)
        return usage.free >= required_bytes
    except (OSError, FileNotFoundError):
        return False
