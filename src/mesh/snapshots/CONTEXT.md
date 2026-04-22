# Feature: Application Snapshot Management

**Description:**
Provides filesystem-based state capture and restore for Nomad applications. Creates tar archives of application volumes with JSON metadata, enabling state preservation and disaster recovery.

## Interface

### Python API

**Function:** `create_snapshot()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app_name` | `str` | required | Nomad job name |
| `nomad_addr` | `str` | required | Nomad server address |

**Returns:** `SnapshotMetadata` - Snapshot details with ID, timestamp, size, status

---

**Function:** `restore_snapshot()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app_name` | `str` | required | Nomad job name to restore |
| `snapshot_id` | `str` | required | Snapshot identifier |
| `nomad_addr` | `str` | required | Nomad server address |

**Returns:** `bool` - True if restore succeeded

---

**Function:** `list_snapshots()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app_name` | `str | None` | `None` | Optional filter by application |

**Returns:** `list[SnapshotMetadata]` - List of snapshots (empty if none)

---

**Function:** `delete_snapshot()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `snapshot_id` | `str` | required | Snapshot identifier |

**Returns:** `bool` - True if deletion succeeded

## Key Behaviors

### create_snapshot
- Queries Nomad `/v1/job/{app_name}/allocations` endpoint
- Discovers volume paths from allocation task configs
- Creates tar archive at `/var/lib/mesh/snapshots/{snapshot_id}.tar.gz`
- Writes metadata JSON at `/var/lib/mesh/snapshots/{snapshot_id}.json`
- Returns SnapshotMetadata with status=COMPLETED

### restore_snapshot
- Stops running allocations for `app_name`
- Extracts tar archive to original volume paths
- Restarts allocations to apply restored state
- Returns True if allocation restart succeeds

### list_snapshots
- Scans `/var/lib/mesh/snapshots/` for `*.json` files
- Parses each JSON into SnapshotMetadata objects
- Filters by `app_name` if provided
- Returns empty list if no snapshots exist

### delete_snapshot
- Removes `{snapshot_id}.tar.gz` file
- Removes `{snapshot_id}.json` file
- Returns True if both files deleted successfully

## Dependencies

- Nomad cluster running
- Nomad API accessible for allocation queries
- Directory `/var/lib/mesh/snapshots/` writable

## Tests

- [x] Test: create_snapshot raises NotImplementedError (RED phase)
- [x] Test: restore_snapshot raises NotImplementedError (RED phase)
- [x] Test: list_snapshots raises NotImplementedError (RED phase)
- [x] Test: delete_snapshot raises NotImplementedError (RED phase)

## Example Usage

### Python API
```python
from mesh.snapshots import create_snapshot, list_snapshots, restore_snapshot

# Create snapshot
metadata = create_snapshot("my-api", "http://127.0.0.1:4646")
print(f"Snapshot ID: {metadata.id}")

# List snapshots
snapshots = list_snapshots("my-api")
for snap in snapshots:
    print(f"{snap.id}: {snap.created_at}")

# Restore snapshot
success = restore_snapshot("my-api", metadata.id, "http://127.0.0.1:4646")
```

### CLI (Future Task 9)
```bash
mesh snapshot create my-app
mesh snapshot list
mesh snapshot restore my-app <snapshot-id>
mesh snapshot delete <snapshot-id>
```
