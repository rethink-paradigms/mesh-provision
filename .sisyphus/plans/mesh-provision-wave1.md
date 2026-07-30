# Wave 1: JSON Mode E2E Verification & Regression Guard

## TL;DR

> **Quick Summary**: Transform JSON output shape to match BRIEF spec, add health-check verification of daemon/Caddy post-provision, add regression tests for JSON/interactive coexistence, and execute a real-DO-token E2E verification.

> **Deliverables**:
> - BRIEF-compliant JSON output shape (`cluster_id`, `leader_ip`, `status`, `nodes`)
> - Health check verification (daemon running, Caddy responding via Caddyfile proxy)
> - Regression test suite (JSON mode + interactive mode coexistence)
> - Destroy JSON shape alignment
> - Real-DO-token E2E evidence

> **Estimated Effort**: Medium (6-8 tasks, ~2 hours)
> **Parallel Execution**: YES — 3 waves, 4+ tasks per wave
> **Critical Path**: Task 1 → Task 2 → Task 4 → Task 7

---

## Context

### Original Request
Wave 1 contracts from `.sisyphus/BRIEF.md`:
1. Verify JSON mode works end-to-end with real DO token
2. Create regression guard that `--output json` doesn't break interactive mode
3. Packaging decision (resolved: already on PyPI, skip)

### Interview Summary
**Key Discussions**:
- **JSON Shape**: Transform current rich nested output to BRIEF flat shape: `{ cluster_id, leader_ip, status, nodes: [{id, ip, role}] }`
- **Status field**: `"ready"` requires health check verification — daemon must be running and Caddy proxy must respond. NOT just "VM provisioned."
- **Test strategy**: TDD with unit tests using mocked DigitalOcean (fast, CI-friendly)
- **Packaging**: Already on PyPI. No publishing work needed.
- **Real DO E2E**: Agent-executed QA scenario, not automated CI test.

**Research Findings**:
- `print_json_success()` calls `sys.exit(0)` — unit tests must mock this or use subprocess-based testing
- No health check exists in the codebase — must be added
- Caddy has no Caddyfile in lite mode — must be generated to proxy daemon health endpoint
- `destroy_resources_direct()` returns Libcloud raw dict — shape is unspecified
- Zero existing tests for JSON mode — gap must be filled

### Metis Review
**Identified Gaps** (addressed):
1. **`sys.exit(0)` kills CliRunner**: All unit tests will mock `print_json_success`/`print_json_error` at module level. Real-output tests use subprocess.
2. **Health check mechanism undefined**: Plan includes Caddyfile generation in boot script (proxy `/health` to daemon on `127.0.0.1:8080`) and post-provision polling on public IP.
3. **Caddy has no Caddyfile**: Plan includes Caddyfile template in daemon install script.
4. **Destroy JSON shape unspecified**: Plan defines flat shape: `{ cluster_id, status: "destroyed", destroyed: true, resources_cleaned: [...] }`
5. **Redundancy in `leader_ip` + `nodes`**: Both present — `leader_ip` for quick parser access, `nodes` for full topology.

---

## Work Objectives

### Core Objective
Transform mesh-provision's JSON mode to produce a BRIEF-compliant output shape with verified health status, backed by regression tests and an E2E verification against a real DigitalOcean token.

### Concrete Deliverables
1. **JSON shape transformation layer** — Pure function that maps current rich dict → BRIEF flat shape
2. **Caddyfile generation** — Template injected into boot script for lite mode health proxy
3. **Health check step** — Post-provision polling on leader public IP with timeout
4. **Regression test suite** — 8+ tests covering JSON mode, interactive mode, and coexistence
5. **Destroy JSON alignment** — Destroy output also produces BRIEF-consistent shape
6. **E2E evidence** — Agent-executed run against real DO token with captured output

### Definition of Done
- [ ] `mesh init --output json --demo --api-key test --leader-size s-2vcpu-4gb --cluster-name test --region nyc3 | python -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ready'; assert 'leader_ip' in d; assert len(d['nodes'])>=1"`
- [ ] `pytest src/mesh/cli/commands/ -v -k "json_mode"` — all pass (8+ tests)
- [ ] `pytest src/mesh/cli/commands/test_init_json.py -v --tb=short` — all pass (6+ tests)
- [ ] `mesh init` (no flags) → interactive prompts work (non-TTY fallback graceful)
- [ ] `mesh destroy --output json --demo --api-key test --cluster test | python -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='destroyed'"`
- [ ] E2E agent-executed: `mesh init --output json --api-key $DO_TOKEN --name e2e-test --region nyc3` produces `status: "ready"` JSON, daemon health endpoint responds, cleanup via destroy

### Must Have
- BRIEF-compliant flat JSON shape for init and destroy
- `status: "ready"` only emitted after daemon health check passes
- All regression tests pass in CI (mock-based, no real DO)
- E2E evidence saved to `.sisyphus/evidence/`

### Must NOT Have (Guardrails)
- **NO** modification to Pulumi provisioning path (`_provision_cloud` in `init_cmd.py`)
- **NO** changes to `init_cmd.py:266` routing logic (high regression risk)
- **NO** new CLI flags added to any command
- **NO** real DO API calls in CI tests
- **NO** SSH key management infrastructure
- **NO** Consul, Tailscale, or multi-node changes (Lite tier only)
- **NO** changes to `json_output.py` public API signatures
- **NO** breaking changes to `run_init_json()` function signature — callers must not need updates

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.

