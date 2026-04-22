"""Tests for shared type definitions in mesh.shared module."""

import pytest
from dataclasses import FrozenInstanceError

# Import the types we're testing
from mesh.shared import (
    SnapshotStatus,
    NodeRole,
    SnapshotMetadata,
    SNAPSHOT_DIR,
    NOMAD_DATA_DIR,
    MESH_CONFIG_DIR,
)


class TestSnapshotStatus:
    """Test SnapshotStatus enum."""

    def test_snapshot_status_has_all_values(self):
        """SnapshotStatus enum should have: CREATING, COMPLETED, FAILED, RESTORING."""
        assert hasattr(SnapshotStatus, "CREATING")
        assert hasattr(SnapshotStatus, "COMPLETED")
        assert hasattr(SnapshotStatus, "FAILED")
        assert hasattr(SnapshotStatus, "RESTORING")

    def test_snapshot_status_values_are_strings(self):
        """SnapshotStatus enum values should be string-based."""
        assert isinstance(SnapshotStatus.CREATING.value, str)
        assert isinstance(SnapshotStatus.COMPLETED.value, str)
        assert isinstance(SnapshotStatus.FAILED.value, str)
        assert isinstance(SnapshotStatus.RESTORING.value, str)


class TestNodeRole:
    """Test NodeRole enum."""

    def test_node_role_has_all_values(self):
        """NodeRole enum should have: SERVER, CLIENT."""
        assert hasattr(NodeRole, "SERVER")
        assert hasattr(NodeRole, "CLIENT")

    def test_node_role_values_are_strings(self):
        """NodeRole enum values should be string-based."""
        assert isinstance(NodeRole.SERVER.value, str)
        assert isinstance(NodeRole.CLIENT.value, str)


class TestSnapshotMetadata:
    """Test SnapshotMetadata dataclass."""

    def test_snapshot_metadata_all_fields_present(self):
        """SnapshotMetadata should have all required fields."""
        meta = SnapshotMetadata(
            id="snap-123",
            app_name="my-app",
            created_at="2024-01-01T00:00:00Z",
            size_bytes=1024,
            status=SnapshotStatus.COMPLETED,
            volume_paths=["/opt/nomad/data/alloc/123"],
            snapshot_path="/var/lib/mesh/snapshots/snap-123.tar.gz",
        )

        assert meta.id == "snap-123"
        assert meta.app_name == "my-app"
        assert meta.created_at == "2024-01-01T00:00:00Z"
        assert meta.size_bytes == 1024
        assert meta.status == SnapshotStatus.COMPLETED
        assert meta.volume_paths == ["/opt/nomad/data/alloc/123"]
        assert meta.snapshot_path == "/var/lib/mesh/snapshots/snap-123.tar.gz"

    def test_to_dict_returns_dict_representation(self):
        """SnapshotMetadata.to_dict() should return dict with all fields."""
        meta = SnapshotMetadata(
            id="snap-123",
            app_name="my-app",
            created_at="2024-01-01T00:00:00Z",
            size_bytes=1024,
            status=SnapshotStatus.COMPLETED,
            volume_paths=["/opt/nomad/data/alloc/123"],
            snapshot_path="/var/lib/mesh/snapshots/snap-123.tar.gz",
        )

        result = meta.to_dict()

        assert isinstance(result, dict)
        assert result["id"] == "snap-123"
        assert result["app_name"] == "my-app"
        assert result["created_at"] == "2024-01-01T00:00:00Z"
        assert result["size_bytes"] == 1024
        assert result["status"] == SnapshotStatus.COMPLETED.value
        assert result["volume_paths"] == ["/opt/nomad/data/alloc/123"]
        assert result["snapshot_path"] == "/var/lib/mesh/snapshots/snap-123.tar.gz"

    def test_to_dict_status_converts_to_string(self):
        """to_dict() should convert enum status to string value."""
        meta = SnapshotMetadata(
            id="snap-123",
            app_name="my-app",
            created_at="2024-01-01T00:00:00Z",
            size_bytes=1024,
            status=SnapshotStatus.CREATING,
            volume_paths=["/opt/nomad/data/alloc/123"],
            snapshot_path="/var/lib/mesh/snapshots/snap-123.tar.gz",
        )

        result = meta.to_dict()

        assert result["status"] == "creating"

    def test_validation_id_non_empty(self):
        """SnapshotMetadata should validate that id is non-empty."""
        with pytest.raises(ValueError, match="id must be non-empty"):
            SnapshotMetadata(
                id="",
                app_name="my-app",
                created_at="2024-01-01T00:00:00Z",
                size_bytes=1024,
                status=SnapshotStatus.COMPLETED,
                volume_paths=["/opt/nomad/data/alloc/123"],
                snapshot_path="/var/lib/mesh/snapshots/snap-123.tar.gz",
            )

    def test_validation_app_name_non_empty(self):
        """SnapshotMetadata should validate that app_name is non-empty."""
        with pytest.raises(ValueError, match="app_name must be non-empty"):
            SnapshotMetadata(
                id="snap-123",
                app_name="",
                created_at="2024-01-01T00:00:00Z",
                size_bytes=1024,
                status=SnapshotStatus.COMPLETED,
                volume_paths=["/opt/nomad/data/alloc/123"],
                snapshot_path="/var/lib/mesh/snapshots/snap-123.tar.gz",
            )

    def test_validation_size_bytes_non_negative(self):
        """SnapshotMetadata should validate that size_bytes is >= 0."""
        with pytest.raises(ValueError, match="size_bytes must be >= 0"):
            SnapshotMetadata(
                id="snap-123",
                app_name="my-app",
                created_at="2024-01-01T00:00:00Z",
                size_bytes=-1,
                status=SnapshotStatus.COMPLETED,
                volume_paths=["/opt/nomad/data/alloc/123"],
                snapshot_path="/var/lib/mesh/snapshots/snap-123.tar.gz",
            )

    def test_validation_size_bytes_zero_allowed(self):
        """SnapshotMetadata should allow size_bytes of 0."""
        meta = SnapshotMetadata(
            id="snap-123",
            app_name="my-app",
            created_at="2024-01-01T00:00:00Z",
            size_bytes=0,
            status=SnapshotStatus.COMPLETED,
            volume_paths=["/opt/nomad/data/alloc/123"],
            snapshot_path="/var/lib/mesh/snapshots/snap-123.tar.gz",
        )

        assert meta.size_bytes == 0


class TestConstants:
    """Test module-level constants."""

    def test_snapshot_dir_constant(self):
        """SNAPSHOT_DIR should be defined with correct value."""
        assert SNAPSHOT_DIR == "/var/lib/mesh/snapshots/"

    def test_nomad_data_dir_constant(self):
        """NOMAD_DATA_DIR should be defined with correct value."""
        assert NOMAD_DATA_DIR == "/opt/nomad/data/alloc"

    def test_mesh_config_dir_constant(self):
        """MESH_CONFIG_DIR should be defined with correct value."""
        assert MESH_CONFIG_DIR == "~/.mesh"
