# MVP Solid - Learnings

## 2026-04-22 Session Start
- Project: Mesh - lightweight infra orchestration (Nomad + Consul + Tailscale)
- Python 3.11+, Typer CLI, Pulumi IaC, Apache Libcloud
- v0.3.0 released, first public OSS
- OSS/EE split via plugin entry points (EE incomplete)
- 375 existing tests, ~20-50% coverage
- Container deploy works for LITE/STANDARD (Caddy ingress)
- Traefik deployment broken (returns False)
- CLI post-init broken (NOMAD_ADDR not set)
- Filesystem snapshots: completely missing

## 2026-04-22 Task 3: Shared Types Implementation (COMPLETE)

### Pattern: String-based Enums
- Follow `tier_config.py` pattern: `class MyEnum(str, Enum):`
- Use string values for JSON serialization compatibility
- Example: `CREATING = "creating"` not `CREATING = 1`

### Pattern: Dataclass Validation
- Use `__post_init__` for validation logic
- Raises `ValueError` with descriptive messages for invalid inputs
- Pattern matches simple, direct validation approach

### Pattern: Constants Definition
- Module-level variables (like `env.py`)
- Use UPPER_CASE for constants
- Path constants end with trailing slash for directories

### TDD Workflow Success
1. Write comprehensive test file first (14 tests)
2. Run pytest → Import failures (RED)
3. Implement `__init__.py` with types
4. Run pytest → All pass (GREEN)

### SnapshotMetadata Design
- 7 fields: id, app_name, created_at, size_bytes, status, volume_paths, snapshot_path
- `to_dict()` converts enum to string value (`.value`)
- Validation: non-empty strings, non-negative integers

### Test Coverage
- 14 tests for shared types (100% coverage on new module)
- Tests enum values, dataclass fields, validation, to_dict() conversion
- All tests passing on first implementation

## 2026-04-22 Task: Strip Traefik/INGRESS/PRODUCTION Code (COMPLETE)

### Scope of Removal
- Deleted `deploy_traefik/` (6 files: deploy.py, test_deploy.py, __init__.py, traefik.nomad.hcl, CONTEXT.md, __pycache__)
- Deleted `deploy_web_service/` (4 files: web_service.nomad.hcl, test_deploy.py, CONTEXT.md, __pycache__) — was Traefik-only (used Consul+Traefik tags)
- Updated `tier_config.py`: ClusterTier enum reduced from 4 to 2 (LITE, STANDARD)
- Removed `enable_traefik` field from TierConfig dataclass entirely
- Updated `tier_manager.py`: simplified detection (1 node→LITE, 2+ nodes→STANDARD)
- Updated `deploy_app/deploy.py`: removed Traefik dispatch branch, now always routes to deploy_lite_web_service
- Changed default tier from PRODUCTION to STANDARD

### Test Updates
- `test_tier_config.py`: 12→9 tests (removed INGRESS/PRODUCTION config tests, spot node test; changed multi-region to assert STANDARD)
- `test_deploy_app.py`: 8→6 tests (removed INGRESS/PRODUCTION returns-False tests; changed fallback from PRODUCTION to STANDARD)
- `test_lite_memory.py`: 4→3 tests (removed production_mode_overhead test)
- `test_lite_routing.py`: removed `assert config.enable_traefik is False`
- `test_lite_boot.py`: removed `assert config.enable_traefik is False`
- All 62 tests in affected modules pass

### Pre-existing Failures (NOT introduced by this task)
- 76 pre-existing failures in providers/provision_node modules (AWS credentials, Provider attribute issues)
- These are unrelated to Traefik removal

### Key Decisions
- `deploy_web_service/` removed because it depends on Traefik tags in HCL template
- `check_traefik_routing()` in e2e test_utils kept — it's a generic HTTP helper, no deploy_traefik import
- `security_groups.py::MESH_INGRESS_RULES` kept — "ingress" here means network firewall rules, not the tier
- Lite web service tests asserting "no traefik" kept — they verify absence, not presence

### Verification
- `grep -r "INGRESS\|PRODUCTION" src/mesh/infrastructure/progressive_activation/ --include="*.py"` → NO matches
- `grep -r "import.*traefik\|from.*traefik" src/mesh/ --include="*.py"` → NO matches
- LSP diagnostics clean on all modified files

## 2026-04-22 Task: Scaffold Snapshots Module (COMPLETE)

### Pattern: TDD RED Phase with Stubs
- Stub functions raise NotImplementedError to define API contract
- Tests verify stubs raise expected errors
- Tests with @patch decorators fail because implementation doesn't use those modules yet
- Result: 9 tests pass (stub verification), 14 tests fail (mock patching on missing modules)