### Test Decision
- **Infrastructure exists**: YES (pytest, pytest-mock, pytest-cov, CliRunner)
- **Automated tests**: TDD — each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR
- **Framework**: pytest with unittest.mock
- **Pattern**: `CliRunner` for CLI integration tests, `@patch` for module-level mocking

### QA Policy
Every task MUST include agent-executed QA scenarios (see TODO template below).
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **CLI**: Use Bash — invoke `mesh` command with arguments, parse JSON from stdout, assert fields
- **API**: Use Bash (curl) — for health endpoint verification after provisioning
- **Unit tests**: Use Bash (pytest) — run test suite, assert pass count

**CRITICAL**: `print_json_success()` calls `sys.exit(0)`. Unit tests MUST mock `print_json_success` and `print_json_error` at the `mesh.cli.commands.init_json` module level. Real-output acceptance tests use `subprocess.run` or direct `bash` invocation.

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.

```
Wave 1 (Start Immediately — foundation + test infrastructure):
├── Task 1: JSON shape transform function + unit tests [quick]
├── Task 2: Caddyfile generation + daemon boot script update [quick]
├── Task 3: Health check step in init_json.py [quick]
└── Task 4: Destroy JSON shape alignment [quick]

Wave 2 (After Wave 1 — regression tests, MAX PARALLEL):
├── Task 5: JSON mode regression test suite [quick]
├── Task 6: Interactive mode non-regression tests [quick]
└── Task 7: Integration test for health check + transform [quick]

Wave 3 (After Wave 2 — E2E verification):
└── Task 8: Real DO token E2E verification (agent-executed QA) [unspecified-high]

Wave FINAL (After ALL tasks):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

**Critical Path**: Task 1 → Task 2 → Task 4 → Task 7 → Task 8
**Parallel Speedup**: ~50% faster than sequential (Tasks 1-4 in parallel)
**Max Concurrent**: 4 (Wave 1)

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | 5, 7 | 1 |
| 2 | — | 3, 8 | 1 |
| 3 | 2 | 7, 8 | 1 |
| 4 | — | 5, 7 | 1 |
| 5 | 1, 4 | — | 2 |
| 6 | — | — | 2 |
| 7 | 1, 3, 4 | 8 | 2 |
| 8 | 7 | F1-F4 | 3 |
| F1-F4 | 8 | — | FINAL |

### Agent Dispatch Summary

| Wave | Count | Profiles |
|------|-------|----------|
| 1 | 4 | T1-T4 → `quick` |
| 2 | 3 | T5-T7 → `quick` |
| 3 | 1 | T8 → `unspecified-high` (real DO, needs careful execution) |
| FINAL | 4 | F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep` |

---

## TODOs

