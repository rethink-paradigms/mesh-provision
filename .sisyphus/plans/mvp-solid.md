# Mesh MVP — 3 Solid Features

## TL;DR

> **Quick Summary**: Strip Mesh down to 3 production-solid features: (1) interactive 2-VM install script with Tailscale mesh, (2) reliable container deployment via Nomad, (3) tar-based container volume snapshots. Remove all broken/incomplete features for a clean MVP.
>
> **Deliverables**:
> - Interactive install script (`mesh-install.sh`) for server + client VM setup
> - Container deployment tested end-to-end (deploy, status, logs)
> - Container volume snapshot create/restore CLI commands
> - Broken features stripped (Traefik automation, INGRESS/PRODUCTION tiers)
> - Full TDD test suite for all 3 features
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 (types) → Task 4 (install script) → Task 7 (snapshot module) → Task 10 (CLI commands) → FINAL

---

## Context

### Original Request
User has a v0.3.0 release of Mesh (lightweight infrastructure orchestration platform) with 7+ features, some working and some broken. The CLI is a blocker (NOMAD_ADDR not set after init). User wants to strip down to 3 solid features that work in all production cases, with a manual 2-VM install path as alternative to the broken CLI init.

### Interview Summary
**Key Discussions**:
- **Feature selection**: User chose Cluster Bootstrap + Container Deployment + Container Volume Snapshots as the 3 MVP features
- **Install approach**: Interactive install script run on each VM (NOT fixing mesh init CLI)
- **Snapshot scope**: Container volume snapshots only (tar-based, no CSI driver)
- **Broken features**: Strip out Traefik, INGRESS/PRODUCTION tiers — clean codebase
- **Test strategy**: TDD — RED → GREEN → REFACTOR for every feature
- **CLI init**: NOT fixing mesh init — only building manual install script path

**Research Findings**:
- Container deployment works for LITE/STANDARD tiers via Caddy (proven)
- Traefik deployment explicitly returns `False` ("not yet automated") — needs removal
- Boot scripts (6 modular Jinja2 templates) are production-quality
- Filesystem snapshots are completely missing — must be built from scratch
- 375 existing tests provide patterns but coverage is ~20-50%

### Metis Review
**Identified Gaps** (addressed):
- **Install script runtime context**: Script runs ON the VM (SSH'd in or cloud-init), not from user's machine
- **Snapshot target**: Nomad task allocation volume mount paths (`/opt/nomad/data/alloc/...`)
- **Tailscale auth for manual setup**: Script prompts user for Tailscale auth key interactively
- **Demo mode fallbacks**: Keep demo mode for non-MVP commands, strip from MVP commands
- **Snapshot storage**: Default to local filesystem (`/var/lib/mesh/snapshots/`), no cloud backend for MVP

---

## Work Objectives

### Core Objective
Create a clean, production-solid MVP of Mesh with exactly 3 features that work end-to-end: cluster bootstrap via manual install, container deployment, and container volume snapshots. All broken/incomplete features are stripped to prevent dead-end user experiences.

### Concrete Deliverables
- `scripts/mesh-install.sh` — Interactive install script (server/client roles, Tailscale, Nomad, Consul, Caddy)
- `src/mesh/snapshots/` — New module for container volume snapshot create/list/restore/delete
- `mesh snapshot create <app>` — CLI command to snapshot a running app's volumes
- `mesh snapshot restore <app> <snapshot-id>` — CLI command to restore from snapshot
- `mesh snapshot list` — CLI command to list snapshots
- Cleaned codebase with Traefik automation and INGRESS/PRODUCTION tiers removed
- Full TDD test coverage for all 3 features

### Definition of Done
- [x] `mesh-install.sh` provisions 2 VMs (server + client) connected via Tailscale
- [x] After install, `mesh deploy myapp --image nginx:latest` works without errors
- [x] `mesh status` shows real cluster data (not demo fallback)
- [x] `mesh snapshot create myapp` creates a tar snapshot of app volumes
- [x] `mesh snapshot restore myapp <id>` restores app from snapshot
- [x] All 3 features have passing TDD tests
- [x] No broken Traefik/INGRESS/PRODUCTION code paths remain

### Must Have
- Interactive install script with server/client role selection
- Nomad + Consul + Tailscale + Caddy installation via script
- Container deployment end-to-end (deploy, status, logs)
- Container volume snapshot create/restore
- TDD tests for all features
- All broken features removed or hidden

### Must NOT Have (Guardrails)
- **NO fixing mesh init CLI** — out of scope, manual script is the alternative
- **NO CSI driver integration** — tar-based snapshots only
- **NO cloud provider provisioning fixes** — manual VM install only
- **NO Traefik automation** — strip it, don't fix it
- **NO INGRESS/PRODUCTION tier code** — strip it
- **NO full VM disk snapshots** — container volumes only
- **NO snapshot cloud storage backends** — local filesystem only
- **NO EE features** — GPU, monitoring, backups stay in EE
- **NO scope creep into CLI init fixes** — strictly manual install path
- **AI slop prevention**: No excessive comments, no over-abstraction, no generic names like `data/result/item`, no JSDoc on every function

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 375 existing tests)
- **Automated tests**: TDD (test first)
- **Framework**: pytest (already configured)
- **Each task follows**: RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Install Script**: Use interactive_bash (tmux) — run script, send inputs, validate output
- **Container Deployment**: Use Bash (curl to Nomad API) — deploy, check status, verify running
- **Snapshot Operations**: Use Bash — create snapshot, verify tar exists, restore, verify data
- **CLI Commands**: Use interactive_bash (tmux) — run mesh commands, validate output

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — types, cleanup, scaffolding):
├── Task 1: Shared types and constants [quick]
├── Task 2: Strip Traefik/INGRESS/PRODUCTION broken code [unspecified-high]
├── Task 3: Snapshot module scaffolding + test infrastructure [quick]

Wave 2 (Core implementation — install, deploy, snapshot engine):
├── Task 4: Interactive install script — server role (depends: 1) [deep]
├── Task 5: Interactive install script — client role (depends: 1, 4) [deep]
├── Task 6: Container deployment hardening (depends: 2) [unspecified-high]
├── Task 7: Snapshot engine — create/restore core (depends: 1, 3) [deep]
├── Task 8: Snapshot storage backend — local filesystem (depends: 3, 7) [unspecified-high]

Wave 3 (CLI integration + verification):
├── Task 9: CLI snapshot commands — mesh snapshot create/restore/list (depends: 7, 8) [unspecified-high]
├── Task 10: Install script integration test — 2-VM full flow (depends: 4, 5) [deep]
├── Task 11: Deploy-to-snapshot end-to-end test (depends: 6, 7, 9) [deep]
├── Task 12: Demo mode cleanup — remove fallbacks from MVP commands (depends: 2) [quick]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
├── Task F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay

Critical Path: Task 1 → Task 4 → Task 5 → Task 10 → FINAL
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 5 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 4, 5, 7 | 1 |
| 2 | — | 6, 12 | 1 |
| 3 | — | 7, 8 | 1 |
| 4 | 1 | 5, 10 | 2 |
| 5 | 1, 4 | 10 | 2 |
| 6 | 2 | 11 | 2 |
| 7 | 1, 3 | 8, 9, 11 | 2 |
| 8 | 3, 7 | 9 | 2 |
| 9 | 7, 8 | 11 | 3 |
| 10 | 4, 5 | FINAL | 3 |
| 11 | 6, 7, 9 | FINAL | 3 |
| 12 | 2 | FINAL | 3 |