### Test File Structure
- Class-based test organization: TestCreateSnapshot, TestRestoreSnapshot, TestListSnapshots, TestDeleteSnapshot
- Fixtures for mock data: nomad_allocations_response, nomad_allocation_details, snapshot_metadata
- Test naming pattern: Test_ClassName_MethodName (e.g., TestCreateSnapshot_Raises_NotImplementeded)
- Inline comments document RED vs GREEN phase expectations

### CONTEXT.md Format
- Section-based with Interface table (Parameter, Type, Default, Description)
- Key Behaviors section explaining expected functionality
- Example Usage section for Python API and CLI (future)
- Tests section with checkboxes for completed tests

### Module Documentation Pattern
- Module-level docstring: overview, public API list, dependencies, example usage
- Function docstrings: parameter table, return type, raises section
- Follows established pattern from deploy_lite_web_service/deploy.py

### Snapshots API Design
- create_snapshot(app_name, nomad_addr) -> SnapshotMetadata
- restore_snapshot(app_name, snapshot_id, nomad_addr) -> bool
- list_snapshots(app_name=None) -> list[SnapshotMetadata]
- delete_snapshot(snapshot_id) -> bool
- Imports SnapshotMetadata and SnapshotStatus from mesh.shared

### Test Coverage (RED Phase)
- 23 tests total: 9 pass (stub verification), 14 fail (mock decorators)
- Tests define exact behavior for Nomad API queries, tar operations, JSON metadata
- Mock fixtures for Nomad allocations API, allocation details with volume mounts
- TestModuleImports class verifies module exports and shared types imports

### Key Decisions
- Tests patch mesh.snapshots.requests, mesh.snapshots.tarfile, mesh.snapshots.os (fail in RED phase)
- These will work in GREEN phase when implementation imports these modules
- Module exports all 4 functions and re-exports shared types for convenience

## 2026-04-22 Task 4: mesh-install.sh Script (COMPLETE)

### Script Architecture
- `scripts/mesh-install.sh` — single-file install script for Ubuntu 22.04 VMs
- Uses `set -euo pipefail` for strict error handling
- Structured as functions for each install step (deps, tailscale, hashicorp, consul, nomad, caddy, systemd)
- `run_cmd()` wrapper enables --dry-run mode globally
- Idempotency: checks `command -v` or file existence before each install

### Boot Script Extraction
- 01-install-deps.sh: apt install curl unzip docker.io jq
- 02-install-tailscale.sh: curl install script + tailscale up with --authkey + IP forwarding
- 03-install-hashicorp.sh: Download consul/nomad zips from releases.hashicorp.com, architecture detection (aarch64→arm64)
- 06-configure-consul.sh: HCL config with bind_addr=TS_IP, server=true, bootstrap_expect=1
- 07-configure-nomad.sh: HCL config with client+server enabled, caddy-data host_volume appended
- 10-install-caddy.sh: Cloudsmith apt repo install

### Version Constants (from production scripts)
- NOMAD_VERSION = "1.9.3"
- CONSUL_VERSION = "1.17.1"

### Test Strategy for Shell Scripts
- Use `subprocess.run(["bash", SCRIPT_PATH, ...])` to test CLI args
- Tests check return codes and stderr/stdout for error messages
- File content tests verify script structure (shebang, strict mode, versions, idempotency patterns)
- 38 tests total across 6 test classes (Help, ArgValidation, ServerRole, ClientStub, DryRun, CheckOnly, ScriptFile)

### Key Design Decisions
- Client role is a stub (exit 1) — Task 5 will implement
- Config file written to ~/.mesh/config with NOMAD_ADDR, CONSUL_ADDR, TAILSCALE_IP, PUBLIC_IP, ROLE
- Systemd services match boot.sh templates exactly
- Caddy host_volume appended to nomad.hcl (idempotent via grep check)
- IP forwarding persisted in /etc/sysctl.d/99-tailscale.conf

## 2026-04-22 Task 6: Container Deployment Hardening (COMPLETE)

### Pattern: Multi-Source Address Discovery
- Resolution chain: env var → config file → default localhost
- `get_nomad_addr()` and `get_consul_addr()` follow identical pattern
- Config file: `~/.mesh/config` written by `mesh-install.sh` (shell-style key=value with optional quotes)

### Config File Parsing
- `_parse_config_value(file_path, key)` — generic parser for shell-style config files
- Handles quoted (single/double) and unquoted values
- Graceful on missing file, permission errors, empty lines, comments
- Returns None on any failure (never raises)