- [x] 1. JSON Shape Transformation Function

  **What to do**:
  - Create a pure function `to_brief_shape(result: dict) -> dict` in `json_output.py` that transforms the current rich JSON output into the BRIEF-specified flat shape:
    ```json
    {
      "cluster_id": "...",
      "leader_ip": "...",
      "status": "ready",
      "nodes": [{"id": "...", "ip": "...", "role": "leader"}, {"id": "...", "ip": "...", "role": "worker"}, ...]
    }
    ```
  - Mapping rules:
    - `cluster_id` → passthrough (already present)
    - `leader_ip` → extract from `leader.ip` (handle empty string case: fallback to `leader.private_ip`, then `""`)
    - `status` → `"ready"` (hardcoded for now; health check plumbing in Task 3)
    - `nodes` → collect `leader` + `workers` into a unified array:
      - Leader: `{ "id": leader.id, "ip": leader.ip, "role": "leader" }`
      - Each worker: `{ "id": w.id, "ip": w.ip, "role": "worker" }`
      - Filter out nodes where both id and ip are empty strings
  - Write unit test file `src/mesh/cli/commands/test_json_output.py`:
    - Test `to_brief_shape` with a realistic rich dict → assert flat shape fields
    - Test with empty IPs (leader has no public_ip, falls back to private_ip)
    - Test with 0 workers → nodes array has only leader
    - Test with 3 workers → nodes array has 4 entries (1 leader + 3 workers)
    - Test that `cluster_id` is preserved
    - **CRITICAL**: Do NOT import `print_json_success` or `print_json_error` in these tests — they call `sys.exit()`. Test `to_brief_shape` as a pure function only.
  - Run: `pytest src/mesh/cli/commands/test_json_output.py -v --tb=short` → 5 tests pass

  **Must NOT do**:
  - Do NOT change the `print_json_success()` or `print_json_error()` function signatures
  - Do NOT add `sys.exit()` calls to `to_brief_shape` (it's a pure function)
  - Do NOT modify `run_init_json()` in this task (that's Task 4 integration)
  - Do NOT touch any Pulumi code path

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - **Reason**: Single file change (json_output.py) + new test file. Pure function, well-defined mapping.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 5, 7
  - **Blocked By**: None

  **References**:
  - `src/mesh/cli/commands/json_output.py:40-51` — `print_json_success()` signature (do NOT modify)
  - `src/mesh/cli/commands/json_output.py:180-204` — `build_demo_init_json()` — current rich shape that needs transforming
  - `src/mesh/cli/commands/init_json.py:170-193` — where `result` dict is built in `run_init_json()` — this is the input to `to_brief_shape`
  - `src/mesh/cli/commands/test_snapshot_cmd.py` — CliRunner test pattern to follow
  - `conftest.py` — pythonpath setup for imports

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: `src/mesh/cli/commands/test_json_output.py`
  - [ ] `pytest src/mesh/cli/commands/test_json_output.py -v --tb=short` → 5 passed, 0 failed
  - [ ] `to_brief_shape` function exists in `json_output.py` with docstring

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Happy path — rich dict with all fields → flat BRIEF shape
    Tool: Bash
    Preconditions: `to_brief_shape` imported and callable
    Steps:
      1. Run: python3 -c "
         import json, sys
         sys.path.insert(0, 'src')
         from mesh.cli.commands.json_output import to_brief_shape
         rich = {
             'cluster_id': 'test-cluster',
             'provider': 'digitalocean',
             'region': 'nyc3',
             'tier': 'lite',
             'leader': {'ip': '164.90.123.45', 'id': 'droplet-abc', 'size': 's-2vcpu-4gb'},
             'workers': [
                 {'ip': '164.90.123.46', 'id': 'droplet-def', 'size': 's-1vcpu-1gb'}
             ],
             'nomad_addr': 'http://127.0.0.1:4646',
             'daemon_url': 'https://daemon-test.agentbodies.com',
             'daemon_token': 'tok123',
             'caddy_admin': 'http://127.0.0.1:2019',
             'created_at': '2026-05-06T12:00:00Z'
         }
         flat = to_brief_shape(rich)
         print(json.dumps(flat, indent=2))
         assert flat['cluster_id'] == 'test-cluster'
         assert flat['leader_ip'] == '164.90.123.45'
         assert flat['status'] == 'ready'
         assert len(flat['nodes']) == 2
         assert flat['nodes'][0]['role'] == 'leader'
         assert flat['nodes'][1]['role'] == 'worker'
         print('ALL ASSERTIONS PASSED')
         "
      2. Assert exit code 0
    Expected Result: "ALL ASSERTIONS PASSED" printed, exit code 0
    Failure Indicators: Any `AssertionError`, non-zero exit code
    Evidence: .sisyphus/evidence/task-1-happy-path.txt

  Scenario: Edge case — empty IPs, 0 workers
    Tool: Bash
    Preconditions: `to_brief_shape` callable
    Steps:
      1. Run python3 -c with rich dict where leader has empty `ip` and no `workers`
      2. Assert `flat['leader_ip']` is empty string (not None)
      3. Assert `flat['nodes']` has exactly 1 entry (leader only)
    Expected Result: No crash, valid output with empty IP
    Evidence: .sisyphus/evidence/task-1-edge-empty.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-1-happy-path.txt` — happy path assertion output
  - [ ] `.sisyphus/evidence/task-1-edge-empty.txt` — edge case assertion output

  **Commit**: YES
  - Message: `feat(json): add to_brief_shape transform for BRIEF-compliant output`
  - Files: `src/mesh/cli/commands/json_output.py`, `src/mesh/cli/commands/test_json_output.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_json_output.py -v --tb=short`

- [x] 2. Caddyfile Generation for Health Check Proxy

  **What to do**:
  - In `11-install-daemon.sh`, add a step BEFORE starting Caddy that writes a Caddyfile to `/etc/caddy/Caddyfile`:
    ```
    :80 {
      reverse_proxy /health localhost:8080
      respond "mesh-provision OK" 200
    }
    ```
    This makes Caddy listen on port 80, proxy `/health` to the daemon's health endpoint at `127.0.0.1:8080`, and serve a simple OK response at `/`.
  - Ensure `mkdir -p /etc/caddy` runs before writing
  - Ensure Caddy config validation: `caddy validate --config /etc/caddy/Caddyfile` 
  - Restart Caddy after writing config: `systemctl restart caddy`
  - Update the boot script template (`boot.sh`) if needed to pass any additional variables
  - **Lite mode only**: Gate this step on `CLUSTER_TIER == "lite"` since standard tiers use Traefik

  **Must NOT do**:
  - Do NOT modify `boot.sh` template structure beyond passing existing variables
  - Do NOT add new environment variables or CLI flags
  - Do NOT change the daemon binary download or config

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - **Reason**: Single shell script edit, well-scoped change.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 3, 8
  - **Blocked By**: None

  **References**:
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh` — daemon install script to modify
  - `src/mesh/infrastructure/boot_consul_nomad/boot.sh:100-105` — template gating daemon install
  - `src/mesh/cli/commands/init_json.py:86` — `tier` variable defined (lite vs standard)
  - `src/mesh/cli/commands/json_output.py:201` — `caddy_admin` hardcoded to `http://127.0.0.1:2019`

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] `pytest src/mesh/infrastructure/boot_consul_nomad/test_boot.py -v --tb=short` → existing tests still pass (boot script generation unchanged for non-daemon paths)
  - [ ] Verify: `grep -n "Caddyfile" src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh` returns at least 3 lines (mkdir, write, validate)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Verify Caddyfile content in boot script
    Tool: Bash
    Preconditions: Caddyfile lines exist in 11-install-daemon.sh
    Steps:
      1. grep "reverse_proxy /health localhost:8080" src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh
      2. Assert match found
      3. grep "caddy validate" src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh
      4. Assert match found
    Expected Result: Both grep commands find matches
    Failure Indicators: Missing Caddyfile write, missing validate step
    Evidence: .sisyphus/evidence/task-2-caddyfile.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-2-caddyfile.txt` — grep output showing Caddyfile content

  **Commit**: YES
  - Message: `feat(daemon): add Caddyfile generation for lite-mode health proxy`
  - Files: `src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh`
  - Pre-commit: `grep -q "reverse_proxy /health" src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh`

- [x] 3. Health Check Step in init_json.py

  **What to do**:
  - After `provision_cluster_direct()` returns in `init_json.py:run_init_json()`, add a health check polling loop:
    1. Extract leader's public IP from `cluster_result["leader"]["public_ip"]`
    2. If no public IP, skip health check and set `status = "provisioned"`
    3. Poll `http://{leader_ip}:80/health` with `requests.get()` (Caddy proxies to daemon on `127.0.0.1:8080`)
    4. Timeout: 120 seconds (same as `_poll_for_ip` in `provision_direct.py`), interval: 5 seconds
    5. On success (HTTP 200): set `status = "ready"`
    6. On timeout: set `status = "provisioned"` (VM is up but daemon/Caddy not verified yet)
    7. Do NOT fail or exit on health check timeout — `status` field communicates the actual state
  - Write unit test file `src/mesh/cli/commands/test_init_json_health.py`:
    - Test with mock `provision_cluster_direct` returning valid public IP, mock `requests.get` returning HTTP 200 → `status = "ready"`
    - Test with mock `provision_cluster_direct` returning valid public IP, mock `requests.get` raising `ConnectionError` → `status = "provisioned"` after retries
    - Test with no public IP → skip health check, `status = "provisioned"`
    - Test with mock `requests.get` returning 503 → retry, eventually `status = "provisioned"` after timeout
    - **CRITICAL**: Mock `print_json_success` and `print_json_error` at module level (`patch("mesh.cli.commands.init_json.print_json_success")`) to catch the output without `sys.exit()` killing the test
    - Assert the mocked `print_json_success` was called with a dict where `result["status"]` is correct

  **Must NOT do**:
  - Do NOT fail/exit on health check timeout (communicate via `status` field)
  - Do NOT add SSH or key management
  - Do NOT change the CLI flags or routing logic
  - Do NOT call `print_json_error` for health check failures (use `status` field)
  - Do NOT mock at function level — mock at module level to catch actual `init_json` output

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - **Reason**: Single file edit (init_json.py) + new test file. Polling logic is straightforward.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: Task 2 (needs Caddyfile so health endpoint actually exists)

  **References**:
  - `src/mesh/cli/commands/init_json.py:146-165` — where `provision_cluster_direct()` is called; add health check after this try block
  - `src/mesh/cli/commands/init_json.py:170-193` — where `result` dict is built; `status` field needs to come from health check
  - `src/mesh/infrastructure/provision_node/provision_direct.py:96-141` — `_poll_for_ip()` pattern (timeout/interval polling) to replicate
  - `src/mesh/cli/commands/test_deploy_hardening.py` — mock pattern with `@patch` at module level
  - `src/mesh/cli/commands/json_output.py:40-51` — `print_json_success` calls `sys.exit(0)` — must mock this

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: `src/mesh/cli/commands/test_init_json_health.py`
  - [ ] `pytest src/mesh/cli/commands/test_init_json_health.py -v --tb=short` → 4 passed, 0 failed

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Health check succeeds — status is "ready"
    Tool: Bash
    Preconditions: Test environment with mock setup
    Steps:
      1. Run: pytest src/mesh/cli/commands/test_init_json_health.py::test_health_check_success -v --tb=long
      2. Assert exit code 0
      3. Assert test name contains "health_check_success"
    Expected Result: Test passes, confirming health-check-success path produces status="ready"
    Evidence: .sisyphus/evidence/task-3-health-success.txt

  Scenario: Health check fails — status is "provisioned"
    Tool: Bash
    Preconditions: Test environment with mock setup
    Steps:
      1. Run: pytest src/mesh/cli/commands/test_init_json_health.py::test_health_check_failure -v --tb=long
      2. Assert exit code 0
    Expected Result: Test passes, confirming health-check-failure path produces status="provisioned"
    Evidence: .sisyphus/evidence/task-3-health-failure.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-3-health-success.txt` — test output for success path
  - [ ] `.sisyphus/evidence/task-3-health-failure.txt` — test output for failure path

  **Commit**: YES
  - Message: `feat(json): add post-provision health check with status field`
  - Files: `src/mesh/cli/commands/init_json.py`, `src/mesh/cli/commands/test_init_json_health.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_init_json_health.py -v --tb=short`

- [x] 4. Destroy JSON Shape Alignment

  **What to do**:
  - Create a `to_brief_destroy_shape(result: dict, cluster_name: str) -> dict` function in `json_output.py`:
    ```json
    {
      "cluster_id": "...",
      "status": "destroyed",
      "destroyed": true,
      "resources_cleaned": ["droplet-id-1", "..."]
    }
    ```
  - Update `_run_destroy_json()` in `destroy.py` to:
    1. Call existing `destroy_resources_direct()` 
    2. Transform result through `to_brief_destroy_shape()`
    3. Pass to `print_json_success()`
  - Update `build_demo_destroy_json()` in `json_output.py` to match the flat shape (add `cluster_id` and `status` fields if missing — currently has `cluster_id`, `destroyed`, `resources_cleaned`, `demo` — just needs `status: "destroyed"`)
  - Write unit tests in `test_json_output.py`:
    - Test `to_brief_destroy_shape` with realistic Libcloud result
    - Test with empty `resources_cleaned` array
    - Test that `destroyed` is always `true`

  **Must NOT do**:
  - Do NOT change `destroy_resources_direct()` interface
  - Do NOT change the `print_json_success()` signature
  - Do NOT remove the `demo` field from demo mode (just add `status` alongside it)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - **Reason**: Small function + single file edit + 2 test cases. Well-defined transform.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Tasks 5, 7
  - **Blocked By**: None

  **References**:
  - `src/mesh/cli/commands/destroy.py:24-65` — `_run_destroy_json()` current implementation
  - `src/mesh/cli/commands/json_output.py:207-225` — `build_demo_destroy_json()` current shape
  - `src/mesh/cli/commands/json_output.py:40-51` — `print_json_success()` (do NOT modify)
  - `src/mesh/infrastructure/provision_node/provision_direct.py:323-374` — `destroy_resources_direct()` return shape

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Tests added to `src/mesh/cli/commands/test_json_output.py`
  - [ ] `pytest src/mesh/cli/commands/test_json_output.py -v -k "destroy" --tb=short` → 3 passed, 0 failed

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Destroy JSON produces BRIEF shape (demo mode)
    Tool: Bash
    Preconditions: Virtual env active, package installed in dev mode
    Steps:
      1. Run: mesh destroy --output json --demo --api-key test123 --cluster test-brief
      2. Parse JSON from stdout
      3. Assert `cluster_id` is "test-brief"
      4. Assert `status` is "destroyed"
      5. Assert `destroyed` is true
      6. Assert `resources_cleaned` is an array
    Expected Result: All assertions pass, JSON valid
    Failure Indicators: Missing status field, non-JSON output, crash
    Evidence: .sisyphus/evidence/task-4-destroy-brief.json
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-4-destroy-brief.json` — captured JSON output

  **Commit**: YES (groups with Task 1)
  - Message: `feat(json): align destroy output with BRIEF flat shape`
  - Files: `src/mesh/cli/commands/json_output.py`, `src/mesh/cli/commands/destroy.py`, `src/mesh/cli/commands/test_json_output.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_json_output.py -v -k "destroy" --tb=short`

- [x] 5. JSON Mode Regression Test Suite

  **What to do**:
  - Create test file `src/mesh/cli/commands/test_init_json.py` with CliRunner tests:
    1. `test_init_json_demo_produces_brief_shape` — `CliRunner.invoke(app, ["init", "--output", "json", "--demo", "--api-key", "test123", "--leader-size", "s-2vcpu-4gb", "--cluster-name", "test-regr", "--region", "nyc3"])` → mock `print_json_success`, assert called with flat shape
    2. `test_init_json_demo_exits_0` — same invocation, assert `result.exit_code == 0`
    3. `test_init_json_missing_args_produces_error` — invoke without required args (no `--api-key`, no `--leader-size`), assert `print_json_error` called with `code="missing_required_args"`
    4. `test_init_json_demo_no_rich_output` — assert Rich panel text (e.g., "Cluster Configuration") is NOT in stdout when `--output json`
    5. `test_init_json_demo_leader_ip_present` — assert `leader_ip` field exists and is a non-empty string
    6. `test_init_json_demo_nodes_has_leader_role` — assert `nodes` array has at least 1 entry, first entry has `role: "leader"`
  - Create test file `src/mesh/cli/commands/test_destroy_json.py`:
    1. `test_destroy_json_demo_produces_brief_shape` — `CliRunner.invoke(app, ["destroy", "--output", "json", "--demo", "--api-key", "test123"])` → mock `print_json_success`, assert flat shape with `status: "destroyed"`
    2. `test_destroy_json_demo_exits_0` — same, assert exit code 0
  - **CRITICAL**: All tests MUST mock `print_json_success` and `print_json_error` at the relevant module level (e.g., `patch("mesh.cli.commands.init_json.print_json_success")`) to prevent `sys.exit()` from killing the test runner.

  **Must NOT do**:
  - Do NOT use real DO API calls — all tests are demo mode or mocked
  - Do NOT import `print_json_success` directly in test code (mock it instead)
  - Do NOT call `result.stdout` directly for JSON — `print_json_success` writes to `sys.stdout` and then exits, so `CliRunner.stdout` may be empty. Assert on the mock call instead.

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - **Reason**: 8 test functions across 2 files, following established CliRunner patterns. Well-understood scope.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7)
  - **Blocks**: None
  - **Blocked By**: Tasks 1, 4 (needs `to_brief_shape` and destroy alignment)

  **References**:
  - `src/mesh/cli/commands/test_snapshot_cmd.py` — CliRunner test pattern (module-level `runner = CliRunner()`)
  - `src/mesh/cli/commands/test_doctor.py` — Another CliRunner test example
  - `src/mesh/cli/main.py:59-117` — `init` command definition with all flags
  - `src/mesh/cli/main.py:140-163` — `destroy` command definition
  - `src/mesh/cli/commands/init_json.py:53-74` — `run_init_json()` signature to understand required args
  - `src/mesh/cli/commands/json_output.py:40-51` — `print_json_success()` — the mock target

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test files created: `src/mesh/cli/commands/test_init_json.py` (6 tests), `src/mesh/cli/commands/test_destroy_json.py` (2 tests)
  - [ ] `pytest src/mesh/cli/commands/test_init_json.py src/mesh/cli/commands/test_destroy_json.py -v --tb=short` → 8 passed, 0 failed

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full test suite passes
    Tool: Bash
    Preconditions: All mock setup correct
    Steps:
      1. Run: pytest src/mesh/cli/commands/test_init_json.py src/mesh/cli/commands/test_destroy_json.py -v --tb=short --no-header
      2. Assert exit code 0
      3. Assert at least 8 tests, 0 failures, 0 errors
    Expected Result: Green test run with full pass
    Evidence: .sisyphus/evidence/task-5-test-suite.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-5-test-suite.txt` — full pytest output

  **Commit**: YES
  - Message: `test(json): add regression tests for JSON mode (init + destroy)`
  - Files: `src/mesh/cli/commands/test_init_json.py`, `src/mesh/cli/commands/test_destroy_json.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_init_json.py src/mesh/cli/commands/test_destroy_json.py -v --tb=short`

- [x] 6. Interactive Mode Non-Regression Tests

  **What to do**:
  - Create test file `src/mesh/cli/commands/test_interactive_regression.py`:
    1. `test_init_no_flags_non_tty_graceful` — `CliRunner.invoke(app, ["init"])` without TTY → assert graceful exit, no crash, error message about non-interactive terminal
    2. `test_init_demo_yes_rich_output` — `CliRunner.invoke(app, ["init", "--demo", "--yes"])` → assert exit 0, assert Rich output present (e.g., "Cluster is ready!" text in output)
    3. `test_init_demo_yes_no_json_output` — same invocation, assert JSON fields NOT present in output (e.g., no `"cluster_id":` in stdout)
    4. `test_init_json_demo_no_rich_output` — `CliRunner.invoke(app, ["init", "--output", "json", "--demo", "--api-key", "test123", "--leader-size", "s-2vcpu-4gb", "--cluster-name", "regr", "--region", "nyc3"])` → mock `print_json_success`, assert Rich "Cluster Configuration" NOT in output
    5. `test_destroy_no_flags_non_tty_graceful` — `CliRunner.invoke(app, ["destroy"])` → assert graceful handling (either exit 0 with message or exit 1 with "non-interactive")
    6. `test_destroy_json_no_rich_output` — `CliRunner.invoke(app, ["destroy", "--output", "json", "--demo", "--api-key", "test123"])` → mock `print_json_success`, assert no Rich/Questionary text in output
  - Tests 1, 2, 3, 5 can use direct `result.output` assertions since interactive mode doesn't call `sys.exit()`.
  - Tests 4, 6 MUST mock `print_json_success`/`print_json_error` at module level.

  **Must NOT do**:
  - Do NOT actually run interactive Questionary prompts (they hang in CliRunner without TTY)
  - Do NOT add `--yes` flags to destroy tests that shouldn't need them
  - Do NOT test JSON output shape here (that's Task 5's responsibility)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - **Reason**: New test file with 6 test functions. Follows existing CliRunner patterns.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7)
  - **Blocks**: None
  - **Blocked By**: None (tests existing code paths, no new implementation needed)

  **References**:
  - `src/mesh/cli/commands/init_cmd.py:246-280` — `run_init()` routing logic (line 266 is the JSON gate)
  - `src/mesh/cli/commands/destroy.py:68-78` — `run_destroy()` routing logic (line 76 is the JSON gate)
  - `src/mesh/cli/commands/destroy.py:96-100` — TTY guard: `if not sys.stdin.isatty()` 
  - `src/mesh/cli/commands/test_snapshot_cmd.py:194` — CliRunner pattern
  - `src/mesh/cli/ui/panels.py` — Rich UI text strings to assert on (e.g., "Cluster Configuration", "Cluster is ready!")

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: `src/mesh/cli/commands/test_interactive_regression.py`
  - [ ] `pytest src/mesh/cli/commands/test_interactive_regression.py -v --tb=short` → 6 passed, 0 failed

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Interactive and JSON modes don't cross-contaminate
    Tool: Bash
    Preconditions: Test file exists
    Steps:
      1. Run: pytest src/mesh/cli/commands/test_interactive_regression.py -v --tb=short --no-header
      2. Assert exit code 0
      3. Assert all 6 tests pass
    Expected Result: All regression tests green
    Evidence: .sisyphus/evidence/task-6-regression.txt
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-6-regression.txt` — full pytest output

  **Commit**: YES
  - Message: `test(regression): verify JSON mode does not break interactive mode`
  - Files: `src/mesh/cli/commands/test_interactive_regression.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_interactive_regression.py -v --tb=short`

