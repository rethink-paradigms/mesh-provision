"""E2E MVP golden-path tests — deploy → snapshot → restore → verify.

Exercises the complete MVP workflow with mocked Nomad API:
  1. Create snapshot of running app
  2. List / restore / delete snapshots
  3. Error cases (nonexistent app, missing snapshot)
  4. CLI integration via Typer CliRunner
  5. JSON metadata round-trip

All infrastructure (Nomad, filesystem) is mocked — no running cluster required.
"""

import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest
from typer.testing import CliRunner

from mesh.cli.commands.snapshot import snapshot_app
from mesh.shared import SNAPSHOT_DIR, NOMAD_DATA_DIR, SnapshotMetadata, SnapshotStatus
from mesh.snapshots import (
    create_snapshot,
    restore_snapshot,
    list_snapshots,
    delete_snapshot,
)

pytestmark = pytest.mark.e2e

NOMAD_ADDR = "http://127.0.0.1:4646"
APP_NAME = "test-app"


def _alloc_list_response():
    return [
        {
            "ID": "alloc-abc123",
            "JobID": APP_NAME,
            "TaskStates": {"web": {"State": "running"}},
        }
    ]


def _alloc_detail_response():
    return {
        "ID": "alloc-abc123",
        "Tasks": [
            {
                "Name": "web",
                "Config": {
                    "Mounts": [
                        {"Type": "volume", "Source": "data"},
                    ]
                },
            }
        ],
    }