### Module Constants
- `MESH_CONFIG_DIR` and `MESH_CONFIG_FILE` — module-level, patchable via monkeypatch
- `get_config_file_path()` — public accessor for config path

### Backward Compatibility
- `get_nomad_addr()` still returns `str` (no type change)
- Env var check uses `os.environ.get()` directly (bypasses `get_env()` to avoid default injection)
- helpers.py unchanged — re-exports from env.py, changes propagate automatically

### Test Strategy
- `autouse=True` fixture cleans env vars before each test
- `config_dir` fixture patches module-level constants with tmp_path
- 23 tests across 7 classes: env priority, config reading, defaults, consul, edge cases, return types
- File permission test (`os.chmod 0o000`) validates graceful degradation

### Files Modified/Created
- Modified: `src/mesh/infrastructure/config/env.py` (148→237 lines)
- Created: `src/mesh/cli/commands/test_deploy_hardening.py` (23 tests)
- NOT modified: helpers.py, status.py, logs.py, ssh.py (changes propagate via imports)

## 2026-04-22 Task 5: Client Role in mesh-install.sh (COMPLETE)

### Client vs Server Differences
- Consul client: `server = false`, `retry_join = ["$SERVER_IP"]` (no bootstrap_expect, no ui_config)
- Nomad client: `server { enabled = false }`, `client { enabled = true }`, `server_join { retry_join = ["$SERVER_IP":4647] }`
- No Caddy installed on client (Caddy is server-only for ingress)
- Config NOMAD_ADDR points to SERVER_IP (not localhost/public_ip)
- Config CONSUL_ADDR also points to SERVER_IP for client

### IP Validation Pattern
- Regex: `^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$` for IPv4
- Hostname regex: `^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$`
- Accepts both IPs and hostnames (e.g., `mesh-leader` via Tailscale MagicDNS)

### Script Architecture Notes
- `write_config()` uses role-aware logic: client → NOMAD_ADDR=SERVER_IP, server → NOMAD_ADDR=public_ip
- `print_client_summary()` is separate from `print_summary()` (server version)
- install_client() reuses: install_deps, install_tailscale, install_hashicorp, create_systemd_services, write_config
- install_client() uses NEW: configure_consul_client, configure_nomad_client, print_client_summary

### Test Pattern: Extracting Shell Function Body
- Parse script text to find function body between braces (depth tracking)
- Verify specific function calls are present/absent in install flow
- 49 tests total: 38 existing + 11 new client role tests

### macOS vs Ubuntu Differences
- macOS reports `arm64` (uname -m), Ubuntu reports `aarch64` — script only accepts aarch64
- No /etc/os-release on macOS — prerequisite check correctly warns
- Tests pass because they test arg parsing / script content, not runtime execution

## 2026-04-22 Task 7: Snapshot Engine GREEN Phase (COMPLETE)

### TDD GREEN Phase Pattern
- RED phase left 14 failing tests (AttributeError: module has no attribute 'requests'/'tarfile'/'json'/'os')
- Root cause: stub functions didn't import these modules, so @patch("mesh.snapshots.X") couldn't find targets
- Fix: Add all imports at module level in __init__.py (json, os, tarfile, uuid, datetime, requests)
- After implementation, RED-phase "raises NotImplementedError" tests must be updated to verify real behavior

### Critical: Module-Level Imports for @patch
- `@patch("mesh.snapshots.requests")` requires `import requests` at module level in `mesh/snapshots/__init__.py`
- Same for tarfile, json, os — must be importable as `mesh.snapshots.X`
- Decorator pattern: innermost decorator → first parameter; outermost → last parameter

### Mock Setup for create_snapshot Tests
- Function calls requests.get TWICE: once for allocations list, once for allocation details
- Used `_mock_get_factory()` helper returning different responses based on URL pattern
- Must mock: requests.get, uuid.uuid4, os.makedirs, tarfile.open, os.path.exists, os.path.getsize, json.dump, builtins.open
- `builtins.open` needs `new_callable=mock_open` to avoid real filesystem writes

### Mock Setup for restore_snapshot Tests
- Must mock: builtins.open (mock_open), json.load, tarfile.open, requests.post
- requests.post called TWICE: stop (with json body) and restart (no body)
- Verify specific calls with `call(url, json=...) in mock_post.call_args_list`

### SnapshotMetadata JSON Round-Trip
- `to_dict()` serializes status as `self.status.value` (string "completed")
- `list_snapshots()` must convert back: `data["status"] = SnapshotStatus(data["status"])`
- Without conversion, SnapshotMetadata(**data) fails because string != SnapshotStatus enum