### Agent Dispatch Summary

- **Wave 1**: 3 tasks — T1 → `quick`, T2 → `unspecified-high`, T3 → `quick`
- **Wave 2**: 5 tasks — T4 → `deep`, T5 → `deep`, T6 → `unspecified-high`, T7 → `deep`, T8 → `unspecified-high`
- **Wave 3**: 4 tasks — T9 → `unspecified-high`, T10 → `deep`, T11 → `deep`, T12 → `quick`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. **Shared Types and Constants**

  **What to do**:
  - Create `src/mesh/shared/__init__.py` with shared type definitions for the MVP
  - Define constants: snapshot storage path (`/var/lib/mesh/snapshots/`), Nomad data paths, volume mount patterns
  - Define dataclasses: `SnapshotMetadata`, `NodeRole` (SERVER/CLIENT), `ClusterConfig`
  - Define enums: `SnapshotStatus` (CREATING/COMPLETED/FAILED/RESTORING)
  - Write TDD tests first: test `SnapshotMetadata` creation, validation, serialization
  - Then implement the types to pass tests

  **Must NOT do**:
  - Do not create utility functions — only types, constants, and enums
  - Do not depend on external libraries beyond stdlib dataclasses
  - Do not over-abstract — concrete types for concrete MVP needs

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Pure type definitions, no complex logic, straightforward dataclass creation
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `python-pro`: Overkill for type definitions

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 2, 3)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 4, 5, 7
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/mesh/infrastructure/progressive_activation/tier_config.py:1-50` — Existing pattern for tier enums and configuration classes. Follow this style for defining `NodeRole`, `SnapshotStatus` enums.
  - `src/mesh/infrastructure/config/env.py:1-40` — Pattern for defining constants and environment variable access. Use similar pattern for snapshot paths.

  **API/Type References**:
  - `src/mesh/workloads/deploy_lite_web_service/lite_web_service.nomad.hcl:1-20` — Nomad job HCL showing volume mount patterns. The snapshot types must reference Nomad allocation paths like `/opt/nomad/data/alloc/`.

  **Test References**:
  - `src/mesh/infrastructure/progressive_activation/test_tier_config.py` — Pattern for testing enums and config classes. Follow this test structure.

  **WHY Each Reference Matters**:
  - `tier_config.py`: Shows the established pattern for defining tier-related types — copy this style for consistency
  - `env.py`: Demonstrates how to define and access configuration constants — match this pattern
  - `lite_web_service.nomad.hcl`: Shows actual volume mount paths that snapshots will target — types must reference these paths
  - `test_tier_config.py`: Provides the testing pattern to follow for TDD

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: `src/mesh/shared/test_types.py`
  - [ ] `pytest src/mesh/shared/test_types.py` → PASS (all tests, 0 failures)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: SnapshotMetadata creation and serialization
    Tool: Bash
    Preconditions: Virtual environment activated, package installed in dev mode
    Steps:
      1. Run: `python -c "from mesh.shared import SnapshotMetadata; m = SnapshotMetadata(id='snap-001', app_name='test-app', created_at='2026-04-22T00:00:00Z', size_bytes=1024, status=SnapshotStatus.COMPLETED); print(m.to_dict())"`
      2. Assert output contains `"id": "snap-001"` and `"app_name": "test-app"`
    Expected Result: Python import succeeds and prints valid dict with all fields
    Failure Indicators: ImportError, KeyError, missing fields in output
    Evidence: .sisyphus/evidence/task-1-types-import.txt

  Scenario: Invalid SnapshotMetadata raises validation error
    Tool: Bash
    Steps:
      1. Run: `python -c "from mesh.shared import SnapshotMetadata; SnapshotMetadata(id='', app_name='', created_at='', size_bytes=-1, status=None)"`
      2. Assert exit code is non-zero or validation error is raised
    Expected Result: ValueError or similar validation error
    Failure Indicators: Object created without error (no validation)
    Evidence: .sisyphus/evidence/task-1-types-validation.txt
  ```

  **Commit**: YES
  - Message: `feat(types): add shared MVP types and constants`
  - Files: `src/mesh/shared/__init__.py`, `src/mesh/shared/test_types.py`
  - Pre-commit: `pytest src/mesh/shared/test_types.py`

- [x] 2. **Strip Traefik/INGRESS/PRODUCTION Broken Code**

  **What to do**:
  - Write TDD tests first: test that importing mesh.cli.main does NOT register Traefik-related commands
  - Remove or disable `src/mesh/workloads/deploy_traefik/` — the entire module returns `False`
  - Remove INGRESS and PRODUCTION tier references from `src/mesh/infrastructure/progressive_activation/tier_config.py` — keep only LITE and STANDARD
  - Update `src/mesh/workloads/deploy_app/deploy.py` to remove Traefik dispatch path — only LITE and STANDARD remain
  - Update `src/mesh/cli/commands/status.py` to remove INGRESS/PRODUCTION status display
  - Update `src/mesh/cli/commands/deploy.py` to remove INGRESS/PRODUCTION options from `--tier` flag
  - Remove `src/mesh/workloads/deploy_web_service/` if it only serves Traefik-based deployments
  - Update imports and references across the codebase
  - Run existing tests to ensure nothing breaks after removal

  **Must NOT do**:
  - Do NOT remove LITE or STANDARD tier code — those work
  - Do NOT remove Caddy ingress code — that works
  - Do NOT remove the demo mode entirely — keep `mesh demo` working
  - Do NOT remove boot scripts that are shared (01-deps, 02-tailscale, 03-hashicorp)
  - Do NOT break existing 375 tests — all must still pass

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multi-file cleanup requiring careful understanding of dependencies and import chains
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `legacy-modernizer`: Not modernizing, just stripping

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 3)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 6, 12
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/mesh/workloads/deploy_traefik/deploy.py` — The broken module to remove. Read to understand what calls it.
  - `src/mesh/workloads/deploy_app/deploy.py` — The tier dispatcher that references Traefik. Must be updated to remove Traefik path.
  - `src/mesh/infrastructure/progressive_activation/tier_config.py` — Tier enum definition. Remove INGRESS/PRODUCTION entries.

  **API/Type References**:
  - `src/mesh/cli/main.py:1-50` — CLI command registration. Check if Traefik-related commands are registered here.
  - `src/mesh/cli/commands/deploy.py` — Deploy command with `--tier` flag. Remove INGRESS/PRODUCTION options.

  **Test References**:
  - `src/mesh/workloads/deploy_traefik/test_deploy.py` — Tests for the broken module. These should be removed with the module.
  - `src/mesh/verification/e2e_*` — E2E tests. Ensure none depend on Traefik/INGRESS/PRODUCTION.

  **WHY Each Reference Matters**:
  - `deploy_traefik/deploy.py`: The primary broken code — understand its return value pattern before removing
  - `deploy_app/deploy.py`: The dispatcher that routes to Traefik — must be updated to not route there
  - `tier_config.py`: Source of truth for tier definitions — remove broken tiers here
  - `cli/main.py`: CLI registration — verify no Traefik commands leak through

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file: verify no Traefik imports remain in active code paths
  - [ ] `pytest src/mesh -m "not e2e"` → PASS (no regressions)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: No Traefik references in active code
    Tool: Bash
    Preconditions: Code cleanup complete
    Steps:
      1. Run: `grep -r "traefik" src/mesh/ --include="*.py" -l`
      2. Assert: no results OR only in comments/docs (not import statements)
      3. Run: `grep -r "INGRESS\|PRODUCTION" src/mesh/infrastructure/progressive_activation/ --include="*.py"`
      4. Assert: no matches in active tier definitions
    Expected Result: No Traefik imports or INGRESS/PRODUCTION tier references in active code
    Failure Indicators: Active import statements referencing Traefik modules
    Evidence: .sisyphus/evidence/task-2-cleanup-grep.txt

  Scenario: Existing tests still pass after cleanup
    Tool: Bash
    Steps:
      1. Run: `pytest src/mesh -m "not e2e" --tb=short`
      2. Assert: exit code 0, all tests pass
    Expected Result: 0 failures, 0 errors
    Failure Indicators: Import errors or test failures from removed code
    Evidence: .sisyphus/evidence/task-2-tests-pass.txt
  ```

  **Commit**: YES
  - Message: `chore(cleanup): strip broken Traefik and INGRESS/PRODUCTION tiers`
  - Files: Multiple (removed files + updated imports)
  - Pre-commit: `pytest src/mesh -m "not e2e"`

