# Draft: JSON Mode E2E Verification & Regression Guards

## Requirements (confirmed from BRIEF)

### Wave 1 Contracts
1. **JSON Mode E2E Verification**: Run `mesh init --output json --api-key $DO_TOKEN --name test-cluster --region nyc3` with real token, verify response shape matches central service parser, verify daemon installed + Caddy running + health endpoint responds.
2. **Regression Guard**: Ensure `--output json` doesn't break interactive mode (`mesh init` without flags → interactive prompts work; both paths coexist).
3. **Packaging Decision**: Document Option A (PyPI package) vs Option B (inline script) — leaning Option B for MVP.

### Constraints
- Python 3.11+, package `rethink-mesh` v0.4.0
- CLI via Typer + Questionary (interactive) or `--output json` (machine)
- All env vars from `os.environ` (loaded by direnv from root `.env`)
- Subprocess model: invoke-and-die, 2-5 min runtime
- MVP: DigitalOcean only, Lite tier only (single droplet)
- CI: ruff lint, pytest (excludes e2e/cloud tests)
- **No new features** — JSON mode and daemon install are complete

### Open Questions
- Should mesh-provision be published to PyPI now or post-MVP?
- Does JSON output schema need fields for error states?

---

## Technical Decisions
- _pending interview questions_

## Research Findings

### Codebase Structure
- **CLI**: Typer app in `src/mesh/cli/main.py`, `--output json` routed per-command to `init_json.py`, `destroy.py`, `add_worker.py`
- **JSON serialization**: `src/mesh/cli/commands/json_output.py` — `print_json_success()`, `to_brief_shape()`, error handlers
- **Provisioning**: Direct Libcloud path via `provision_direct.py` (no Pulumi for JSON mode)
- **Env vars**: `src/mesh/infrastructure/config/env.py` — canonical `EnvVars` class, `get_env()` function
- **Boot scripts**: Jinja2 templates, Caddy enabled for lite/standard tiers (line 121 of `generate_boot_scripts.py`)
- **Package**: `rethink-mesh` v0.4.0, Python >=3.11, console script `mesh`

### Test Infrastructure (HEALTHY)
- **Framework**: pytest >=7.4.0 with pytest-mock, pytest-cov
- **CLI testing**: Typer `CliRunner` + `@patch` from unittest.mock
- **~507 test functions** across 45 test files (~5-6:1 test-to-source ratio)
- **CI**: Excludes `e2e`, `integration`, `cloud_only`, `cross_cloud`, `destructive` markers
- **Markers available**: `slow`, `integration`, `e2e`, `local_only`, `destructive`, `cloud_only`, `cross_cloud`

### What Already Exists (JSON Mode Tests)
- **`test_init_json.py`**: 8 tests — demo mode, error cases, full flow with mocked provisioning
- **`test_destroy_json.py`**: 2 tests — demo mode destroy
- **`test_json_output.py`**: 8 tests — `to_brief_shape()`, `to_brief_destroy_shape()`
- **`test_init_json_health.py`**: 4 tests — health check polling
- **`test_interactive_regression.py`**: 6 tests — JSON doesn't leak Rich, interactive doesn't leak JSON

### Gaps Identified
1. No real-token E2E validation exists yet (CI can't run it, needs manual/local invocation)
2. `add-worker --output json` has no dedicated test file
3. No centralized conftest fixtures (CliRunner, mock patterns duplicated across files)
4. JSON error state fields (e.g., provisioning failed mid-way) not validated against central parser contract
5. `provision_cloud_cluster/` omitted from coverage — intentional (Pulumi entrypoint)

## Scope Boundaries
- INCLUDE: E2E verification with real DO token, regression tests for JSON vs interactive mode, packaging decision document
- EXCLUDE: New features, multi-droplet support, additional cloud providers, PyPI publishing (MVP decision is Option B)
