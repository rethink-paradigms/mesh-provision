"""Tests for Feature: Application Snapshot Management (GREEN Phase)

Tests verify the implemented snapshot engine: create, restore, list, delete.
"""

from unittest.mock import patch, MagicMock, mock_open, call
import pytest

from mesh.shared import SnapshotMetadata, SnapshotStatus


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


class TestCreateSnapshot:
    """Test suite for create_snapshot function."""

    @patch("builtins.open", new_callable=mock_open)
    @patch("mesh.snapshots.json.dump")
    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_does_not_raise(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_dump, mock_file,
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

    @patch("builtins.open", new_callable=mock_open)
    @patch("mesh.snapshots.json.dump")
    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_queries_nomad_allocations(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_dump, mock_file,
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

    @patch("builtins.open", new_callable=mock_open)
    @patch("mesh.snapshots.json.dump")
    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open")
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_creates_tar_archive(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_dump, mock_file,
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

    @patch("builtins.open", new_callable=mock_open)
    @patch("mesh.snapshots.json.dump")
    @patch("mesh.snapshots.os.path.getsize", return_value=1024)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_writes_metadata_json(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_dump, mock_file,
        nomad_allocations_response, nomad_allocation_details,
    ):
        """Test_CreateSnapshot_Writes_Metadata_Json: Verify json.dump called."""
        from mesh.snapshots import create_snapshot

        mock_get.side_effect = _mock_get_factory(
            nomad_allocations_response, nomad_allocation_details
        )
        mock_uuid.return_value = MagicMock(hex="abc123def456")

        create_snapshot("test-app", "http://127.0.0.1:4646")

        assert mock_dump.called
        dumped_data = mock_dump.call_args[0][0]
        assert dumped_data["app_name"] == "test-app"
        assert dumped_data["status"] == "completed"

    @patch("builtins.open", new_callable=mock_open)
    @patch("mesh.snapshots.json.dump")
    @patch("mesh.snapshots.os.path.getsize", return_value=10485760)
    @patch("mesh.snapshots.os.path.exists", return_value=True)
    @patch("mesh.snapshots.tarfile.open", return_value=MagicMock())
    @patch("mesh.snapshots.os.makedirs")
    @patch("mesh.snapshots.uuid.uuid4")
    @patch("mesh.snapshots.requests.get")
    def test_create_snapshot_returns_snapshot_metadata(
        self, mock_get, mock_uuid, mock_makedirs, mock_tar,
        mock_exists, mock_getsize, mock_dump, mock_file,
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
    @patch("builtins.open", new_callable=mock_open)
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
    @patch("builtins.open", new_callable=mock_open)
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
    @patch("builtins.open", new_callable=mock_open)
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
    @patch("builtins.open", new_callable=mock_open)
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
    @patch("builtins.open", new_callable=mock_open)
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
    @patch("builtins.open", new_callable=mock_open)
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
    @patch("builtins.open", new_callable=mock_open)
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
    @patch("builtins.open", new_callable=mock_open)
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
