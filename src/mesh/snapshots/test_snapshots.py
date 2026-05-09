"""Tests for Feature: Application Snapshot Management (GREEN Phase)

Tests verify the implemented snapshot engine: create, restore, list, delete.
Also tests all storage helpers merged from storage.py and path traversal protection.
"""

import io
import json
import os
import tarfile
import threading

import pytest
from unittest.mock import patch, MagicMock, call

from mesh.shared import SnapshotMetadata, SnapshotStatus
from mesh.snapshots import (
    check_disk_space,
    delete_snapshot_files,
    ensure_snapshot_dir,
    list_all_metadata,
    load_snapshot_metadata,
    save_snapshot,
)


@pytest.fixture
def nomad_allocations_response():
    """Mock Nomad /v1/job/{app_name}/allocations API response."""
    return [
        {
            "ID": "abc123",
            "JobID": "test-app",
            "TaskStates": {
                "web": {
                    "State": "running",
                }
            },
        }
    ]


@pytest.fixture
def nomad_allocation_details():
    """Mock Nomad /v1/allocation/{alloc_id} API response with volume mounts."""
    return {
        "ID": "abc123",
        "JobID": "test-app",
        "Tasks": [
            {
                "Name": "web",
                "Config": {
                    "Mounts": [
                        {
                            "Type": "volume",
                            "Destination": "/app/data",
                            "Source": "data",
                        }
                    ]
                },
            }
        ],
    }


@pytest.fixture
def snapshot_metadata():
    """Sample SnapshotMetadata object for testing."""
    return SnapshotMetadata(
        id="snap-20240422-001",
        app_name="test-app",
        created_at="2024-04-22T12:00:00Z",
        size_bytes=10485760,
        status=SnapshotStatus.COMPLETED,
        volume_paths=["/opt/nomad/data/alloc/abc123/data"],
        snapshot_path="/var/lib/mesh/snapshots/snap-20240422-001.tar.gz",
    )


def _mock_get_factory(allocations, details):
    """Build a requests.get side_effect that returns allocations list or detail."""
    def side_effect(url, **kwargs):
        resp = MagicMock()
        if "/allocation/" in url and "/allocations" not in url:
            resp.json.return_value = details
        else:
            resp.json.return_value = allocations
        return resp
    return side_effect


def _make_metadata(
    snapshot_id: str = "snap-20240422-test1",
    app_name: str = "test-app",
    status: SnapshotStatus = SnapshotStatus.COMPLETED,
) -> SnapshotMetadata:
    return SnapshotMetadata(
        id=snapshot_id,
        app_name=app_name,
        created_at="2024-04-22T12:00:00Z",
        size_bytes=1024,
        status=status,
        volume_paths=["/opt/nomad/data/alloc/abc123/data"],
        snapshot_path=f"/var/lib/mesh/snapshots/{snapshot_id}.tar.gz",
    )


def _write_json_file(directory: str, filename: str, data: dict) -> str:
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# Public API tests
# ---------------------------------------------------------------------------