- [x] 7. Integration: Wire Transform + Health Check into run_init_json

  **What to do**:
  - In `run_init_json()` (`init_json.py`), after the `provision_cluster_direct()` try block and health check (Task 3):
    1. Apply `to_brief_shape()` to the result dict
    2. Inject the `status` field from health check result (overriding `to_brief_shape`'s hardcoded `"ready"`)
    3. Pass the transformed dict to `print_json_success()`
  - Also apply `to_brief_shape()` to `build_demo_init_json()` result in the demo path
  - Update the demo result function `build_demo_init_json()` to produce the flat BRIEF shape directly instead of the current rich shape (OR add a transform call in the demo path)
  - Update `to_brief_shape()` in `json_output.py` to accept an optional `status` parameter:
    ```python
    def to_brief_shape(result: dict, status: str = "ready") -> dict
    ```
    So the health check result can override the default `"ready"`.
  - Ensure demo mode still produces the flat BRIEF shape
  - Write an integration test:
    - `test_init_json_full_flow_demo` — `run_init_json(demo=True, ...)` with mocked `print_json_success`, assert the mock received flat BRIEF shape
    - `test_init_json_full_flow_real_mocked` — mock `provision_cluster_direct` returning fake VM, mock `requests.get` returning 200, assert `print_json_success` called with flat shape where `status == "ready"`

  **Must NOT do**:
  - Do NOT break demo mode — it must still work
  - Do NOT change `run_init_json()` function signature (callers must not need updates)
  - Do NOT call `print_json_success` before transformation completes

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - **Reason**: Wiring existing pieces together. 2 file edits, 2 new integration tests.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Wave 2, runs after 1-3-4)
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 1, 3, 4 (needs transform function, health check, and destroy alignment)

  **References**:
  - `src/mesh/cli/commands/init_json.py:53-195` — full `run_init_json()` to integrate into
  - `src/mesh/cli/commands/init_json.py:65-74` — demo path (needs transform applied)
  - `src/mesh/cli/commands/init_json.py:146-165` — provisioning path with health check (Task 3) added
  - `src/mesh/cli/commands/init_json.py:170-193` — result dict construction (to be replaced by `to_brief_shape()` call)
  - `src/mesh/cli/commands/json_output.py:179-204` — `build_demo_init_json()` (update to flat shape)
  - `src/mesh/cli/commands/json_output.py` — `to_brief_shape()` function (Task 1)

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Integration tests added to `src/mesh/cli/commands/test_init_json.py`
  - [ ] `pytest src/mesh/cli/commands/test_init_json.py -v -k "full_flow" --tb=short` → 2 passed, 0 failed
  - [ ] `mesh init --output json --demo --api-key test123 --leader-size s-2vcpu-4gb --cluster-name int-test --region nyc3 | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ready'; assert 'leader_ip' in d; assert len(d['nodes'])>=1; print('INTEGRATION PASSED')"` → prints "INTEGRATION PASSED"

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full init pipeline produces BRIEF shape (demo mode)
    Tool: Bash
    Preconditions: Virtual env active, package installed in dev mode
    Steps:
      1. Run: mesh init --output json --demo --api-key test123 --leader-size s-2vcpu-4gb --cluster-name integrate --region nyc3
      2. Capture stdout
      3. Parse: python3 -c "
         import json, sys
         d = json.load(sys.stdin)
         assert d['cluster_id'] == 'integrate'
         assert d['status'] in ('ready', 'provisioned')
         assert d['leader_ip'] is not None
         assert len(d['nodes']) >= 1
         assert d['nodes'][0]['role'] == 'leader'
         for field in ('provider', 'region', 'tier', 'nomad_addr', 'daemon_url', 'daemon_token', 'caddy_admin'):
             assert field not in d, f'Rich field {field} leaked into flat shape'
         print('FULL PIPELINE PASSED')
         "
    Expected Result: "FULL PIPELINE PASSED" printed
    Failure Indicators: Rich fields leaking, missing status, non-JSON output
    Evidence: .sisyphus/evidence/task-7-integration.json
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-7-integration.json` — captured JSON output

  **Commit**: YES
  - Message: `feat(json): wire BRIEF transform and health check into init pipeline`
  - Files: `src/mesh/cli/commands/init_json.py`, `src/mesh/cli/commands/json_output.py`, `src/mesh/cli/commands/test_init_json.py`
  - Pre-commit: `mesh init --output json --demo --api-key test123 --leader-size s-2vcpu-4gb --cluster-name precommit --region nyc3 | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status'] in ('ready','provisioned')"`

