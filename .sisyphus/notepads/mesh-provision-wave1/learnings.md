# Wave 1 Learnings

## Codebase Context (from exploration)

### json_output.py
- `print_json_success(data)` → writes JSON to stdout, calls `sys.exit(0)` (line 51)
- `print_json_error(**kwargs)` → writes JSON to stderr, calls `sys.exit(1)` (line 100)
- `build_demo_init_json()` → rich nested shape with leader/workers, nomad_addr, daemon_*, caddy_admin
- `build_demo_destroy_json()` → {cluster_id, destroyed, resources_cleaned, demo}
- **No transform functions exist** — clean slate for `to_brief_shape()`

### init_json.py
- `run_init_json()` (line 53) — main JSON init entry point
- Demo path (lines 65-74): calls `build_demo_init_json()` then `print_json_success()`
- Real path: `provision_cluster_direct()` called at line 146, result dict built at lines 170-193
- **No health check** exists
- ALL success/error paths go through `print_json_success`/`print_json_error` → sys.exit

### destroy.py
- `_run_destroy_json()` (line 24) — JSON destroy handler
- Provider HARDCODED to "digitalocean" (line 53)
- Demo branch (line 37): uses `build_demo_destroy_json()`
- Real branch (line 49): calls `destroy_resources_direct()`

### Boot Script Patterns (11-install-daemon.sh + boot.sh)
- Daemon install gated by Jinja2 `{% if DAEMON_TOKEN and DAEMON_URL %}` + bash `ROLE == "server"`
- Caddy installed via `ENABLE_CADDY == "true"` flag, but **NO Caddyfile is generated**
- Tier gating: `CLUSTER_TIER != "lite"` blocks Consul/Tailscale, lite mode uses Nomad-only
- Non-fatal download failure: curl fail → warn + exit 0 (doesn't block boot)

### IP Polling Pattern (provision_direct.py)
- `_poll_for_ip(driver, node_id, timeout=120, interval=5)` — sleep-first, dual fallback
- Returns tuple `(public_ip, private_ip)` — either may be None
- `destroy_resources_direct()` returns `{cluster_name, destroyed: True, resources_cleaned: [...]}`

## T1: to_brief_shape (completed)
- Added `to_brief_shape()` at json_output.py line 207 — pure function, no sys.exit
- Input shape: `{cluster_id, leader: {ip, id, size}, workers: [{ip, id, size}], ...}`
- Output shape: `{cluster_id, leader_ip, status: "ready", nodes: [{id, ip, role}]}`
- Leader IP extracted from `leader.ip` with empty-string fallback
- `to_brief_shape` does NOT use print_json_success/print_json_error — pure transform only
- 5 tests in test_json_output.py: happy path, empty IPs, zero workers, three workers, cluster_id preserved
- Tests avoid importing print_json_success/print_json_error (they call sys.exit)

## Critical Patterns to Follow
1. **sys.exit mock**: All unit tests must `patch("mesh.cli.commands.<module>.print_json_success")` at MODULE level
2. **Sleep-first polling**: In health check, sleep before first check (match `_poll_for_ip` pattern)
3. **Non-fatal health**: Health check timeout → set status="provisioned", do NOT call print_json_error
4. **Jinja2 gating**: Boot script changes use `{% if %}` for template-level, bash `if` for runtime
5. **Tier awareness**: Caddyfile only for lite mode; standard tiers use Traefik

### T2: Caddyfile generation (11-install-daemon.sh)
- Inserted step 5 between config.yaml write and systemd unit creation (line 53-67)
- Gate: `CLUSTER_TIER == "lite"` — lite-only, standard tiers use Traefik
- Caddyfile writes to `/etc/caddy/Caddyfile` — proxy /health → localhost:8080 + fallback 200 response
- Non-fatal on all failures (validate + restart): `|| echo "WARNING: ..."`
- Renumbered downstream sections: 5→6 (systemd unit), 6→7 (data dir), 7→8 (enable/start)
- Caddy installed earlier by `10-install-caddy.sh` when `ENABLE_CADDY == "true"`

## Task 4: to_brief_destroy_shape (completed)

- `build_demo_destroy_json()` at line 269 (now includes `status: "destroyed"`)
- `to_brief_destroy_shape()` added at line ~277 — pure function, no side effects
- `_run_destroy_json()` in destroy.py: demo branch passes `build_demo_destroy_json` directly (already flat shape), real branch applies `to_brief_destroy_shape()` transform then adds `demo=False`
- `print_json_success()` calls `sys.exit(0)` — must mock for tests
- Test pattern: pure-function tests, no fixtures needed, docstrings match existing convention

## T6: Brief shape wiring (2026-05-06)
- `to_brief_shape()` signature: added optional `status` param with default "ready" for backward compat
- Demo path: already wired via `to_brief_shape(result)` before T6
- Real path: wired `to_brief_shape(result, status=health_status)` to propagate polled status
- Tests: 2 integration tests added — `test_full_flow_demo` (verifies flat shape + no rich field leaks) and `test_full_flow_real_mocked` (verifies status propagation from mocked health check)
- Pre-existing `test_missing_args_produces_error` failure unrelated to this change

## T5: CliRunner tests for init/destroy JSON (2026-05-06)
- Created `test_init_json.py` (6 tests) and `test_destroy_json.py` (2 tests)
- **Mock location is critical**: `destroy.py` lazily imports `print_json_success`/`print_json_error` inside `_run_destroy_json()`, so they don't exist as module-level attributes. Patch at source: `mesh.cli.commands.json_output.print_json_success`
- Same for `require_json_mode_args` → calls `print_json_error()` within `json_output.py`, so patch `mesh.cli.commands.json_output.print_json_error` not `mesh.cli.commands.init_json.print_json_error`
- `init_json.py` imports at module level → `patch("mesh.cli.commands.init_json.print_json_success")` works for init tests
- Wired `to_brief_shape()` into demo path of `run_init_json()` (was only on real path before)
- Pattern: mock print_json_success/error → invoke CliRunner → assert mock calls + data shape

## F2 Code Quality Review — 2026-05-06

### Lint pattern
- ruff flags F841 (result unused) in tests that use CliRunner + mocks — `runner.invoke()` return is captured but assertions go via `mock_success.call_args`. Convention: use `_` or just skip assignment.
- ruff does NOT understand bash syntax — running `ruff check` on `.sh` files produces noise. Exclude shell files from ruff checks.
- F401 `import pytest` left in `test_json_output.py` suggests the file was initially written with `@pytest.mark.*` decorators then simplified.

### `type: ignore` usage
- One `type: ignore[arg-type]` in `destroy.py:55` is acceptable — targeted rule, has justification comment.

### Health polling pattern
- `except Exception: pass` in `_poll_health` is intentional and correct — wide catch for connection errors during polling loop. Must have inline comment explaining why.

### Verdict
All logic correct. 9 minor auto-fixable lint warnings in new test files only.