class TestCreateSnapshot:
    """Test suite for create_snapshot function."""

    @patch("mesh.snapshots.save_snapshot")
    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_does_not_raise(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_save,
        nomad_allocations_response, nomad_allocation_details,
    ):
        """Test_CreateSnapshot_Does_Not_Raise: Function executes without error."""
        from mesh.snapshots import create_snapshot

        mock_get.side_effect = _mock_get_factory(
            nomad_allocations_response, nomad_allocation_details
        )
        mock_uuid.return_value = MagicMock(hex="abc123def456")

        result = create_snapshot("test-app", "http://127.0.0.1:4646")
        assert isinstance(result, SnapshotMetadata)
        assert result.app_name == "test-app"
        assert result.status == SnapshotStatus.COMPLETED

    @patch("mesh.snapshots.save_snapshot")
    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_queries_nomad_allocations(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_save,
        nomad_allocations_response, nomad_allocation_details,
    ):
        """Test_CreateSnapshot_Queries_Nomad_Allocations: Verify Nomad API call."""
        from mesh.snapshots import create_snapshot

        mock_get.side_effect = _mock_get_factory(
            nomad_allocations_response, nomad_allocation_details
        )
        mock_uuid.return_value = MagicMock(hex="abc123def456")

        create_snapshot("test-app", "http://127.0.0.1:4646")

        mock_get.assert_any_call("http://127.0.0.1:4646/v1/job/test-app/allocations")

    @patch("mesh.snapshots.save_snapshot")
    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open")
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_creates_tar_archive(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_save,
        nomad_allocations_response, nomad_allocation_details,
    ):
        """Test_CreateSnapshot_Creates_Tar_Archive: Verify tarfile.open called."""
        from mesh.snapshots import create_snapshot

        mock_get.side_effect = _mock_get_factory(
            nomad_allocations_response, nomad_allocation_details
        )
        mock_uuid.return_value = MagicMock(hex="abc123def456")

        create_snapshot("test-app", "http://127.0.0.1:4646")

        mock_tar.assert_called_once()
        call_args = mock_tar.call_args[0]
        assert call_args[0].endswith(".tar.gz")
        assert call_args[1] == "w:gz"

    @patch("mesh.snapshots.save_snapshot")
    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_writes_metadata_json(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_save,
        nomad_allocations_response, nomad_allocation_details,
    ):
        """Test_CreateSnapshot_Writes_Metadata_Json: Verify save_snapshot called with correct metadata."""
        from mesh.snapshots import create_snapshot

        mock_get.side_effect = _mock_get_factory(
            nomad_allocations_response, nomad_allocation_details
        )
        mock_uuid.return_value = MagicMock(hex="abc123def456")

        create_snapshot("test-app", "http://127.0.0.1:4646")

        assert mock_save.called
        metadata_arg = mock_save.call_args[0][1]
        assert metadata_arg.app_name == "test-app"
        assert metadata_arg.status == SnapshotStatus.COMPLETED

    @patch("mesh.snapshots.save_snapshot")
    @patch("mesh.snapshots.os.path.getsize", return_value=10485760)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_returns_snapshot_metadata(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_save,
        nomad_allocations_response, nomad_allocation_details,
    ):
        """Test_CreateSnapshot_Returns_SnapshotMetadata: Verify return type."""
        from mesh.snapshots import create_snapshot

        mock_get.side_effect = _mock_get_factory(
            nomad_allocations_response, nomad_allocation_details
        )
        mock_uuid.return_value = MagicMock(hex="abc123def456")

        result = create_snapshot("test-app", "http://127.0.0.1:4646")

        assert isinstance(result, SnapshotMetadata)
        assert result.app_name == "test-app"
        assert result.status == SnapshotStatus.COMPLETED
        assert result.size_bytes == 10485760
        assert result.snapshot_path.endswith(".tar.gz")
        assert len(result.volume_paths) > 0


