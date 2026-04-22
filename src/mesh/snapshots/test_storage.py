"""Tests for Snapshot Storage Backend — Local Filesystem.

Tests verify all 6 storage functions with edge cases: corrupted metadata,
missing files, empty directories, permission errors, and concurrent writes.
"""

import json
import os
import threading

import pytest

from mesh.shared import SnapshotMetadata, SnapshotStatus
from mesh.snapshots.storage import (
    check_disk_space,
    delete_snapshot_files,
    ensure_snapshot_dir,
    list_all_metadata,
    load_snapshot_metadata,
    save_snapshot,
)


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
            mp.setattr("mesh.snapshots.storage.json.dump", _failing_dump)
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