- [x] 8. Real DO Token E2E Verification (Agent-Executed QA) — **BLOCKED: Invalid DO token** (see `.sisyphus/notepads/mesh-provision-wave1/issues.md` for resolution)

  **What to do**:
  - Execute a full E2E flow against a REAL DigitalOcean token:
    1. Export token: `export DIGITALOCEAN_API_TOKEN="<real DO token from user>"`
     2. Provision: `mesh init --output json --api-key "$DIGITALOCEAN_API_TOKEN" --region nyc3 --leader-size s-1vcpu-1gb --cluster-name "e2e-wave1-$(date +%s)"`
    3. Parse stdout JSON with `jq`:
       - Assert `.cluster_id` is non-empty
       - Assert `.status` is `"ready"` (NOT `"provisioned"` — health check must pass)
       - Assert `.leader_ip` is a valid IPv4
       - Assert `.nodes | length >= 1`
       - Assert `.nodes[0].role == "leader"` 
    4. Extract `leader_ip` and curl the health endpoint: `curl -s http://<leader_ip>/health`
       - Assert HTTP 200 and response contains daemon health info OR the Caddy OK message
    5. Wait 60s for boot script to complete, then curl again to verify persistence
    6. Destroy: `mesh destroy --output json --api-key "$DIGITALOCEAN_API_TOKEN" --cluster e2e-wave1-<timestamp>`
       - Parse JSON: assert `.status == "destroyed"`, assert `.destroyed == true`
  - Save ALL evidence:
    - `.sisyphus/evidence/task-8-init-output.json` — raw init JSON output
    - `.sisyphus/evidence/task-8-health-curl.txt` — curl response from health endpoint
    - `.sisyphus/evidence/task-8-destroy-output.json` — raw destroy JSON output
    - `.sisyphus/evidence/task-8-summary.md` — summary of pass/fail with timestamps
  - Clean up on failure: if init succeeds but health check fails, still run destroy to prevent orphaned droplets

  **Must NOT do**:
  - Do NOT commit real DO tokens to the repo
  - Do NOT run this in CI (manual/agent gate only)
  - Do NOT leave orphaned droplets (always cleanup)
  - Do NOT use sizes larger than `s-1vcpu-1gb` (minimize cost)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `[]`
  - **Reason**: Real cloud provisioning, polling, cleanup. Needs careful execution and error handling.

  **Parallelization**:
  - **Can Run In Parallel**: NO 
  - **Parallel Group**: Wave 3 (sequential, runs after all implementation)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 7 (all features wired up)

  **References**:
  - `src/mesh/cli/commands/init_json.py:53-195` — `run_init_json()` full flow
  - `src/mesh/infrastructure/provision_node/provision_direct.py:149-253` — `provision_node_direct()` — understands the provisioning mechanics
  - `src/mesh/infrastructure/config/env.py:30` — `DIGITALOCEAN_API_TOKEN` env var name
  - `.sisyphus/BRIEF.md:31-45` — Expected JSON output spec from BRIEF

  **Acceptance Criteria**:
  - [ ] `.sisyphus/evidence/task-8-init-output.json` exists with valid JSON
  - [ ] `.sisyphus/evidence/task-8-init-output.json` `.status` is `"ready"`
  - [ ] `.sisyphus/evidence/task-8-health-curl.txt` exists with HTTP 200 response
  - [ ] `.sisyphus/evidence/task-8-destroy-output.json` exists with `.status == "destroyed"`
  - [ ] Zero orphaned DigitalOcean droplets (verified via DO dashboard or API)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full E2E — provision, verify health, destroy (real DO token)
    Tool: Bash (curl + mesh CLI)
    Preconditions: $DIGITALOCEAN_API_TOKEN set, mesh CLI installed
    Steps:
      1. TS=$(date +%s) && echo "Timestamp: $TS" > /tmp/e2e-timestamp.txt
      2. mesh init --output json --api-key "$DIGITALOCEAN_API_TOKEN" --region nyc3 --leader-size s-1vcpu-1gb --cluster-name "e2e-$TS" > .sisyphus/evidence/task-8-init-output.json 2>.sisyphus/evidence/task-8-init-stderr.txt
      3. cat .sisyphus/evidence/task-8-init-output.json | python3 -c "
         import json, sys
         d = json.load(sys.stdin)
         assert d['status'] == 'ready', f'Expected ready, got {d.get(\"status\")}'
         assert d['leader_ip'], 'leader_ip is empty'
         print(d['leader_ip'])
         " > /tmp/leader-ip.txt
      4. LEADER_IP=$(cat /tmp/leader-ip.txt) && echo "Leader IP: $LEADER_IP"
      5. sleep 60 && curl -s --max-time 30 "http://$LEADER_IP/health" -o .sisyphus/evidence/task-8-health-curl.txt -w "%{http_code}" > /tmp/health-code.txt
      6. HEALTH_CODE=$(cat /tmp/health-code.txt) && echo "Health code: $HEALTH_CODE"
      7. [ "$HEALTH_CODE" = "200" ] && echo "HEALTH CHECK PASSED" || echo "HEALTH CHECK FAILED (code=$HEALTH_CODE)"
      8. mesh destroy --output json --api-key "$DIGITALOCEAN_API_TOKEN" --cluster "e2e-$TS" > .sisyphus/evidence/task-8-destroy-output.json
      9. cat .sisyphus/evidence/task-8-destroy-output.json | python3 -c "
         import json, sys
         d = json.load(sys.stdin)
         assert d['status'] == 'destroyed', f'Expected destroyed, got {d.get(\"status\")}'
         "
    Expected Result: All steps pass. Init JSON has status="ready". Health curl returns 200. Destroy JSON has status="destroyed".
    Failure Indicators: status != "ready", health curl timeout/error, orphaned droplet
    Failure Recovery: Run destroy command manually if step 8 fails
    Evidence: 
      - .sisyphus/evidence/task-8-init-output.json
      - .sisyphus/evidence/task-8-init-stderr.txt
      - .sisyphus/evidence/task-8-health-curl.txt
      - .sisyphus/evidence/task-8-destroy-output.json
  ```

  **Evidence to Capture**:
  - [ ] `.sisyphus/evidence/task-8-init-output.json` — raw init JSON
  - [ ] `.sisyphus/evidence/task-8-init-stderr.txt` — any stderr output during init
  - [ ] `.sisyphus/evidence/task-8-health-curl.txt` — health endpoint response
  - [ ] `.sisyphus/evidence/task-8-destroy-output.json` — raw destroy JSON
  - [ ] `.sisyphus/evidence/task-8-summary.md` — execution summary

  **Commit**: NO (evidence only, no code changes)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
>
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check src/mesh/cli/commands/` + `pytest src/mesh/cli/commands/ -v -k "json_mode or test_init_json or test_destroy_json or test_json_output or test_interactive_regression or test_init_json_health" --tb=short`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (features working together, not isolation). Test edge cases: empty IP, 0 workers, missing args. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(json): add BRIEF-compliant output shape and health check` — `src/mesh/cli/commands/json_output.py`, `src/mesh/cli/commands/init_json.py`, `scripts/11-install-daemon.sh`
- **Wave 2**: `test(json): add regression tests for JSON and interactive modes` — `src/mesh/cli/commands/test_init_json.py`, `src/mesh/cli/commands/test_destroy_json.py`
- **Wave 3**: `test(e2e): real DO token verification evidence` — `.sisyphus/evidence/`

---

## Success Criteria

### Verification Commands
```bash
# Unit tests pass (mocked DO)
pytest src/mesh/cli/commands/test_init_json.py -v --tb=short --no-header
# Expected: 6-8 passed, 0 failed

pytest src/mesh/cli/commands/ -v -k "json_mode" --tb=short --no-header
# Expected: 8-10 passed, 0 failed

# JSON output shape verification (demo mode)
mesh init --output json --demo --api-key test123 --leader-size s-2vcpu-4gb --cluster-name verify --region nyc3 | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['cluster_id'] == 'verify'
assert d['status'] == 'ready'
assert 'leader_ip' in d
assert len(d['nodes']) >= 1
assert d['nodes'][0]['role'] == 'leader'
print('PASS: JSON shape valid')
"
# Expected: PASS: JSON shape valid

# Destroy JSON shape verification (demo mode)
mesh destroy --output json --demo --api-key test123 --cluster verify | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['status'] == 'destroyed'
assert d['destroyed'] == True
print('PASS: Destroy JSON shape valid')
"
# Expected: PASS: Destroy JSON shape valid
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] E2E evidence captured