class TestRestoreSnapshot:
    """Test suite for restore_snapshot function."""

    @patch("mesh.snapshots.requests.post")
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.json.load")
    @patch("builtins.open", new_callable=MagicMock)
    def test_restore_snapshot_does_not_raise(
        self, mock_file, mock_json_load, mock_tar, mock_post,
    ):
        """Test_RestoreSnapshot_Does_Not_Raise: Function executes without error."""
        from mesh.snapshots import restore_snapshot

        mock_json_load.return_value = {"volume_paths": ["/app/data"]}

        result = restore_snapshot("test-app", "snap-001", "http://127.0.0.1:4646")
        assert result is True

    @patch("mesh.snapshots.requests.post")
    @patch("mesh.snapshots.tarfile.open")
    @patch("mesh.snapshots.json.load")
    @patch("builtins.open", new_callable=MagicMock)
    def test_restore_snapshot_extracts_tar(
        self, mock_file, mock_json_load, mock_tar, mock_post,
    ):
        """Test_RestoreSnapshot_Extracts_Tar: Verify tarfile.open for extraction."""
        from mesh.snapshots import restore_snapshot

        mock_json_load.return_value = {"volume_paths": ["/app/data"]}
        mock_tar_handle = MagicMock()
        mock_tar.return_value.__enter__ = MagicMock(return_value=mock_tar_handle)
        mock_tar.return_value.__exit__ = MagicMock(return_value=False)

        restore_snapshot("test-app", "snap-001", "http://127.0.0.1:4646")

        mock_tar.assert_called_once()
        call_args = mock_tar.call_args[0]
        assert "snap-001.tar.gz" in call_args[0]
        assert call_args[1] == "r:gz"

    @patch("mesh.snapshots.requests.post")
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.json.load")
    @patch("builtins.open", new_callable=MagicMock)
    def test_restore_snapshot_stops_allocations(
        self, mock_file, mock_json_load, mock_tar, mock_post,
    ):
        """Test_RestoreSnapshot_Stops_Allocations: Verify stop POST request."""
        from mesh.snapshots import restore_snapshot

        mock_json_load.return_value = {"volume_paths": ["/app/data"]}

        restore_snapshot("test-app", "snap-001", "http://127.0.0.1:4646")

        stop_call = call(
            "http://127.0.0.1:4646/v1/job/test-app/stop",
            json={"Stop": True},
        )
        assert stop_call in mock_post.call_args_list

    @patch("mesh.snapshots.requests.post")
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.json.load")
    @patch("builtins.open", new_callable=MagicMock)
    def test_restore_snapshot_restarts_allocations(
        self, mock_file, mock_json_load, mock_tar, mock_post,
    ):
        """Test_RestoreSnapshot_Restarts_Allocations: Verify restart POST request."""
        from mesh.snapshots import restore_snapshot

        mock_json_load.return_value = {"volume_paths": ["/app/data"]}

        restore_snapshot("test-app", "snap-001", "http://127.0.0.1:4646")

        restart_call = call(
            "http://127.0.0.1:4646/v1/job/test-app/periodic/force-run",
        )
        assert restart_call in mock_post.call_args_list

    @patch("mesh.snapshots.requests.post")
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.json.load")
    @patch("builtins.open", new_callable=MagicMock)
    def test_restore_snapshot_returns_true_on_success(
        self, mock_file, mock_json_load, mock_tar, mock_post,
    ):
        """Test_RestoreSnapshot_Returns_True_On_Success: Verify return value."""
        from mesh.snapshots import restore_snapshot

        mock_json_load.return_value = {"volume_paths": ["/app/data"]}

        result = restore_snapshot("test-app", "snap-001", "http://127.0.0.1:4646")
        assert result is True


