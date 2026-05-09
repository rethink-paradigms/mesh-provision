"""Shared type definitions for Mesh MVP."""

from dataclasses import dataclass
from enum import Enum


class SnapshotStatus(str, Enum):
    CREATING = "creating"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORING = "restoring"


@dataclass
class SnapshotMetadata:
    id: str
    app_name: str
    created_at: str
    size_bytes: int
    status: SnapshotStatus
    volume_paths: list[str]
    snapshot_path: str

    def __post_init__(self):
        if not self.id:
            raise ValueError("id must be non-empty")
        if not self.app_name:
            raise ValueError("app_name must be non-empty")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be >= 0")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "app_name": self.app_name,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "status": self.status.value,
            "volume_paths": self.volume_paths,
            "snapshot_path": self.snapshot_path,
        }


SNAPSHOT_DIR = "/var/lib/mesh/snapshots/"
NOMAD_DATA_DIR = "/opt/nomad/data/alloc"