- [x] 3. **Snapshot Module Scaffolding + Test Infrastructure**

  **What to do**:
  - Write TDD tests first: define the snapshot module interface as failing tests
  - Create `src/mesh/snapshots/__init__.py` with module exports
  - Create `src/mesh/snapshots/CONTEXT.md` documenting the module's purpose and interface contract
  - Define the public API as abstract/testable interfaces:
    - `create_snapshot(app_name: str, nomad_addr: str) -> SnapshotMetadata`
    - `restore_snapshot(app_name: str, snapshot_id: str, nomad_addr: str) -> bool`
    - `list_snapshots(app_name: str | None = None) -> list[SnapshotMetadata]`
    - `delete_snapshot(snapshot_id: str) -> bool`
  - Create test fixtures and mocks for Nomad API responses
  - Tests should FAIL at this stage (RED phase) — implementation comes in Task 7

  **Must NOT do**:
  - Do not implement the actual snapshot logic — only interfaces and failing tests
  - Do not import heavy dependencies — keep scaffolding lightweight
  - Do not create CLI commands yet — that's Task 9

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Scaffolding and test creation, no complex implementation logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 1, 2)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src/mesh/workloads/deploy_lite_web_service/CONTEXT.md` — Example of a well-written CONTEXT.md for a module. Follow this format.
  - `src/mesh/workloads/deploy_lite_web_service/test_lite_web_service.py` — Example of TDD test patterns in this project. Follow this structure.

  **API/Type References**:
  - `src/mesh/shared/__init__.py` (from Task 1) — `SnapshotMetadata` and `SnapshotStatus` types that the snapshot module will use.

  **Test References**:
  - `src/mesh/infrastructure/boot_consul_nomad/test_boot.py` — Example of fixture-based testing with mock data. Follow this pattern for Nomad API mocks.

  **WHY Each Reference Matters**:
  - `deploy_lite_web_service/CONTEXT.md`: Shows the established format for module documentation — match it
  - `test_lite_web_service.py`: Shows TDD patterns used in this codebase — copy the test structure
  - `test_boot.py`: Shows mock/fixture patterns for infrastructure testing — reuse for snapshot testing

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: `src/mesh/snapshots/test_snapshots.py`
  - [ ] `pytest src/mesh/snapshots/test_snapshots.py` → FAIL (tests exist but interface not implemented — RED phase)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Snapshot module exports are defined
    Tool: Bash
    Preconditions: Task 1 complete (shared types exist)
    Steps:
      1. Run: `python -c "from mesh.snapshots import create_snapshot, restore_snapshot, list_snapshots, delete_snapshot; print('OK')"`
      2. Assert: ImportError (expected — interfaces not yet implemented)
    Expected Result: ImportError indicating module structure exists but functions not implemented
    Failure Indicators: Module not found at all (wrong path) or import succeeds with actual implementation (jumped ahead)
    Evidence: .sisyphus/evidence/task-3-scaffold-import.txt

  Scenario: Test file exists and fails (RED phase)
    Tool: Bash
    Steps:
      1. Run: `pytest src/mesh/snapshots/test_snapshots.py --tb=line 2>&1 | head -5`
      2. Assert: output shows FAILED or ERROR status
    Expected Result: Tests exist but fail because implementation is missing
    Failure Indicators: Tests pass (implies implementation was done prematurely) or file not found
    Evidence: .sisyphus/evidence/task-3-scaffold-tests.txt
  ```

  **Commit**: YES
  - Message: `feat(snapshots): scaffold snapshot module and test infrastructure`
  - Files: `src/mesh/snapshots/__init__.py`, `src/mesh/snapshots/CONTEXT.md`, `src/mesh/snapshots/test_snapshots.py`
  - Pre-commit: `pytest src/mesh/snapshots/test_snapshots.py` (expected: FAIL — RED phase)