class TestListSnapshots:
    """Test suite for list_snapshots function."""

    @patch("mesh.snapshots.json.load")
    @patch("mesh.snapshots.os.path.isfile", return_value=True)
    @patch("mesh.snapshots.os.listdir")
    @patch("builtins.open", new_callable=MagicMock)
    def test_list_snapshots_does_not_raise(
        self, mock_file, mock_listdir, mock_isfile, mock_json_load,
    ):
        """Test_ListSnapshots_Does_Not_Raise: Function executes without error."""
        from mesh.snapshots import list_snapshots

        mock_listdir.return_value = []
        result = list_snapshots()
        assert isinstance(result, list)

    @patch("mesh.snapshots.json.load")
    @patch("mesh.snapshots.os.path.isfile", return_value=True)
    @patch("mesh.snapshots.os.listdir")
    @patch("builtins.open", new_callable=MagicMock)
    def test_list_snapshots_scans_snapshot_directory(
        self, mock_file, mock_listdir, mock_isfile, mock_json_load,
    ):
        """Test_ListSnapshots_Scans_Snapshot_Directory: Verify directory scan."""
        from mesh.snapshots import list_snapshots

        mock_listdir.return_value = ["snap-001.json", "snap-002.json", "other.txt"]
        mock_json_load.return_value = {
            "id": "snap-001",
            "app_name": "test-app",
            "created_at": "2024-04-22T12:00:00Z",
            "size_bytes": 1024,
            "status": "completed",
            "volume_paths": ["/app/data"],
            "snapshot_path": "/var/lib/mesh/snapshots/snap-001.tar.gz",
        }

        result = list_snapshots()

        mock_listdir.assert_called_once()
        assert len(result) == 2

    @patch("mesh.snapshots.json.load")
    @patch("mesh.snapshots.os.path.isfile", return_value=True)
    @patch("mesh.snapshots.os.listdir")
    @patch("builtins.open", new_callable=MagicMock)
    def test_list_snapshots_filters_by_app_name(
        self, mock_file, mock_listdir, mock_isfile, mock_json_load,
    ):
        """Test_ListSnapshots_Filters_By_AppName: Verify app_name filter."""
        from mesh.snapshots import list_snapshots

        mock_listdir.return_value = ["snap-001.json", "snap-002.json"]

        metadata_list = [
            {
                "id": "snap-001",
                "app_name": "test-app",
                "created_at": "2024-04-22T12:00:00Z",
                "size_bytes": 1024,
                "status": "completed",
                "volume_paths": ["/app/data"],
                "snapshot_path": "/var/lib/mesh/snapshots/snap-001.tar.gz",
            },
            {
                "id": "snap-002",
                "app_name": "other-app",
                "created_at": "2024-04-22T13:00:00Z",
                "size_bytes": 2048,
                "status": "completed",
                "volume_paths": ["/app/data"],
                "snapshot_path": "/var/lib/mesh/snapshots/snap-002.tar.gz",
            },
        ]
        mock_json_load.side_effect = metadata_list

        result = list_snapshots(app_name="test-app")

        assert len(result) == 1
        assert result[0].app_name == "test-app"

    @patch("mesh.snapshots.os.listdir")
    def test_list_snapshots_returns_empty_list_when_none(self, mock_listdir):
        """Test_ListSnapshots_Returns_Empty_List_When_None: Verify empty list."""
        from mesh.snapshots import list_snapshots

        mock_listdir.return_value = []

        result = list_snapshots()
        assert result == []


class TestDeleteSnapshot:
    """Test suite for delete_snapshot function."""

    @patch("mesh.snapshots.os.remove")
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    def test_delete_snapshot_does_not_raise(self, mock_exists, mock_remove):
        """Test_DeleteSnapshot_Does_Not_Raise: Function executes without error."""
        from mesh.snapshots import delete_snapshot

        result = delete_snapshot("snap-001")
        assert result is True

    @patch("mesh.snapshots.os.remove")
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    def test_delete_snapshot_removes_tar_file(self, mock_exists, mock_remove):
        """Test_DeleteSnapshot_Removes_Tar_File: Verify tar.gz removal."""
        from mesh.snapshots import delete_snapshot

        delete_snapshot("snap-001")

        tar_remove_call = call("/var/lib/mesh/snapshots/snap-001.tar.gz")
        assert tar_remove_call in mock_remove.call_args_list

    @patch("mesh.snapshots.os.remove")
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    def test_delete_snapshot_removes_json_file(self, mock_exists, mock_remove):
        """Test_DeleteSnapshot_Removes_Json_File: Verify JSON removal."""
        from mesh.snapshots import delete_snapshot

        delete_snapshot("snap-001")

        json_remove_call = call("/var/lib/mesh/snapshots/snap-001.json")
        assert json_remove_call in mock_remove.call_args_list

    @patch("mesh.snapshots.os.remove")
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    def test_delete_snapshot_returns_true_on_success(self, mock_exists, mock_remove):
        """Test_DeleteSnapshot_Returns_True_On_Success: Verify return value."""
        from mesh.snapshots import delete_snapshot

        result = delete_snapshot("snap-001")
        assert result is True