### Test Results
- 23/23 tests pass (was 14 FAIL + 9 PASS)
- 14/14 shared types tests pass (no regression)
- LSP diagnostics clean on __init__.py

## 2026-04-22 Task 12: Demo Mode Cleanup (COMPLETE)

### Scope of Changes
- Updated `src/mesh/cli/commands/status.py` to show error instead of silent fallback when demo=False
- Added `show_error` to imports in status.py (was missing)
- Created `src/mesh/cli/commands/test_status.py` with 5 tests
- `logs.py` and `ssh.py` already had correct error handling (no changes needed)

### Pattern: Error Handling vs Silent Fallback
- **Before**: status.py fell back to mock data silently when no cluster found
- **After**: status.py shows clear error and returns early when demo=False
- Error message: "No Mesh cluster found." + "Run mesh-install.sh or set NOMAD_ADDR"
- This pattern already existed in logs.py and ssh.py (lines 115-119 and 150-154)

### Import Safety
- Adding `show_error` to imports broke tests initially (NameError: 'show_error' is not defined)
- Always verify imports are complete after adding new UI functions
- Pattern: `from mesh.cli.ui.panels import (..., show_error, ...)`

### Test Pattern: Demo Mode Behavior
- Test class `TestStatusNoCluster`: verifies error when demo=False and no cluster
- Test class `TestStatusDemoMode`: verifies mock data when demo=True
- Test class `TestStatusWithCluster`: verifies live data when cluster exists
- Mock pattern: `@patch("mesh.cli.commands.status._get_live_status", return_value=(None, None))`

### Verification Results
- All 5 new status tests pass
- All existing tests in test_logs.py pass (no regression)
- All existing tests in test_ssh.py pass (no regression)
- 64/65 tests in src/mesh/cli/commands/ pass (1 pre-existing failure in test_doctor.py)

### Key Decision
- Only status.py needed changes — logs.py and ssh.py already had proper error handling
- This suggests the MVP commands evolved at different times
- Good to verify patterns across similar commands before making changes

## 2026-04-22 Task 8: Snapshot Storage Backend (COMPLETE)

### Pattern: Extracting Storage Into a Separate Module
- NEW file `storage.py` alongside existing `__init__.py` (no refactor of engine)
- Engine can optionally import from storage later (not part of this task)
- Same data types: SnapshotMetadata, SnapshotStatus, SNAPSHOT_DIR from mesh.shared

### Atomic Write Pattern
- `save_snapshot()` uses tempfile.mkstemp + os.replace for atomic writes
- Write to temp file in same directory (ensures same filesystem for rename)
- Clean up temp file on any exception (BaseException catch)
- Prevents partial JSON files if process crashes mid-write

### Trailing Slash Gotcha in Paths
- SNAPSHOT_DIR = "/var/lib/mesh/snapshots/" (trailing slash)
- `os.path.dirname("/a/b/")` returns "/a/b" (not "/a") — trailing slash breaks dirname
- Fix: `path.rstrip(os.sep)` before dirname call in `check_disk_space()`

### Edge Cases Tested
- Corrupted JSON: returns None / silently skipped in list
- Invalid status enum: returns None (SnapshotStatus() raises ValueError)
- Empty/missing directory: returns empty list / None
- Concurrent writes: threading with 10 parallel saves, all succeed
- Permission errors: propagated from ensure_snapshot_dir
- Missing files: FileNotFoundError from delete_snapshot_files
- Partial files: only tar or only json → FileNotFoundError on delete

### Test Strategy for Filesystem Operations
- Use `tmp_path` fixture (pytest builtin) for all file operations
- Construct paths with trailing slash to match SNAPSHOT_DIR convention: `f"{tmp_path}/snaps/"`
- No monkeypatch needed for default args — pass explicit snapshot_dir parameter
- 30 tests across 7 test classes, all passing

### Coverage
- storage.py: 98.63% (1 miss: list_all_metadata except Exception catch block)
- No regression in existing test_snapshots.py (23/23 pass)
- Total: 53 tests in src/mesh/snapshots/ (30 new + 23 existing)

## 2026-04-22 Task 10: Install Script Integration Tests (COMPLETE)

### Test Architecture
- `scripts/test_install_integration.py` — 65 integration tests across 6 classes
- Two testing strategies: script content analysis + subprocess CLI testing
- `extract_function_body()` helper parses bash function bodies via brace-depth tracking
- `script_content` fixture loads script once per module (scope="module")