- [x] 4. **Interactive Install Script — Server Role**

  **What to do**:
  - Write TDD tests first: test script argument parsing, server role detection, dependency checks
  - Create `scripts/mesh-install.sh` — the interactive install script
  - Script flow for SERVER role:
    1. Check prerequisites (root, Ubuntu 22.04, internet connectivity)
    2. Ask: "What role? [server/client]" → user picks server
    3. Ask: "Tailscale auth key:" → user pastes key
    4. Install dependencies (curl, jq, etc.)
    5. Install Tailscale, authenticate with provided key
    6. Install HashiCorp tools (Nomad, Consul)
    7. Configure Consul server agent
    8. Configure Nomad server agent
    9. Install Caddy (LITE/STANDARD ingress)
    10. Start all services via systemd
    11. Print success message with: server IP, Nomad address, Consul address, Tailscale IP
    12. Print instruction: "On the client VM, run this script and choose 'client' role"
  - Reuse logic from existing boot scripts in `src/mesh/infrastructure/boot_consul_nomad/scripts/`
  - The script must be idempotent — safe to re-run
  - Tests: test argument parsing, test role detection, test prerequisite checking with mocks

  **Must NOT do**:
  - Do NOT call Pulumi or Libcloud — this is manual install
  - Do NOT provision VMs — script runs INSIDE an existing VM
  - Do NOT implement cloud provider logic
  - Do NOT handle GPU, monitoring, or EE features

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex shell script with multiple system interactions, service configurations, and error handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 6, 7, 8 — but Task 5 logically depends on this)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 5, 10
  - **Blocked By**: Task 1 (shared types for constants)

  **References**:

  **Pattern References**:
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/01-install-deps.sh` — Base dependency installation. Extract and reuse this logic in the install script.
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/02-install-tailscale.sh` — Tailscale installation pattern. Copy the installation commands.
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/03-install-hashicorp.sh` — Nomad/Consul binary installation. Reuse the exact installation steps.
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/06-configure-consul.sh` — Consul configuration pattern. Adapt for server role.
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/07-configure-nomad.sh` — Nomad configuration pattern. Adapt for server role.
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/10-install-caddy.sh` — Caddy installation. Reuse directly.

  **API/Type References**:
  - `src/mesh/infrastructure/boot_consul_nomad/generate_boot_scripts.py:30-80` — Shows how boot scripts are generated with Jinja2 templates. The install script should produce equivalent configurations without Jinja2 (pure bash).

  **Test References**:
  - `src/mesh/infrastructure/boot_consul_nomad/test_boot.py` — Tests for boot script generation. Adapt patterns for testing install script.

  **WHY Each Reference Matters**:
  - `01-install-deps.sh` through `10-install-caddy.sh`: These are the PROVEN installation scripts already working in production — the install script should be a bash aggregation of these scripts
  - `generate_boot_scripts.py`: Shows the template variables and configuration patterns used — understand what gets injected
  - `test_boot.py`: Test patterns for infrastructure scripts — reuse for testing install script

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: `scripts/test_mesh_install.sh` (bats framework or pytest with subprocess)
  - [ ] Tests for: argument parsing, role detection, prerequisite checking
  - [ ] `pytest scripts/test_mesh_install.py` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Install script shows help and validates arguments
    Tool: interactive_bash (tmux)
    Preconditions: Script exists and is executable
    Steps:
      1. Run: `bash scripts/mesh-install.sh --help`
      2. Assert output contains: "server", "client", "Tailscale", "Nomad"
      3. Run: `bash scripts/mesh-install.sh --role invalid`
      4. Assert exit code non-zero, error message about invalid role
    Expected Result: Help text shows usage, invalid role rejected
    Failure Indicators: Script runs without validation, accepts any input
    Evidence: .sisyphus/evidence/task-4-install-help.txt

  Scenario: Install script detects missing prerequisites
    Tool: Bash
    Preconditions: Running on a system without Docker installed
    Steps:
      1. Run: `bash scripts/mesh-install.sh --role server --check-only`
      2. Assert: output lists missing prerequisites
      3. Assert: exit code non-zero
    Expected Result: Script checks for prerequisites and reports missing ones
    Failure Indicators: Script proceeds without checking prerequisites
    Evidence: .sisyphus/evidence/task-4-install-prereq.txt
  ```

  **Commit**: YES
  - Message: `feat(install): interactive server role install script`
  - Files: `scripts/mesh-install.sh`, `scripts/test_mesh_install.py`
  - Pre-commit: `pytest scripts/test_mesh_install.py`

- [x] 5. **Interactive Install Script — Client Role**

  **What to do**:
  - Extend `scripts/mesh-install.sh` with CLIENT role logic
  - Write TDD tests first: test client role setup, server discovery, join process
  - Client script flow:
    1. Same prerequisite checks as server
    2. Ask: "Server Tailscale IP or hostname:" → user provides
    3. Install dependencies, Tailscale, HashiCorp tools (same as server)
    4. Configure Consul CLIENT agent — pointing to server's Tailscale IP
    5. Configure Nomad CLIENT agent — pointing to server's Tailscale IP
    6. Start all services
    7. Verify connection: check Consul membership, check Nomad node registration
    8. Print success with node info
  - Tests: test client config generation, test server IP validation, test connection verification

  **Must NOT do**:
  - Do NOT install Caddy on client (ingress is server-only)
  - Do NOT configure Nomad server or Consul server on client
  - Do NOT start Traefik or any ingress on client

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Continuation of install script with client-specific service configuration and network discovery
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 4 for script structure)
  - **Parallel Group**: Wave 2 (sequential after Task 4)
  - **Blocks**: Task 10
  - **Blocked By**: Task 1 (shared types), Task 4 (server role as reference)

  **References**:

  **Pattern References**:
  - `scripts/mesh-install.sh` (from Task 4) — The server role implementation. Client role extends this script.
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/06-configure-consul.sh` — Consul agent configuration. Note the difference between server and client config blocks.
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/07-configure-nomad.sh` — Nomad agent configuration. Note the server vs client config.

  **API/Type References**:
  - `src/mesh/infrastructure/provision_cloud_cluster/main.py:80-150` — Shows how the cloud provisioner configures server vs client nodes. The config differences (retry_join, server vs client mode) are documented here.

  **Test References**:
  - `scripts/test_mesh_install.py` (from Task 4) — Extend existing test file with client role tests.

  **WHY Each Reference Matters**:
  - `mesh-install.sh`: The script being extended — understand the existing structure before adding client role
  - `06-configure-consul.sh` and `07-configure-nomad.sh`: Show the exact config differences between server and client modes
  - `provision_cloud_cluster/main.py`: Shows the production-tested configuration for both roles

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Tests added to: `scripts/test_mesh_install.py`
  - [ ] Tests for: client config generation, server IP validation, connection check logic
  - [ ] `pytest scripts/test_mesh_install.py` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Client role configures Nomad client agent
    Tool: Bash
    Preconditions: Script with client role implemented
    Steps:
      1. Run: `bash scripts/mesh-install.sh --role client --server-ip 100.64.0.1 --dry-run`
      2. Assert: output shows Nomad client config with "server address: 100.64.0.1:4647"
      3. Assert: output shows Consul client config with "retry_join: 100.64.0.1"
      4. Assert: NO Nomad server config blocks
    Expected Result: Dry run shows correct client configuration targeting server IP
    Failure Indicators: Server config generated for client role, wrong ports, missing retry_join
    Evidence: .sisyphus/evidence/task-5-client-config.txt

  Scenario: Client rejects invalid server IP
    Tool: Bash
    Steps:
      1. Run: `bash scripts/mesh-install.sh --role client --server-ip invalid-ip`
      2. Assert: exit code non-zero, error message about invalid IP
    Expected Result: Script validates server IP format and rejects invalid input
    Failure Indicators: Script proceeds with invalid IP
    Evidence: .sisyphus/evidence/task-5-client-validation.txt
  ```

  **Commit**: YES
  - Message: `feat(install): interactive client role install script`
  - Files: `scripts/mesh-install.sh`, `scripts/test_mesh_install.py`
  - Pre-commit: `pytest scripts/test_mesh_install.py`