class TestModuleImports:
    """Test suite for module-level imports and exports."""

    def test_module_exports_create_snapshot(self):
        """Test_Module_Exports_CreateSnapshot: Verify create_snapshot is exported."""
        from mesh.snapshots import create_snapshot

        assert callable(create_snapshot)

    def test_module_exports_restore_snapshot(self):
        """Test_Module_Exports_RestoreSnapshot: Verify restore_snapshot is exported."""
        from mesh.snapshots import restore_snapshot

        assert callable(restore_snapshot)

    def test_module_exports_list_snapshots(self):
        """Test_Module_Exports_ListSnapshots: Verify list_snapshots is exported."""
        from mesh.snapshots import list_snapshots

        assert callable(list_snapshots)

    def test_module_exports_delete_snapshot(self):
        """Test_Module_Exports_DeleteSnapshot: Verify delete_snapshot is exported."""
        from mesh.snapshots import delete_snapshot

        assert callable(delete_snapshot)

    def test_module_imports_shared_types(self):
        """Test_Module_Imports_SharedTypes: Verify SnapshotMetadata and SnapshotStatus are importable."""
        from mesh.snapshots import SnapshotMetadata, SnapshotStatus

        assert SnapshotMetadata is not None
        assert SnapshotStatus is not None


# ---------------------------------------------------------------------------
# Path traversal protection tests
# ---------------------------------------------------------------------------

class TestPathTraversal:
    """Test suite for path traversal protection in restore_snapshot."""

    def test_path_traversal_blocked(self, tmp_path):
        """test_path_traversal_blocked: malicious tar with ../../etc/passwd raises ValueError."""
        from mesh.snapshots import restore_snapshot

        snap_dir = str(tmp_path) + "/"
        snapshot_id = "snap-malicious"

        with open(snap_dir + f"{snapshot_id}.json", "w") as f:
            json.dump({"volume_paths": []}, f)

        tar_path = snap_dir + f"{snapshot_id}.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            info = tarfile.TarInfo(name="../../etc/passwd")
            info.size = 0
            tar.addfile(info, io.BytesIO(b""))

        with patch("mesh.snapshots.SNAPSHOT_DIR", snap_dir):
            with patch("mesh.snapshots.requests.post"):
                with pytest.raises(ValueError, match="Path traversal detected"):
                    restore_snapshot("test-app", snapshot_id, "http://127.0.0.1:4646")

    def test_normal_extraction_still_works(self, tmp_path):
        """test_normal_extraction_still_works: valid tar extracts without error."""
        from mesh.snapshots import restore_snapshot

        snap_dir = str(tmp_path / "snaps") + "/"
        os.makedirs(snap_dir, exist_ok=True)
        extract_dir = str(tmp_path / "nomad_data")
        os.makedirs(extract_dir, exist_ok=True)

        snapshot_id = "snap-normal"

        with open(snap_dir + f"{snapshot_id}.json", "w") as f:
            json.dump({"volume_paths": []}, f)

        tar_path = snap_dir + f"{snapshot_id}.tar.gz"
        safe_content = b"safe content"
        with tarfile.open(tar_path, "w:gz") as tar:
            info = tarfile.TarInfo(name="safe_file.txt")
            info.size = len(safe_content)
            tar.addfile(info, io.BytesIO(safe_content))

        with patch("mesh.snapshots.SNAPSHOT_DIR", snap_dir):
            with patch("mesh.snapshots.NOMAD_DATA_DIR", extract_dir):
                with patch("mesh.snapshots.requests.post"):
                    result = restore_snapshot(
                        "test-app", snapshot_id, "http://127.0.0.1:4646"
                    )

        assert result is True
        assert os.path.exists(os.path.join(extract_dir, "safe_file.txt"))


# ---------------------------------------------------------------------------
# Storage helper tests (merged from test_storage.py)
# ---------------------------------------------------------------------------