def _mock_get_factory(alloc_list, alloc_detail):
    """Return a side_effect callable that routes requests.get by URL."""
    def _factory(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "/allocations" in url:
            resp.json.return_value = alloc_list
        elif "/allocation/" in url:
            resp.json.return_value = alloc_detail
        else:
            resp.json.return_value = {}
        return resp
    return _factory


def _patch_snapshot_dir(tmp_path):
    """Return a context manager that patches SNAPSHOT_DIR to tmp_path."""
    snap_dir = str(tmp_path) + "/"
    return patch("mesh.snapshots.SNAPSHOT_DIR", snap_dir)


# ---------------------------------------------------------------------------
# TestMVPGoldenPath — full create → list → restore → delete flow
# ---------------------------------------------------------------------------

class TestMVPGoldenPath:
    """Full MVP flow with mocked Nomad API."""

    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", new_callable=MagicMock)
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_full_create_list_restore_delete(
        self,
        mock_get,
        mock_uuid,
        mock_makedirs,
        mock_tar,
        mock_exists,
        mock_getsize,
        tmp_path,
    ):
        mock_get.side_effect = _mock_get_factory(
            _alloc_list_response(), _alloc_detail_response()
        )
        mock_uuid.return_value = MagicMock(hex="abcdef1234567890")

        with _patch_snapshot_dir(tmp_path), \
             patch("builtins.open", mock_open()):
            # Step 1: Create snapshot
            metadata = create_snapshot(APP_NAME, NOMAD_ADDR)
            assert metadata.status == SnapshotStatus.COMPLETED
            assert metadata.app_name == APP_NAME
            assert metadata.id.startswith("snap-")
            snapshot_id = metadata.id

            # Step 2: List snapshots — verify it appears
            with patch("builtins.open", mock_open(
                read_data=json.dumps(metadata.to_dict())
            )):
                with patch("os.listdir", return_value=[f"{snapshot_id}.json"]):
                    with patch("os.path.isfile", return_value=True):
                        snaps = list_snapshots(APP_NAME)
            assert len(snaps) == 1
            assert snaps[0].id == snapshot_id

        # Step 3: Restore snapshot
        with _patch_snapshot_dir(tmp_path), \
             patch("mesh.snapshots.requests.post") as mock_post, \
             patch("builtins.open", mock_open(
                 read_data=json.dumps(metadata.to_dict())
             )), \
             patch("mesh.snapshots.tarfile.open"):
            result = restore_snapshot(APP_NAME, snapshot_id, NOMAD_ADDR)
            assert result is True
            assert mock_post.call_count == 2

        # Step 4: Delete snapshot
        with _patch_snapshot_dir(tmp_path), \
             patch("mesh.snapshots.os.path.exists", return_value=True), \
             patch("mesh.snapshots.os.remove") as mock_remove:
            deleted = delete_snapshot(snapshot_id)
            assert deleted is True
            assert mock_remove.call_count == 2


# ---------------------------------------------------------------------------
# TestMVPSnapshotErrorCases
# ---------------------------------------------------------------------------

class TestMVPSnapshotErrorCases:
    """Error handling for invalid snapshot operations."""

    @patch("mesh.snapshots.requests.get")
    def test_snapshot_nonexistent_app_raises_valueerror(self, mock_get):
        mock_get.return_value = MagicMock(json=lambda: [])
        with pytest.raises(ValueError, match="not found"):
            create_snapshot("nonexistent-app", NOMAD_ADDR)

    @patch("mesh.snapshots.requests.get")
    def test_snapshot_no_running_allocations_raises_valueerror(self, mock_get):
        allocs = [
            {"ID": "alloc-dead", "TaskStates": {"web": {"State": "dead"}}}
        ]
        mock_get.return_value = MagicMock(json=lambda: allocs)
        with pytest.raises(ValueError, match="No running allocations"):
            create_snapshot(APP_NAME, NOMAD_ADDR)

    def test_restore_nonexistent_snapshot_raises_filenotfound(self, tmp_path):
        with _patch_snapshot_dir(tmp_path):
            with pytest.raises((FileNotFoundError, OSError)):
                restore_snapshot(APP_NAME, "snap-nonexistent", NOMAD_ADDR)

    def test_delete_nonexistent_snapshot_raises_filenotfound(self, tmp_path):
        with _patch_snapshot_dir(tmp_path):
            with pytest.raises(FileNotFoundError):
                delete_snapshot("snap-nonexistent")

    def test_list_snapshots_when_none_exist_returns_empty(self, tmp_path):
        with _patch_snapshot_dir(tmp_path):
            snaps = list_snapshots()
        assert snaps == []


# ---------------------------------------------------------------------------
# TestMVPSnapshotCLIIntegration — Typer CliRunner tests
# ---------------------------------------------------------------------------

class TestMVPSnapshotCLIIntegration:
    """CLI command tests via Typer CliRunner with mocked engine."""

    runner = CliRunner()

    @patch("mesh.cli.commands.snapshot.create_snapshot")
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value=NOMAD_ADDR)
    def test_cli_create_snapshot(self, mock_addr, mock_create, tmp_path):
        mock_create.return_value = SnapshotMetadata(
            id="snap-20260422-abcdef",
            app_name=APP_NAME,
            created_at="2026-04-22T12:00:00+00:00",
            size_bytes=2048,
            status=SnapshotStatus.COMPLETED,
            volume_paths=["/opt/nomad/data/alloc/alloc-abc123/data"],
            snapshot_path=f"{tmp_path}/snap-20260422-abcdef.tar.gz",
        )
        result = self.runner.invoke(snapshot_app, ["create", APP_NAME])
        assert result.exit_code == 0
        assert "snap-20260422-abcdef" in result.output
        mock_create.assert_called_once_with(APP_NAME, NOMAD_ADDR)

    @patch("mesh.cli.commands.snapshot.list_snapshots")
    def test_cli_list_snapshots(self, mock_list):
        mock_list.return_value = [
            SnapshotMetadata(
                id="snap-20260422-abcdef",
                app_name=APP_NAME,
                created_at="2026-04-22T12:00:00+00:00",
                size_bytes=2048,
                status=SnapshotStatus.COMPLETED,
                volume_paths=["/opt/nomad/data/alloc/alloc-abc123/data"],
                snapshot_path="/var/lib/mesh/snapshots/snap-20260422-abcdef.tar.gz",
            )
        ]
        result = self.runner.invoke(snapshot_app, ["list"])
        assert result.exit_code == 0
        assert "snap-20260422-abcdef" in result.output
        assert APP_NAME in result.output

    @patch("mesh.cli.commands.snapshot.list_snapshots")
    def test_cli_list_snapshots_empty(self, mock_list):
        mock_list.return_value = []
        result = self.runner.invoke(snapshot_app, ["list"])
        assert result.exit_code == 0
        assert "No snapshots found" in result.output

    @patch("mesh.cli.commands.snapshot.restore_snapshot")
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value=NOMAD_ADDR)
    def test_cli_restore_snapshot(self, mock_addr, mock_restore):
        mock_restore.return_value = True
        snap_id = "snap-20260422-abcdef"
        result = self.runner.invoke(
            snapshot_app, ["restore", APP_NAME, snap_id]
        )
        assert result.exit_code == 0
        assert "Restored" in result.output
        mock_restore.assert_called_once_with(APP_NAME, snap_id, NOMAD_ADDR)

    @patch("mesh.cli.commands.snapshot.restore_snapshot")
    @patch("mesh.cli.commands.snapshot.get_nomad_addr", return_value=NOMAD_ADDR)
    def test_cli_restore_nonexistent_shows_error(self, mock_addr, mock_restore):
        mock_restore.side_effect = FileNotFoundError("not found")
        result = self.runner.invoke(
            snapshot_app, ["restore", APP_NAME, "snap-nonexistent"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("mesh.cli.commands.snapshot.delete_snapshot")
    def test_cli_delete_snapshot(self, mock_delete):
        snap_id = "snap-20260422-abcdef"
        mock_delete.return_value = True
        result = self.runner.invoke(snapshot_app, ["delete", snap_id])
        assert result.exit_code == 0
        assert "deleted" in result.output
        mock_delete.assert_called_once_with(snap_id)

    @patch("mesh.cli.commands.snapshot.delete_snapshot")
    def test_cli_delete_nonexistent_shows_error(self, mock_delete):
        mock_delete.side_effect = FileNotFoundError("not found")
        result = self.runner.invoke(snapshot_app, ["delete", "snap-nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output


# ---------------------------------------------------------------------------
# TestMVPSnapshotRoundTrip — metadata JSON persistence
# ---------------------------------------------------------------------------

class TestMVPSnapshotRoundTrip:
    """Verify JSON metadata round-trips through the snapshot engine."""

    @patch("mesh.snapshots.os.path.getsize", return_value=4096)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", new_callable=MagicMock)
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_metadata_round_trip(
        self,
        mock_get,
        mock_uuid,
        mock_makedirs,
        mock_tar,
        mock_exists,
        mock_getsize,
        tmp_path,
    ):
        mock_get.side_effect = _mock_get_factory(
            _alloc_list_response(), _alloc_detail_response()
        )
        mock_uuid.return_value = MagicMock(hex="aabbccddeeff0011")

        snap_dir = tmp_path / "snaps"
        snap_dir.mkdir()

        with _patch_snapshot_dir(tmp_path / "snaps"):
            # Write actual JSON to tmp filesystem
            metadata = create_snapshot(APP_NAME, NOMAD_ADDR)

            json_name = f"{metadata.id}.json"
            json_path = snap_dir / json_name

            assert json_path.exists(), f"Metadata file {json_name} not created"

            with open(json_path) as f:
                data = json.load(f)

            assert data["id"] == metadata.id
            assert data["app_name"] == APP_NAME
            assert data["status"] == SnapshotStatus.COMPLETED.value
            assert data["size_bytes"] == 4096

    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", new_callable=MagicMock)
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_list_filtered_by_app_name(
        self,
        mock_get,
        mock_uuid,
        mock_makedirs,
        mock_tar,
        mock_exists,
        mock_getsize,
        tmp_path,
    ):
        mock_get.side_effect = _mock_get_factory(
            _alloc_list_response(), _alloc_detail_response()
        )
        mock_uuid.return_value = MagicMock(hex="1111111111111111")

        snap_dir = tmp_path / "snaps"
        snap_dir.mkdir()

        with _patch_snapshot_dir(tmp_path / "snaps"):
            metadata = create_snapshot(APP_NAME, NOMAD_ADDR)

            # List with matching filter
            snaps = list_snapshots(APP_NAME)
            assert len(snaps) == 1
            assert snaps[0].app_name == APP_NAME

            # List with non-matching filter
            snaps_other = list_snapshots("other-app")
            assert len(snaps_other) == 0

    @patch("mesh.snapshots.os.path.getsize", return_value=512)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", new_callable=MagicMock)
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_list_returns_all_without_filter(
        self,
        mock_get,
        mock_uuid,
        mock_makedirs,
        mock_tar,
        mock_exists,
        mock_getsize,
        tmp_path,
    ):
        mock_get.side_effect = _mock_get_factory(
            _alloc_list_response(), _alloc_detail_response()
        )
        mock_uuid.return_value = MagicMock(hex="2222222222222222")

        snap_dir = tmp_path / "snaps"
        snap_dir.mkdir()

        with _patch_snapshot_dir(tmp_path / "snaps"):
            create_snapshot(APP_NAME, NOMAD_ADDR)

            all_snaps = list_snapshots()
            assert len(all_snaps) >= 1