- [x] 6. **Container Deployment Hardening**

  **What to do**:
  - Write TDD tests first: test deploy with real Nomad API contract, test status with real response format
  - Verify and harden the existing LITE/STANDARD deploy path:
    - `src/mesh/workloads/deploy_lite_web_service/deploy.py` — ensure it works with the install script's Nomad
    - `src/mesh/workloads/deploy_lite_ingress/deploy.py` — ensure Caddy ingress works post-install
  - Fix NOMAD_ADDR discovery: after install script sets up server, CLI must be able to find the Nomad address
  - Create a cluster connection helper that auto-discovers NOMAD_ADDR:
    - Check env var first
    - Check `~/.mesh/config` file (created by install script)
    - Check local Multipass if available
    - Fail with clear error message if no cluster found
  - Ensure `mesh deploy`, `mesh status`, `mesh logs` all work against the manually-installed cluster
  - Add proper error messages when cluster is unreachable (not silent demo fallback)
  - Tests: test NOMAD_ADDR discovery, test deploy against mock Nomad API, test status display

  **Must NOT do**:
  - Do NOT fix the mesh init CLI — only post-install connectivity
  - Do NOT add Traefik or INGRESS tier support
  - Do NOT change the Nomad job HCL templates (they work)
  - Do NOT add cloud provider features

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multi-file changes across CLI and workloads, needs careful understanding of existing deploy flow
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5, 7, 8)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 11
  - **Blocked By**: Task 2 (Traefik cleanup must be done first)

  **References**:

  **Pattern References**:
  - `src/mesh/workloads/deploy_lite_web_service/deploy.py` — The working deploy implementation. Verify it still works after cleanup.
  - `src/mesh/workloads/deploy_app/deploy.py` — Tier-aware deployment dispatcher. After Task 2 cleanup, verify only LITE/STANDARD paths remain.
  - `src/mesh/cli/commands/deploy.py` — CLI deploy command. Check how it calls the deploy module.

  **API/Type References**:
  - `src/mesh/infrastructure/config/env.py:get_nomad_addr()` — Current NOMAD_ADDR discovery logic. This is what needs to be enhanced with file-based discovery.
  - `src/mesh/cli/commands/status.py:_check_cluster()` — Current cluster check that fails silently. Fix to show proper error.

  **Test References**:
  - `src/mesh/workloads/deploy_lite_web_service/test_lite_web_service.py` — Existing deploy tests. Extend with NOMAD_ADDR discovery tests.

  **WHY Each Reference Matters**:
  - `deploy_lite_web_service/deploy.py`: The core working deploy code — understand it before modifying surrounding infrastructure
  - `env.py:get_nomad_addr()`: The function that currently fails to find Nomad — this is the key fix point
  - `status.py:_check_cluster()`: Shows how cluster detection currently works (and fails) — improve error handling here

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file: `src/mesh/cli/commands/test_deploy_hardening.py`
  - [ ] Tests for: NOMAD_ADDR discovery from config file, from env, fallback chain
  - [ ] `pytest src/mesh/cli/commands/test_deploy_hardening.py` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: NOMAD_ADDR discovered from config file
    Tool: Bash
    Preconditions: `~/.mesh/config` contains `NOMAD_ADDR=http://100.64.0.1:4646`
    Steps:
      1. Unset NOMAD_ADDR env var: `unset NOMAD_ADDR`
      2. Run: `python -c "from mesh.infrastructure.config.env import get_nomad_addr; print(get_nomad_addr())"`
      3. Assert output: `http://100.64.0.1:4646`
    Expected Result: NOMAD_ADDR read from config file when env var not set
    Failure Indicators: Returns default localhost or raises error
    Evidence: .sisyphus/evidence/task-6-nomad-discovery.txt

  Scenario: Clear error when no cluster found
    Tool: Bash
    Preconditions: No NOMAD_ADDR env var, no config file, no local cluster
    Steps:
      1. Run: `mesh status 2>&1`
      2. Assert: output contains "No cluster found" and instructions on how to connect
      3. Assert: does NOT fall back to demo data silently
    Expected Result: Clear error message with remediation steps
    Failure Indicators: Falls back to demo data silently or shows generic error
    Evidence: .sisyphus/evidence/task-6-no-cluster-error.txt
  ```

  **Commit**: YES
  - Message: `feat(deploy): harden container deployment for MVP`
  - Files: `src/mesh/infrastructure/config/env.py`, `src/mesh/cli/commands/test_deploy_hardening.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_deploy_hardening.py`

- [x] 7. **Snapshot Engine — Create/Restore Core**

  **What to do**:
  - Implement the snapshot engine to pass the failing tests from Task 3 (GREEN phase)
  - `create_snapshot(app_name, nomad_addr)`:
    1. Query Nomad API to find running allocations for the app
    2. Find the allocation's task group and volume mount paths
    3. Stop the allocation gracefully (or take online snapshot if possible)
    4. Tar the volume directories: `tar czf /var/lib/mesh/snapshots/{id}.tar.gz -C /opt/nomad/data/alloc/{alloc_id}/ ...`
    5. Record metadata (app name, timestamp, size, allocation ID)
    6. Restart the allocation
    7. Return SnapshotMetadata
  - `restore_snapshot(app_name, snapshot_id, nomad_addr)`:
    1. Find current allocations for the app
    2. Stop allocations
    3. Extract tar: `tar xzf /var/lib/mesh/snapshots/{id}.tar.gz -C /opt/nomad/data/alloc/{alloc_id}/`
    4. Restart allocations
    5. Return True on success
  - `list_snapshots(app_name=None)`:
    1. Scan `/var/lib/mesh/snapshots/` for `.tar.gz` files
    2. Read metadata from sidecar `.json` files
    3. Filter by app_name if provided
    4. Return list of SnapshotMetadata
  - `delete_snapshot(snapshot_id)`:
    1. Remove `.tar.gz` and `.json` files
    2. Return True on success
  - Tests should now PASS (GREEN phase)

  **Must NOT do**:
  - Do NOT implement cloud storage backends — local filesystem only
  - Do NOT implement incremental snapshots — full tar only
  - Do NOT implement CSI drivers
  - Do NOT snapshot VM disks — only Nomad task volumes

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core new feature implementation with Nomad API integration, file system operations, and error handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5, 6, 8)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 8, 9, 11
  - **Blocked By**: Task 1 (shared types), Task 3 (scaffolding + failing tests)

  **References**:

  **Pattern References**:
  - `src/mesh/workloads/deploy_lite_web_service/deploy.py:40-100` — Shows how to interact with Nomad API (submit jobs, check status). Follow this pattern for querying allocations.
  - `src/mesh/workloads/deploy_lite_web_service/lite_web_service.nomad.hcl:20-40` — Shows volume mount configuration in Nomad job specs. This is where volume paths are defined.

  **API/Type References**:
  - `src/mesh/infrastructure/config/env.py:get_nomad_addr()` — How to get Nomad API address. Use this in snapshot functions.
  - Nomad API: `GET /v1/job/{job_name}/allocations` — Returns allocation list with task states
  - Nomad API: `GET /v1/allocation/{alloc_id}` — Returns allocation details with task config and volume mounts

  **Test References**:
  - `src/mesh/snapshots/test_snapshots.py` (from Task 3) — The failing tests that must now pass. Implement against these.

  **WHY Each Reference Matters**:
  - `deploy_lite_web_service/deploy.py`: Shows the production-tested pattern for Nomad API interaction — follow this pattern for consistency
  - `lite_web_service.nomad.hcl`: Shows where volume paths are configured — snapshots need to find these paths at runtime
  - `test_snapshots.py`: The failing tests that define the contract — implement to make these pass

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] `pytest src/mesh/snapshots/test_snapshots.py` → PASS (GREEN phase achieved)
  - [ ] Tests cover: create, restore, list, delete operations with mocked Nomad API

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Create snapshot of a deployed app
    Tool: Bash
    Preconditions: Mock Nomad API running with a test app allocation
    Steps:
      1. Run: `python -c "from mesh.snapshots import create_snapshot; result = create_snapshot('test-app', 'http://localhost:4646'); print(result)"`
      2. Assert: SnapshotMetadata returned with status=COMPLETED
      3. Check: `ls /var/lib/mesh/snapshots/` contains a .tar.gz file and .json metadata file
    Expected Result: Snapshot tar file and metadata JSON created in snapshots directory
    Failure Indicators: FileNotFoundError, empty tar, missing metadata
    Evidence: .sisyphus/evidence/task-7-create-snapshot.txt

  Scenario: Restore snapshot restores volume data
    Tool: Bash
    Preconditions: Snapshot exists from previous scenario, test data in snapshot
    Steps:
      1. Run: `python -c "from mesh.snapshots import restore_snapshot; result = restore_snapshot('test-app', 'snap-001', 'http://localhost:4646'); print(result)"`
      2. Assert: returns True
      3. Check: volume directory contains restored data matching original
    Expected Result: Volume data restored from snapshot tar
    Failure Indicators: Returns False, data mismatch, tar extraction error
    Evidence: .sisyphus/evidence/task-7-restore-snapshot.txt
  ```

  **Commit**: YES
  - Message: `feat(snapshots): implement create and restore core engine`
  - Files: `src/mesh/snapshots/engine.py`, `src/mesh/snapshots/__init__.py`
  - Pre-commit: `pytest src/mesh/snapshots/test_snapshots.py`