class TestEnsureSnapshotDir:
    def test_creates_directory(self, tmp_path):
        target = str(tmp_path / "new_snap_dir")
        result = ensure_snapshot_dir(target)
        assert os.path.isdir(target)
        assert result == target

    def test_returns_existing_directory(self, tmp_path):
        result = ensure_snapshot_dir(str(tmp_path))
        assert result == str(tmp_path)

    def test_nested_directory_creation(self, tmp_path):
        target = str(tmp_path / "a" / "b" / "c")
        result = ensure_snapshot_dir(target)
        assert os.path.isdir(target)
        assert result == target

    def test_permission_error_propagates(self, tmp_path, monkeypatch):
        def _raise_permission(*args, **kwargs):
            raise PermissionError("denied")

        monkeypatch.setattr("os.makedirs", _raise_permission)
        with pytest.raises(PermissionError, match="denied"):
            ensure_snapshot_dir("/fake/path")


class TestSaveSnapshot:
    def test_creates_json_file(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        meta = _make_metadata()
        result = save_snapshot("/fake.tar.gz", meta, snap_dir)
        assert os.path.isfile(result)
        assert result.endswith(f"{meta.id}.json")

    def test_json_content_round_trips(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        meta = _make_metadata()
        path = save_snapshot("/fake.tar.gz", meta, snap_dir)
        with open(path) as f:
            data = json.load(f)
        assert data["id"] == meta.id
        assert data["app_name"] == meta.app_name
        assert data["status"] == "completed"

    def test_atomic_write_no_partial_on_error(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        meta = _make_metadata()
        original_dump = json.dump
        call_count = 0

        def _failing_dump(obj, fp, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated crash")
            original_dump(obj, fp, **kwargs)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mesh.snapshots.json.dump", _failing_dump)
            with pytest.raises(RuntimeError):
                save_snapshot("/fake.tar.gz", meta, snap_dir)

        tmp_files = [
            f
            for f in os.listdir(snap_dir)
            if f.startswith(".snap_tmp_") or f.endswith(".json")
        ]
        assert len(tmp_files) == 0

    def test_overwrites_existing_metadata(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        meta = _make_metadata()
        save_snapshot("/fake.tar.gz", meta, snap_dir)
        meta.status = SnapshotStatus.FAILED
        path = save_snapshot("/fake.tar.gz", meta, snap_dir)
        with open(path) as f:
            data = json.load(f)
        assert data["status"] == "failed"

    def test_creates_directory_if_missing(self, tmp_path):
        snap_dir = f"{tmp_path}/new_dir/"
        meta = _make_metadata()
        path = save_snapshot("/fake.tar.gz", meta, snap_dir)
        assert os.path.isfile(path)


class TestLoadSnapshotMetadata:
    def test_loads_valid_metadata(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        meta = _make_metadata("snap-load-test")
        _write_json_file(snap_dir, "snap-load-test.json", meta.to_dict())

        result = load_snapshot_metadata("snap-load-test", snap_dir)
        assert result is not None
        assert result.id == "snap-load-test"
        assert result.status == SnapshotStatus.COMPLETED

    def test_returns_none_for_missing_file(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        result = load_snapshot_metadata("nonexistent", snap_dir)
        assert result is None

    def test_returns_none_for_corrupted_json(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        _write_json_file(snap_dir, "bad.json", {"invalid": True})

        result = load_snapshot_metadata("bad", snap_dir)
        assert result is None

    def test_returns_none_for_invalid_status(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        data = _make_metadata("bad-status").to_dict()
        data["status"] = "not_a_real_status"
        _write_json_file(snap_dir, "bad-status.json", data)

        result = load_snapshot_metadata("bad-status", snap_dir)
        assert result is None

    def test_returns_none_for_malformed_json(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        with open(os.path.join(snap_dir, "malformed.json"), "w") as f:
            f.write("{not valid json")

        result = load_snapshot_metadata("malformed", snap_dir)
        assert result is None


class TestListAllMetadata:
    def test_returns_empty_for_empty_directory(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        result = list_all_metadata(snap_dir)
        assert result == []

    def test_returns_empty_for_nonexistent_directory(self, tmp_path):
        result = list_all_metadata(f"{tmp_path}/no_such_dir/")
        assert result == []

    def test_lists_all_valid_metadata(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        meta1 = _make_metadata("snap-001")
        meta2 = _make_metadata("snap-002", app_name="other-app")
        _write_json_file(snap_dir, "snap-001.json", meta1.to_dict())
        _write_json_file(snap_dir, "snap-002.json", meta2.to_dict())

        result = list_all_metadata(snap_dir)
        assert len(result) == 2
        ids = {m.id for m in result}
        assert ids == {"snap-001", "snap-002"}

    def test_skips_corrupted_files_silently(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        meta = _make_metadata("snap-good")
        _write_json_file(snap_dir, "snap-good.json", meta.to_dict())
        _write_json_file(snap_dir, "snap-bad.json", {"broken": True})

        result = list_all_metadata(snap_dir)
        assert len(result) == 1
        assert result[0].id == "snap-good"

    def test_skips_non_json_files(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        meta = _make_metadata("snap-001")
        _write_json_file(snap_dir, "snap-001.json", meta.to_dict())
        with open(os.path.join(snap_dir, "notes.txt"), "w") as f:
            f.write("not a snapshot")

        result = list_all_metadata(snap_dir)
        assert len(result) == 1

    def test_handles_mixed_valid_and_corrupted(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        for i in range(3):
            meta = _make_metadata(f"snap-{i:03d}")
            _write_json_file(snap_dir, f"snap-{i:03d}.json", meta.to_dict())
        with open(os.path.join(snap_dir, "corrupt.json"), "w") as f:
            f.write("{{{bad")
        with open(os.path.join(snap_dir, "empty.json"), "w") as f:
            f.write("")

        result = list_all_metadata(snap_dir)
        assert len(result) == 3


class TestDeleteSnapshotFiles:
    def test_deletes_tar_and_json(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        tar = os.path.join(snap_dir, "snap-del.tar.gz")
        jsn = os.path.join(snap_dir, "snap-del.json")
        open(tar, "w").close()
        open(jsn, "w").close()

        result = delete_snapshot_files("snap-del", snap_dir)
        assert result is True
        assert not os.path.exists(tar)
        assert not os.path.exists(jsn)

    def test_raises_for_missing_files(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        with pytest.raises(FileNotFoundError):
            delete_snapshot_files("nonexistent", snap_dir)

    def test_raises_if_tar_missing(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        jsn = os.path.join(snap_dir, "snap-partial.json")
        open(jsn, "w").close()

        with pytest.raises(FileNotFoundError):
            delete_snapshot_files("snap-partial", snap_dir)

    def test_raises_if_json_missing(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        tar = os.path.join(snap_dir, "snap-partial.tar.gz")
        open(tar, "w").close()

        with pytest.raises(FileNotFoundError):
            delete_snapshot_files("snap-partial", snap_dir)


class TestCheckDiskSpace:
    def test_returns_true_when_enough_space(self, tmp_path):
        assert check_disk_space(1, str(tmp_path)) is True

    def test_returns_true_for_zero_bytes(self, tmp_path):
        assert check_disk_space(0, str(tmp_path)) is True

    def test_returns_false_for_impossible_size(self, tmp_path):
        assert check_disk_space(10**18, str(tmp_path)) is False

    def test_nonexistent_directory_uses_parent(self, tmp_path):
        fake_dir = f"{tmp_path}/does_not_exist/"
        assert check_disk_space(1, fake_dir) is True

    def test_returns_false_on_os_error(self, tmp_path, monkeypatch):
        def _raise_oserror(path):
            raise OSError("fail")

        monkeypatch.setattr("shutil.disk_usage", _raise_oserror)
        assert check_disk_space(1, str(tmp_path)) is False


class TestConcurrentWrites:
    def test_concurrent_save_no_corruption(self, tmp_path):
        snap_dir = f"{tmp_path}/snaps/"
        os.makedirs(snap_dir)
        errors = []
        results = []

        def _save(idx):
            try:
                meta = _make_metadata(f"snap-concurrent-{idx}")
                path = save_snapshot("/fake.tar.gz", meta, snap_dir)
                results.append(path)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_save, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        for path in results:
            assert os.path.isfile(path)
            with open(path) as f:
                data = json.load(f)
            assert "id" in data
