"""Tests for mesh snapshot CLI commands."""

from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from mesh.cli.main import app
from mesh.shared import SnapshotMetadata, SnapshotStatus

runner = CliRunner()

MOCK_METADATA = SnapshotMetadata(
    id="snap-20260422-abc123",
    app_name="my-app",
    created_at="2026-04-22T10:30:00+00:00",
    size_bytes=1048576,
    status=SnapshotStatus.COMPLETED,
    volume_paths=["/opt/nomad/data/alloc/vol1"],
    snapshot_path="/var/lib/mesh/snapshots/snap-20260422-abc123.tar.gz",
)


class TestSnapshotCreate:
    @patch("mesh.cli.commands.snapshot.create_snapshot", return_value=MOCK_METADATA)
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value="http://127.0.0.1:4646")
    def test_create_success(self, mock_addr, mock_create):
        result = runner.invoke(app, ["snapshot", "create", "my-app"])
        assert result.exit_code == 0
        assert "snap-20260422-abc123" in result.output
        assert "my-app" in result.output
        mock_create.assert_called_once_with("my-app", "http://127.0.0.1:4646")

    @patch("mesh.cli.commands.snapshot.create_snapshot", side_effect=ValueError("App 'no-app' not found"))
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value="http://127.0.0.1:4646")
    def test_create_app_not_found(self, mock_addr, mock_create):
        result = runner.invoke(app, ["snapshot", "create", "no-app"])
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("mesh.cli.commands.snapshot.create_snapshot", side_effect=ConnectionError("No cluster"))
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value="http://127.0.0.1:4646")
    def test_create_no_cluster(self, mock_addr, mock_create):
        result = runner.invoke(app, ["snapshot", "create", "my-app"])
        assert result.exit_code == 1
        assert "Failed to create snapshot" in result.output

    @patch("mesh.cli.commands.snapshot.create_snapshot", side_effect=ValueError("No running allocations for 'stopped-app'"))
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value="http://127.0.0.1:4646")
    def test_create_no_running_allocations(self, mock_addr, mock_create):
        result = runner.invoke(app, ["snapshot", "create", "stopped-app"])
        assert result.exit_code == 1
        assert "No running allocations" in result.output


class TestSnapshotRestore:
    @patch("mesh.cli.commands.snapshot.restore_snapshot", return_value=True)
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value="http://127.0.0.1:4646")
    def test_restore_success(self, mock_addr, mock_restore):
        result = runner.invoke(app, ["snapshot", "restore", "my-app", "snap-20260422-abc123"])
        assert result.exit_code == 0
        assert "Restored" in result.output
        assert "snap-20260422-abc123" in result.output
        mock_restore.assert_called_once_with("my-app", "snap-20260422-abc123", "http://127.0.0.1:4646")

    @patch("mesh.cli.commands.snapshot.restore_snapshot", side_effect=FileNotFoundError)
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value="http://127.0.0.1:4646")
    def test_restore_snapshot_not_found(self, mock_addr, mock_restore):
        result = runner.invoke(app, ["snapshot", "restore", "my-app", "snap-nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("mesh.cli.commands.snapshot.restore_snapshot", side_effect=Exception("Restore failed"))
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value="http://127.0.0.1:4646")
    def test_restore_failure(self, mock_addr, mock_restore):
        result = runner.invoke(app, ["snapshot", "restore", "my-app", "snap-20260422-abc123"])
        assert result.exit_code == 1
        assert "Failed to restore snapshot" in result.output


class TestSnapshotList:
    @patch("mesh.cli.commands.snapshot.list_snapshots", return_value=[MOCK_METADATA])
    def test_list_with_snapshots(self, mock_list):
        result = runner.invoke(app, ["snapshot", "list"])
        assert result.exit_code == 0
        assert "snap-20260422-abc123" in result.output
        assert "my-app" in result.output

    @patch("mesh.cli.commands.snapshot.list_snapshots", return_value=[])
    def test_list_empty(self, mock_list):
        result = runner.invoke(app, ["snapshot", "list"])
        assert result.exit_code == 0
        assert "No snapshots found" in result.output

    @patch("mesh.cli.commands.snapshot.list_snapshots", return_value=[])
    def test_list_empty_with_app_filter(self, mock_list):
        result = runner.invoke(app, ["snapshot", "list", "--app", "my-app"])
        assert result.exit_code == 0
        assert "No snapshots found for 'my-app'" in result.output
        mock_list.assert_called_once_with(app_name="my-app")

    @patch("mesh.cli.commands.snapshot.list_snapshots", return_value=[MOCK_METADATA])
    def test_list_with_app_filter(self, mock_list):
        result = runner.invoke(app, ["snapshot", "list", "--app", "my-app"])
        assert result.exit_code == 0
        assert "snap-20260422-abc123" in result.output
        mock_list.assert_called_once_with(app_name="my-app")


class TestSnapshotDelete:
    @patch("mesh.cli.commands.snapshot.delete_snapshot", return_value=True)
    def test_delete_success(self, mock_delete):
        result = runner.invoke(app, ["snapshot", "delete", "snap-20260422-abc123"])
        assert result.exit_code == 0
        assert "deleted" in result.output
        assert "snap-20260422-abc123" in result.output
        mock_delete.assert_called_once_with("snap-20260422-abc123")

    @patch("mesh.cli.commands.snapshot.delete_snapshot", side_effect=FileNotFoundError)
    def test_delete_not_found(self, mock_delete):
        result = runner.invoke(app, ["snapshot", "delete", "snap-nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("mesh.cli.commands.snapshot.delete_snapshot", side_effect=PermissionError("Access denied"))
    def test_delete_failure(self, mock_delete):
        result = runner.invoke(app, ["snapshot", "delete", "snap-20260422-abc123"])
        assert result.exit_code == 1
        assert "Failed to delete snapshot" in result.output