- [x] 8. **Snapshot Storage Backend — Local Filesystem**

  **What to do**:
  - Extract storage operations from Task 7 into a dedicated storage module
  - Write TDD tests: test file operations, directory creation, space checking, cleanup
  - Create `src/mesh/snapshots/storage.py`:
    - `ensure_snapshot_dir()` — Create `/var/lib/mesh/snapshots/` with correct permissions
    - `save_snapshot(archive_path, metadata)` — Write tar + JSON metadata atomically
    - `load_snapshot_metadata(snapshot_id)` — Read and parse metadata JSON
    - `list_all_metadata()` — Scan directory and return all snapshot metadata
    - `delete_snapshot_files(snapshot_id)` — Remove tar + JSON safely
    - `check_disk_space(required_bytes)` — Verify sufficient disk space before create
  - Handle edge cases: concurrent writes, partial writes, corrupted metadata, permission errors
  - Tests: test all operations with temp directories, test concurrent access, test corruption handling

  **Must NOT do**:
  - Do NOT implement S3, GCS, or any cloud storage
  - Do NOT implement compression beyond what tar provides
  - Do NOT implement encryption at rest (MVP)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: File system operations with edge cases (concurrency, corruption, permissions) need careful handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 4, 5, 6)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Task 3 (scaffolding), Task 7 (core engine to extract storage from)

  **References**:

  **Pattern References**:
  - `src/mesh/snapshots/engine.py` (from Task 7) — The core engine that will use this storage module. Extract file operations from here.

  **Test References**:
  - `src/mesh/snapshots/test_snapshots.py` (from Task 7) — Existing tests that should still pass after extraction.

  **WHY Each Reference Matters**:
  - `engine.py`: The code being refactored — storage operations should be extracted without breaking the engine interface

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file: `src/mesh/snapshots/test_storage.py`
  - [ ] Tests for: save, load, list, delete, space check, corruption handling
  - [ ] `pytest src/mesh/snapshots/test_storage.py` → PASS
  - [ ] `pytest src/mesh/snapshots/test_snapshots.py` → still PASS (no regression)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Save and load snapshot metadata
    Tool: Bash
    Preconditions: Snapshot directory exists
    Steps:
      1. Run: `python -c "from mesh.snapshots.storage import save_snapshot, load_snapshot_metadata; save_snapshot('/tmp/test.tar.gz', {'id':'test','app':'app1'}); m = load_snapshot_metadata('test'); print(m)"`
      2. Assert: metadata matches what was saved
    Expected Result: Round-trip save/load works correctly
    Failure Indicators: Data loss, JSON parse errors, file not found
    Evidence: .sisyphus/evidence/task-8-storage-roundtrip.txt

  Scenario: Handle corrupted metadata gracefully
    Tool: Bash
    Preconditions: Snapshot directory has a file with invalid JSON metadata
    Steps:
      1. Create corrupted file: `echo "not json" > /var/lib/mesh/snapshots/bad.json`
      2. Run: `python -c "from mesh.snapshots.storage import load_snapshot_metadata; load_snapshot_metadata('bad')"`
      3. Assert: returns None or raises SnapshotCorruptedError (not generic crash)
    Expected Result: Graceful error handling for corrupted files
    Failure Indicators: Unhandled exception, crash
    Evidence: .sisyphus/evidence/task-8-storage-corruption.txt
  ```

  **Commit**: YES
  - Message: `feat(snapshots): local filesystem storage backend`
  - Files: `src/mesh/snapshots/storage.py`, `src/mesh/snapshots/test_storage.py`
  - Pre-commit: `pytest src/mesh/snapshots/`

- [x] 9. **CLI Snapshot Commands — mesh snapshot create/restore/list**

  **What to do**:
  - Write TDD tests first: test CLI argument parsing, test output formatting
  - Create `src/mesh/cli/commands/snapshot.py` with Typer commands:
    - `mesh snapshot create <app_name>` — Create snapshot of app volumes
    - `mesh snapshot restore <app_name> <snapshot_id>` — Restore from snapshot
    - `mesh snapshot list [--app <app_name>]` — List snapshots
    - `mesh snapshot delete <snapshot_id>` — Delete a snapshot
  - Register snapshot commands in `src/mesh/cli/main.py`
  - Rich-formatted output: tables for list, progress bars for create/restore
  - Error handling: clear messages when Nomad unreachable, app not found, snapshot not found
  - Tests: test each command with mocked snapshot engine

  **Must NOT do**:
  - Do NOT add snapshot commands to the EE plugin system
  - Do NOT implement scheduling or cron for automatic snapshots
  - Do NOT add snapshot diff or comparison features

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: CLI integration with multiple commands, Rich formatting, and error handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 10, 11, 12)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 11
  - **Blocked By**: Task 7 (engine), Task 8 (storage)

  **References**:

  **Pattern References**:
  - `src/mesh/cli/commands/deploy.py` — Existing CLI command pattern with Typer. Follow this exact structure for snapshot commands.
  - `src/mesh/cli/commands/status.py` — Rich-formatted table output pattern. Use for `mesh snapshot list`.
  - `src/mesh/cli/ui/panels.py` — Shared UI components (console, show_success, show_error). Use for output formatting.

  **API/Type References**:
  - `src/mesh/cli/main.py:app` — The main Typer app. Snapshot commands must be registered here.
  - `src/mesh/snapshots/__init__.py` (from Task 7) — The snapshot engine functions to call from CLI.

  **Test References**:
  - `src/mesh/cli/commands/deploy.py` — Has tests showing how to test Typer commands. Follow this pattern.

  **WHY Each Reference Matters**:
  - `deploy.py`: The established CLI command pattern — match this for consistency
  - `status.py`: Shows Rich table formatting — use for snapshot list display
  - `main.py`: Where commands are registered — add snapshot subcommands here

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file: `src/mesh/cli/commands/test_snapshot_cmd.py`
  - [ ] Tests for: create, restore, list, delete commands with mocked engine
  - [ ] `pytest src/mesh/cli/commands/test_snapshot_cmd.py` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: mesh snapshot create creates and shows progress
    Tool: interactive_bash (tmux)
    Preconditions: Mock Nomad with running test app, snapshot engine operational
    Steps:
      1. Run: `mesh snapshot create test-app`
      2. Assert: progress bar shown, success message with snapshot ID
      3. Run: `mesh snapshot list`
      4. Assert: table shows the created snapshot with app name, date, size
    Expected Result: Snapshot created and listed successfully
    Failure Indicators: Error about missing app, no progress feedback
    Evidence: .sisyphus/evidence/task-9-cli-create.txt

  Scenario: mesh snapshot restore restores and shows confirmation
    Tool: interactive_bash (tmux)
    Preconditions: Snapshot exists from previous scenario
    Steps:
      1. Run: `mesh snapshot restore test-app <snapshot-id>`
      2. Assert: confirmation prompt shown, restore progress, success message
    Expected Result: App restored from snapshot with clear progress feedback
    Failure Indicators: Silent failure, no progress, missing confirmation
    Evidence: .sisyphus/evidence/task-9-cli-restore.txt

  Scenario: mesh snapshot list with no snapshots shows empty state
    Tool: Bash
    Preconditions: No snapshots exist
    Steps:
      1. Run: `mesh snapshot list`
      2. Assert: "No snapshots found" message, not error or crash
    Expected Result: Graceful empty state message
    Failure Indicators: Error, crash, or empty output with no message
    Evidence: .sisyphus/evidence/task-9-cli-empty.txt
  ```

  **Commit**: YES
  - Message: `feat(cli): add mesh snapshot CLI commands`
  - Files: `src/mesh/cli/commands/snapshot.py`, `src/mesh/cli/commands/test_snapshot_cmd.py`, `src/mesh/cli/main.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_snapshot_cmd.py`