### Test Classes
- **TestServerConfigGeneration** (10 tests): Nomad server=true, bootstrap_expect=1, Caddy host_volume, Consul server=true/ui_config, write_config uses public_ip
- **TestClientConfigGeneration** (13 tests): Nomad server=false, server_join retry_join, Consul server=false, no Caddy, write_config uses SERVER_IP, step ordering
- **TestServerClientConsistency** (12 tests): Same versions, systemd ExecStart, config path, datacenter dc1, shared deps/tailscale/hashicorp, same data dirs
- **TestIdempotency** (12 tests): command -v checks, file existence, dpkg -s, grep checks, "already installed" patterns count >= 4
- **TestErrorCases** (14 tests): client w/o server-ip, invalid role, missing tskey, invalid IP format, help, no args, injection attempts
- **TestDryRunMode** (5 tests): Server/client dry-run arg parsing, run_cmd helper content, prerequisite reaching

### Pattern: Bash String Assertions
- Script uses `"$DRY_RUN" == "true"` (with $ prefix) — must match exactly in assertions
- Heredoc content uses `${SERVER_IP}` (dollar-brace) — Python assertions need the exact string

### Pattern: Function Body Extraction
- `extract_function_body(content, "func_name")` finds `func_name()` then tracks brace depth
- Returns substring from function declaration to closing brace
- Used to isolate install flows for step presence/absence checks

### Test Results
- 65/65 integration tests PASS
- 49/49 existing unit tests PASS (no regression)
- Total: 114 tests for mesh-install.sh

### T9: CLI Snapshot Commands
- **Rich markup gotcha**: Don't use `[/]` closing tags after f-string interpolated color constants like `{MESH_GREEN}{value}[/]` — the interpolated hex code isn't a valid Rich tag. Use `[{MESH_GREEN}]{value}` without closing `[/]` instead (Rich auto-closes at line end) or use explicit `[/{MESH_GREEN}]`.
- **Sub-app registration pattern**: `app.add_typer(snapshot_app, name="snapshot")` creates `mesh snapshot create/restore/list/delete` command group. Add import at top of main.py, register after all commands but before plugin discovery loop.
- **Mock path matters**: Must mock at the import location, not the definition — `@patch("mesh.cli.commands.snapshot.create_snapshot")` not `@patch("mesh.snapshots.create_snapshot")`.
- **SnapshotMetadata dataclass**: Lives in `mesh.shared.__init__` (not `mesh.shared` — that's a package directory). Has fields: id, app_name, created_at, size_bytes, status (SnapshotStatus enum), volume_paths, snapshot_path.
- **Pre-existing failures**: `test_doctor.py::test_env_check_passes` fails (env-dependent test, not related to snapshot changes).

## 2026-04-22 Task 11: E2E MVP Golden Path Test (COMPLETE)

### Test Architecture
- `src/mesh/verification/e2e_mvp/test_mvp_flow.py` — 16 tests across 4 classes
- All tests use `@pytest.mark.e2e` decorator for selective running
- All infrastructure mocked — no running Nomad cluster required

### Test Classes
- **TestMVPGoldenPath** (1 test): Full create→list→restore→delete flow in one test method
- **TestMVPSnapshotErrorCases** (5 tests): Nonexistent app, no running allocs, missing snapshot, empty list
- **TestMVPSnapshotCLIIntegration** (7 tests): Typer CliRunner for create/list/restore/delete + error cases
- **TestMVPSnapshotRoundTrip** (3 tests): JSON metadata persistence, app_name filtering, unfiltered list

### Mock Strategy
- `_mock_get_factory(alloc_list, alloc_detail)`: routes requests.get by URL pattern (allocations vs allocation detail)
- `_patch_snapshot_dir(tmp_path)`: patches `mesh.snapshots.SNAPSHOT_DIR` to tmp_path with trailing slash
- Round-trip tests use real filesystem writes (not mock_open) for JSON metadata verification
- CLI tests mock at import location: `mesh.cli.commands.snapshot.create_snapshot` not `mesh.snapshots.create_snapshot`

### Key Patterns
- `mock_open(read_data=...)` for reading JSON metadata in restore tests
- `mock_uuid.return_value = MagicMock(hex="...")` for predictable snapshot IDs
- Typer CliRunner: `self.runner.invoke(snapshot_app, ["create", APP_NAME])` 
- CLI error exit codes: `result.exit_code == 1` for error, `== 0` for success
- `pytest.raises((FileNotFoundError, OSError))` for restore of missing snapshot (open() can raise either)

### Verification Results
- 16/16 new tests PASS
- 69/69 tests in src/mesh/verification/ PASS (no regressions)
- LSP diagnostics clean