- [x] 10. **Install Script Integration Test — 2-VM Full Flow**

  **What to do**:
  - Write TDD tests first: define the expected end state of a 2-VM install
  - Create integration tests that verify the full install flow:
    1. Server VM install → verify Nomad server running, Consul server running, Tailscale connected
    2. Client VM install → verify Nomad client connected to server, Consul client joined
    3. Cross-verification → verify client appears in `nomad node status`, Consul members
  - Use Docker containers or Multipass as lightweight VM substitutes for testing
  - Test idempotency: run install script twice on same "VM" → should succeed both times
  - Test error cases: missing Tailscale key, unreachable server IP, wrong OS

  **Must NOT do**:
  - Do NOT require real cloud VMs for testing
  - Do NOT test cloud provider provisioning
  - Do NOT test GPU or EE features

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Integration testing requires orchestrating multiple containers/VMs and verifying cross-node connectivity
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 11, 12)
  - **Parallel Group**: Wave 3
  - **Blocks**: FINAL
  - **Blocked By**: Task 4 (server install), Task 5 (client install)

  **References**:

  **Pattern References**:
  - `src/mesh/verification/e2e_lite_mode/` — Existing E2E test suite for lite mode. Follow this test structure and fixture patterns.
  - `src/mesh/verification/e2e_multi_node_scenarios/` — Multi-node test scenarios. Adapt for 2-VM install verification.

  **Test References**:
  - `src/mesh/verification/e2e_lite_mode/test_lite_deployment.py` — Shows how E2E tests are structured with pytest markers. Use `@pytest.mark.integration` marker.

  **WHY Each Reference Matters**:
  - `e2e_lite_mode/`: The closest existing test pattern to what we need — shows how to test a full cluster setup
  - `e2e_multi_node_scenarios/`: Shows multi-node test patterns — adapt for server/client topology

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file: `scripts/test_install_integration.py`
  - [ ] Tests for: server setup, client setup, cross-verification, idempotency, error cases
  - [ ] `pytest scripts/test_install_integration.py -m "not slow"` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full 2-VM install and verify cluster
    Tool: interactive_bash (tmux)
    Preconditions: Two Docker containers or Multipass VMs running Ubuntu 22.04
    Steps:
      1. On server container: `bash mesh-install.sh --role server --tskey $TSKEY`
      2. Wait for services to start (30s)
      3. Verify: `systemctl is-active nomad consul tailscale` → all "active"
      4. On client container: `bash mesh-install.sh --role client --server-ip $SERVER_IP --tskey $TSKEY`
      5. Wait for join (15s)
      6. Verify on server: `nomad node status -json` → client node listed
      7. Verify on server: `consul members` → client listed with status "alive"
    Expected Result: 2-node cluster formed with server + client connected
    Failure Indicators: Services not running, client not joining, connection refused
    Evidence: .sisyphus/evidence/task-10-integration-2vm.txt

  Scenario: Idempotent install — run twice without error
    Tool: Bash
    Preconditions: Server already installed from previous scenario
    Steps:
      1. Run install script again: `bash mesh-install.sh --role server --tskey $TSKEY`
      2. Assert: exit code 0, message "already configured" or similar
      3. Verify services still running
    Expected Result: Second run succeeds, services still healthy
    Failure Indicators: Error on second run, services broken after re-run
    Evidence: .sisyphus/evidence/task-10-idempotent.txt
  ```

  **Commit**: YES
  - Message: `test(install): 2-VM integration test`
  - Files: `scripts/test_install_integration.py`
  - Pre-commit: `pytest scripts/test_install_integration.py -m "not slow"`

- [x] 11. **Deploy-to-Snapshot End-to-End Test**

  **What to do**:
  - Write TDD tests first: define the full E2E flow as failing tests
  - Create E2E test that exercises the complete MVP workflow:
    1. Install 2-VM cluster (using install script from Tasks 4/5)
    2. Deploy a test application: `mesh deploy test-app --image nginx:latest`
    3. Verify app running: `mesh status` shows test-app
    4. Write data to app: `curl` to create a file in the volume
    5. Create snapshot: `mesh snapshot create test-app`
    6. Modify data: `curl` to change the file
    7. Restore snapshot: `mesh snapshot restore test-app <id>`
    8. Verify data restored: file content matches step 4, not step 6
    9. Clean up: `mesh destroy`
  - This is the "golden path" test proving all 3 MVP features work together

  **Must NOT do**:
  - Do NOT test cloud providers — use local infrastructure only
  - Do NOT test Traefik or INGRESS tier
  - Do NOT test GPU or EE features

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Full E2E test spanning all 3 MVP features, requires careful orchestration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 10, 12)
  - **Parallel Group**: Wave 3
  - **Blocks**: FINAL
  - **Blocked By**: Task 6 (deploy hardening), Task 7 (snapshot engine), Task 9 (CLI commands)

  **References**:

  **Pattern References**:
  - `src/mesh/verification/e2e_app_deployment/` — Existing E2E deployment tests. Follow this structure for the E2E test.
  - `src/mesh/verification/test_app/` — Test application container used in E2E tests. Reuse this.

  **Test References**:
  - `src/mesh/verification/e2e_app_deployment/test_deployment.py` — Existing E2E deployment test. Extend with snapshot operations.

  **WHY Each Reference Matters**:
  - `e2e_app_deployment/`: The closest existing E2E test — shows the deployment verification pattern to build on
  - `test_app/`: Pre-built test container that can be used in the E2E test

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file: `src/mesh/verification/e2e_mvp/test_mvp_flow.py`
  - [ ] Tests for: full deploy → snapshot → modify → restore → verify flow
  - [ ] `pytest src/mesh/verification/e2e_mvp/test_mvp_flow.py -m "e2e"` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full MVP golden path — deploy, snapshot, restore
    Tool: Bash
    Preconditions: 2-VM cluster running, mesh CLI installed
    Steps:
      1. `mesh deploy test-app --image nginx:latest --port 80`
      2. Wait for deployment: `sleep 10 && mesh status | grep test-app`
      3. Write data: `curl -X POST http://$APP_IP/test -d "original-data"`
      4. Snapshot: `mesh snapshot create test-app`
      5. Modify data: `curl -X POST http://$APP_IP/test -d "modified-data"`
      6. Restore: `mesh snapshot restore test-app <snapshot-id>`
      7. Verify: `curl http://$APP_IP/test` → returns "original-data" (not "modified-data")
    Expected Result: Data restored to pre-modification state
    Failure Indicators: Data unchanged after modify, or data shows "modified-data" after restore
    Evidence: .sisyphus/evidence/task-11-e2e-golden-path.txt

  Scenario: Snapshot of non-existent app fails gracefully
    Tool: Bash
    Preconditions: No app deployed
    Steps:
      1. Run: `mesh snapshot create nonexistent-app`
      2. Assert: clear error "App 'nonexistent-app' not found" (not crash)
    Expected Result: Graceful error message
    Failure Indicators: Stack trace, unhandled exception
    Evidence: .sisyphus/evidence/task-11-e2e-missing-app.txt
  ```

  **Commit**: YES
  - Message: `test(e2e): deploy-to-snapshot end-to-end`
  - Files: `src/mesh/verification/e2e_mvp/test_mvp_flow.py`
  - Pre-commit: `pytest src/mesh/verification/e2e_mvp/test_mvp_flow.py -m "e2e"`

- [x] 12. **Demo Mode Cleanup — Remove Fallbacks from MVP Commands**

  **What to do**:
  - Write TDD tests first: test that MVP commands show real errors, not demo data
  - In `mesh status`: Remove the silent fallback to `DEMO_NODES`/`MOCK_APPS` when cluster unreachable. Instead show clear error.
  - In `mesh logs`: Remove the silent fallback to `DEMO_LOG_LINES`. Show real error.
  - In `mesh ssh`: Remove the silent fallback to `DEMO_NODES`. Show real error.
  - Keep `mesh demo` command working — that's intentional demo mode
  - Keep `--demo` flag on commands — that's explicit, not silent fallback
  - The change: when `--demo` is NOT set and cluster is unreachable → show clear error, NOT demo data
  - Tests: test that without `--demo` flag and no cluster, commands error (not show mock data)

  **Must NOT do**:
  - Do NOT remove `mesh demo` command
  - Do NOT remove `--demo` flag functionality
  - Do NOT remove demo data constants (still used by `mesh demo`)
  - Do NOT change behavior when `--demo` is explicitly set

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Targeted changes to remove fallback branches in 3 files
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 10, 11)
  - **Parallel Group**: Wave 3
  - **Blocks**: FINAL
  - **Blocked By**: Task 2 (Traefik cleanup)

  **References**:

  **Pattern References**:
  - `src/mesh/cli/commands/status.py` — Has the fallback logic `if not _check_cluster(): show_demo_data()`. Change to show error instead.
  - `src/mesh/cli/commands/logs.py` — Has similar fallback to `DEMO_LOG_LINES`. Remove.
  - `src/mesh/cli/commands/ssh.py` — Has fallback to `DEMO_NODES`. Remove.

  **Test References**:
  - Existing test files for these commands — update to expect errors instead of demo data when no cluster.

  **WHY Each Reference Matters**:
  - `status.py`, `logs.py`, `ssh.py`: The three files with silent demo fallbacks — these are the specific files to change

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Tests: verify commands error without `--demo` when no cluster
  - [ ] `pytest src/mesh/cli/commands/` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: mesh status without --demo and no cluster shows error
    Tool: Bash
    Preconditions: No cluster running, NOMAD_ADDR not set
    Steps:
      1. Run: `mesh status 2>&1`
      2. Assert: output contains "No cluster found" or similar error
      3. Assert: output does NOT contain "mesh-leader" (demo data)
    Expected Result: Clear error, not demo data
    Failure Indicators: Shows demo data silently
    Evidence: .sisyphus/evidence/task-12-status-no-fallback.txt

  Scenario: mesh status --demo still shows demo data
    Tool: Bash
    Preconditions: No cluster running
    Steps:
      1. Run: `mesh status --demo`
      2. Assert: output shows mock nodes (mesh-leader, mesh-worker-1, etc.)
    Expected Result: Demo data shown when --demo flag is explicit
    Failure Indicators: Error shown even with --demo flag
    Evidence: .sisyphus/evidence/task-12-demo-flag-works.txt
  ```

  **Commit**: YES
  - Message: `chore(cli): remove demo fallbacks from MVP commands`
  - Files: `src/mesh/cli/commands/status.py`, `src/mesh/cli/commands/logs.py`, `src/mesh/cli/commands/ssh.py`
  - Pre-commit: `pytest src/mesh/cli/commands/`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
>
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest` + any linter config. Review all changed files for: `as any`/type ignores, empty catches, print statements in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (install → deploy → snapshot → restore). Test edge cases: empty state, large volume, concurrent snapshots. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Task 1**: `feat(types): add shared MVP types and constants` — `src/mesh/shared/`
- **Task 2**: `chore(cleanup): strip broken Traefik and INGRESS/PRODUCTION tiers` — multiple files
- **Task 3**: `feat(snapshots): scaffold snapshot module and test infrastructure` — `src/mesh/snapshots/`
- **Task 4**: `feat(install): interactive server role install script` — `scripts/mesh-install.sh`
- **Task 5**: `feat(install): interactive client role install script` — `scripts/mesh-install.sh`
- **Task 6**: `feat(deploy): harden container deployment for MVP` — `src/mesh/workloads/`
- **Task 7**: `feat(snapshots): implement create and restore core engine` — `src/mesh/snapshots/`
- **Task 8**: `feat(snapshots): local filesystem storage backend` — `src/mesh/snapshots/`
- **Task 9**: `feat(cli): add mesh snapshot CLI commands` — `src/mesh/cli/commands/`
- **Task 10**: `test(install): 2-VM integration test` — `tests/`
- **Task 11**: `test(e2e): deploy-to-snapshot end-to-end` — `tests/`
- **Task 12**: `chore(cli): remove demo fallbacks from MVP commands` — `src/mesh/cli/commands/`

---

## Success Criteria

### Verification Commands
```bash
# 1. Install script runs
bash scripts/mesh-install.sh  # Interactive, should install server or client role

# 2. Container deployment works
mesh deploy test-app --image nginx:latest  # Expected: deployment successful

# 3. Snapshot works
mesh snapshot create test-app  # Expected: snapshot created
mesh snapshot list             # Expected: lists the snapshot
mesh snapshot restore test-app <id>  # Expected: app restored

# 4. No broken code paths
grep -r "not yet automated" src/mesh/  # Expected: 0 matches
grep -r "return False" src/mesh/workloads/deploy_traefik/  # Expected: file removed

# 5. All tests pass
pytest src/mesh -m "not e2e"  # Expected: all pass
```

### Final Checklist
- [x] Install script provisions server VM with Nomad server + Consul server + Caddy
- [x] Install script provisions client VM with Nomad client + Consul client
- [x] Server and client connect via Tailscale mesh
- [x] `mesh deploy` creates and runs containers on the cluster
- [x] `mesh status` shows real cluster data (not demo)
- [x] `mesh snapshot create` tars container volumes to local disk
- [x] `mesh snapshot restore` restores volumes from tar
- [x] All "Must NOT Have" items are absent from codebase
- [x] All tests pass with TDD coverage
