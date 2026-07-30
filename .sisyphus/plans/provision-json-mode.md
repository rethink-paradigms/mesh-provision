# Python Provisioning: JSON Output + Daemon Install + Token Passthrough

## TL;DR

> **Quick Summary**: Make the Python provisioning CLI callable by a machine (Central service). Add `--output json` for structured stdout/stderr, a daemon install step in boot scripts, and `--daemon-token` passthrough. All without breaking the existing interactive Rich-based CLI for humans.
>
> **Deliverables**:
> - `mesh init --output json` — creates cluster via direct Libcloud, prints JSON to stdout
> - `mesh destroy --output json` — tears down cluster, prints JSON
> - `mesh add-worker --output json` — adds worker to existing cluster
> - Daemon install step in boot.sh (download binary, write config, systemd unit, start)
> - `--daemon-token`, `--daemon-url`, `--api-key`, `--leader-size`, `--cluster-name` CLI flags
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves (scaffolding → parallel implementation → integration)
> **Critical Path**: Task 6 (boot script daemon step) → Task 7 (init_json wiring) → Task 9 (end-to-end verification)

---

## Context

### Original Request

Add three capabilities on top of the existing working Python provisioning tool:
1. **JSON output mode** (`--output json`) — structured stdout/stderr, no Rich, no prompts
2. **Daemon install step** — final bootstrap step to download and start the Go daemon
3. **Daemon token passthrough** (`--daemon-token`) — Central's auth token written into daemon config

### Interview Summary

**Key Discussions**:
- **Daemon binary source**: Pass download URL as `--daemon-url` CLI arg. Central controls the version.
- **Credential handling**: `--api-key` wins if provided, falls back to Infisical env (via `.workspace-secrets.yml`). Single-token providers (DO, Linode, Vultr) only — multi-credential providers handled later.  [OUTDATED — see SECRETS-PROTOCOL.md]
- **Provisioning engine**: Use direct Libcloud for `--output json` mode. Pulumi stays untouched for interactive mode.
- **Test strategy**: No automated unit tests per E2E plan — agent QA scenarios only.

**Research Findings**:
- `init_cmd.py` has 5 questionary prompts (all need CLI arg bypass in JSON mode)
- `boot.sh` correctly gates Consul/Tailscale for Lite tier (`CLUSTER_TIER != "lite"`) — no changes needed there
- `automation.py` Pulumi program only provisions 1 leader (no workers) — but Libcloud direct path handles ALL nodes
- `provision_node()` returns `instance_id` — available for JSON output
- Spec §6.2 defines exact JSON contracts for init, destroy, add-worker (stdout) and errors (stderr)
- Spec §9 defines daemon config.yaml schema: listen addr, nomad/consul endpoints, data dir, auth_token, tier

### Metis Review

**Identified Gaps** (addressed):
- **Multi-credential providers**: Locked to single-token providers (DO first). `--api-key` sufficient.
- **Daemon on all nodes vs leader-only**: Spec §5 confirms daemon runs on leader only. Boot step gated by `ROLE="server"`.
- **Partial provisioning failure**: Error JSON includes `partial_resources` array per spec §6.2.
- **Daemon config.yaml schema**: Defined in spec §9 — listen, nomad_addr, consul_addr, data_dir, auth_token, tier.
- **Architecture detection (AMD64 vs ARM64)**: boot.sh detects via `uname -m` and appends arch suffix to daemon URL.
- **`--output json` with `--demo`**: Produces synthetic JSON with `"demo": true` field.
- **Re-provisioning same cluster name**: Direct Libcloud path checks for existing resources before creating.
- **IP polling timeout**: JSON output returns `null` for IP field, document that Central should retry.

---

## Work Objectives

### Core Objective

Make `mesh init`, `mesh destroy`, and `mesh add-worker` callable by a machine with structured JSON output, while preserving 100% backward compatibility with the existing interactive Rich CLI.

### Concrete Deliverables

- `src/mesh/cli/commands/init_json.py` — direct Libcloud provisioning, JSON output
- `src/mesh/cli/commands/add_worker.py` — new command, JSON + interactive modes
- Modified `src/mesh/cli/main.py` — new CLI args + routing logic
- Modified `src/mesh/cli/commands/init_cmd.py` — routing to init_json when `--output json`
- Modified `src/mesh/cli/commands/destroy.py` — JSON mode
- New `src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh` — daemon install
- Modified `src/mesh/infrastructure/boot_consul_nomad/boot.sh` — invoke daemon step
- Modified `src/mesh/infrastructure/boot_consul_nomad/generate_boot_scripts.py` — new params

### Definition of Done

- [ ] `mesh init --output json --provider digitalocean --region nyc3 --workers 0 --leader-size s-2vcpu-4gb --api-key $DO_KEY --daemon-token $TOKEN --daemon-url $URL` produces exact JSON matching spec §6.2
- [ ] `mesh destroy --output json --cluster my-cluster --api-key $DO_KEY` produces exact JSON matching spec §6.2
- [ ] `mesh add-worker --output json --cluster my-cluster --provider digitalocean --region nyc3 --size s-2vcpu-4gb --api-key $DO_KEY --leader-ip 1.2.3.4` produces exact JSON matching spec §6.2
- [ ] `mesh init` (without `--output json`) behaves exactly as before — Rich output, questionary prompts work
- [ ] Boot script with `daemon_token` set installs and starts daemon; without it, boot script is unchanged

### Must Have

- All required CLI args enforced in JSON mode (error JSON on stderr if missing)
- Suppression of ALL Rich/ANSI output when `--output json` is set
- Direct Libcloud provisioning for JSON mode (NO Pulumi dependency in JSON path)
- Daemon install gated by `ROLE="server"` (leader only) and `--daemon-token` presence
- Boot script daemon step is idempotent (checks existing binary/unit before installing)

### Must NOT Have (Guardrails)

- **G1**: Do NOT modify `automation.py`'s Pulumi program or `_provision_cloud()` in init_cmd.py
- **G2**: Do NOT add `--output json` to deploy, status, logs, ssh, doctor, or any command except init, destroy, add-worker
- **G3**: Do NOT add health checks, log forwarding, restart logic, or any daemon management beyond install + enable + start
- **G4**: Do NOT change existing Rich output or questionary behavior
- **G5**: Do NOT create a remove-worker or scale-down command
- **G6**: Do NOT add multi-credential provider support (e.g., AWS key+secret) — single-token providers only
- **G7**: `--output json` and `--demo` together produce synthetic JSON with `"demo": true` — do NOT error

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision

- **Infrastructure exists**: YES — pytest with 27+ provider tests, 50+ boot script tests
- **Automated tests**: NO — per E2E plan, agent QA scenarios only. Tests added post-MVP.
- **Framework**: N/A for this plan
- **TDD**: No

### QA Policy

Every task includes agent-executed QA scenarios:
- CLI tests: `Bash` runs `mesh init --output json ...` and validates exit code + stdout/stderr content
- Boot script tests: `Bash` runs `python -c "from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import generate_shell_script; ..."` and validates output
- Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.txt`

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation):
├── Task 1: CLI flag additions (--output, --api-key, --daemon-token, --daemon-url, --leader-size, --cluster-name) [quick]
├── Task 2: JSON output serializer + error handler (shared module) [quick]
├── Task 3: Boot script: daemon install modular script [unspecified-low]
└── Task 4: Boot script: template + generator changes [unspecified-low]

Wave 2 (After Wave 1 — parallel implementation):
├── Task 5: ProvisionNode direct Libcloud extraction [deep]
├── Task 6: init_json.py — direct Libcloud provisioning with JSON output [deep]
├── Task 7: init_cmd.py routing + interactive backward compat [quick]
├── Task 8: destroy.py JSON mode [quick]
├── Task 9: add_worker.py — new command (JSON + interactive) [unspecified-high]
└── Task 10: Demo mode JSON support [quick]

Wave 3 (After Wave 2 — integration):
├── Task 11: End-to-end verification: init --output json [unspecified-high]
├── Task 12: End-to-end verification: destroy --output json [unspecified-high]
└── Task 13: End-to-end verification: backward compatibility [unspecified-high]

Wave FINAL (After ALL tasks):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

### Dependency Matrix

| Task | Blocked By | Blocks |
|---|---|---|
| 1 | None | 5-10 |
| 2 | None | 5-10 |
| 3 | None | 4 |
| 4 | 3 | 6 |
| 5 | None | 6 |
| 6 | 1,2,4,5 | 11 |
| 7 | 1 | 11 |
| 8 | 1,2 | 12 |
| 9 | 1,2 | 13 |
| 10 | 1,2 | 11,12,13 |
| 11 | 6,7 | FINAL |
| 12 | 8 | FINAL |
| 13 | 9 | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 4 tasks — T1,T2,T4 → `quick`, T3 → `unspecified-low`
- **Wave 2**: 6 tasks — T5,T6 → `deep`, T7,T8,T10 → `quick`, T9 → `unspecified-high`
- **Wave 3**: 3 tasks — all `unspecified-high`
- **FINAL**: 4 tasks — F1 → `oracle`, F2-F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. **CLI Flag Additions** — `--output`, `--api-key`, `--daemon-token`, `--daemon-url`, `--leader-size`, `--cluster-name`

  **What to do**:
  - Add `--output` flag to `init`, `destroy`, and new `add-worker` commands in `src/mesh/cli/main.py`:
    ```python
    output: Optional[str] = typer.Option(None, "--output", help="Output format: 'json' for machine-readable (default: rich)")
    ```
  - Add `--api-key` flag to `init`, `destroy`, `add-worker` — single string for token-based providers:
    ```python
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Cloud provider API key/token (overrides Infisical env)")
    ```
  - Add `--daemon-token` flag to `init`:
    ```python
    daemon_token: Optional[str] = typer.Option(None, "--daemon-token", help="Auth token for Go daemon (written to daemon config.yaml)")
    ```
  - Add `--daemon-url` flag to `init`:
    ```python
    daemon_url: Optional[str] = typer.Option(None, "--daemon-url", help="Download URL for Go daemon binary")
    ```
  - Add `--leader-size` flag to `init` (existing code has hardcoded defaults):
    ```python
    leader_size: Optional[str] = typer.Option(None, "--leader-size", help="VM size for leader node")
    ```
  - Add `--cluster-name` flag to `init` (existing code uses `--cluster` in destroy, spec uses `--cluster-name`; add both variants):
    ```python
    cluster_name: Optional[str] = typer.Option(None, "--cluster-name", help="Cluster name")
    ```
  - Add `--leader-ip` flag to `add-worker`:
    ```python
    leader_ip: Optional[str] = typer.Option(None, "--leader-ip", help="Leader node public IP for worker to join")
    ```
  - All flags are `Optional[str]` (or `Optional[int]` for `workers`) — defaults to `None` so interactive mode is unaffected
  - Help text must distinguish JSON mode behavior: `"(required when --output json)"` for mandatory-in-JSON-mode flags

  **Must NOT do**:
  - Do NOT remove or rename existing flags (`--provider`, `--region`, `--workers`, `--yes`, `--demo`, `--cluster`)
  - Do NOT change default values of existing flags
  - Do NOT add `--api-secret` (multi-credential) — out of scope per Guardrail G6

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple Typer option additions in one file, no logic changes

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 3, 5
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 6, 7, 8, 9, 10
  - **Blocked By**: None

  **References**:
  - `src/mesh/cli/main.py:59-87` — Existing `init` command flag pattern (use same `typer.Option` style)
  - `src/mesh/cli/main.py:111-128` — Existing `destroy` command flag pattern
  - `src/mesh/cli/main.py:199-237` — Existing `deploy` command (shows flag passthrough to command function)

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: Flags appear in help text
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --help
      2. Assert: output contains "--output TEXT", "--api-key TEXT", "--daemon-token TEXT", "--daemon-url TEXT", "--leader-size TEXT", "--cluster-name TEXT"
    Expected Result: All new flags listed in help output with descriptions
    Evidence: .sisyphus/evidence/task-1-help-output.txt
  
  Scenario: Flags default to None (interactive mode unaffected)
    Tool: Bash  
    Steps:
      1. Run: python -c "from mesh.cli.main import app; import inspect; sig = inspect.signature(app.commands['init'].callback); defaults = {k: v.default for k,v in sig.parameters.items() if v.default is not inspect.Parameter.empty}; print(defaults)"
      2. Assert: defaults for new flags are None
    Expected Result: All new flags have None default
    Failure Indicators: Any new flag has a non-None default
    Evidence: .sisyphus/evidence/task-1-defaults.txt
  ```

  **Commit**: YES (with Tasks 2,3,4)
  - Message: `feat(provision): add CLI flags for JSON mode and daemon install`
  - Files: `src/mesh/cli/main.py`

---

- [x] 2. **JSON Output Serializer + Error Handler** — shared module for JSON mode

  **What to do**:
  - Create `src/mesh/cli/commands/json_output.py` — shared utilities for JSON mode:
    ```python
    def print_json_success(data: dict) -> None:
        """Print success JSON to stdout, exit 0."""
    
    def print_json_error(*, code: str, message: str, phase: Optional[str] = None,
                         partial_resources: Optional[list] = None,
                         available_providers: Optional[list] = None,
                         missing_args: Optional[list] = None) -> None:
        """Print error JSON to stderr, exit 1."""
    
    def require_json_mode_args(**kwargs) -> dict:
        """Validate required CLI args in JSON mode. Return merged dict or exit with error JSON."""
    ```
  - `print_json_success()`: `json.dumps(data, indent=2)` → `sys.stdout`, then `sys.exit(0)`
  - `print_json_error()`: builds error dict matching spec §6.2 error shape:
    ```json
    {
      "error": {
        "code": "provision_failed",
        "message": "...",
        "phase": "create_droplet",
        "partial_resources": ["do-droplet-12345"]
      }
    }
    ```
  - `require_json_mode_args()`: checks each kwarg — if `None`, calls `print_json_error` with `missing_args` list
  - Error code mapping: `missing_required_args` → missing CLI args, `unknown_provider` → invalid provider, `missing_credentials` → no API key, `provision_failed` → provisioning error with phase
  - Suppress ALL Rich output: In JSON mode, set `from mesh.cli.ui.panels import console; console.quiet = True` or redirect console

  **Must NOT do**:
  - Do NOT import Rich in this module (keep it dependency-free except for stdlib + json)
  - Do NOT handle provider-specific logic here — that's the provisioner's job
  - Do NOT create a class — simple functions only

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small utility module, no dependencies, pure functions

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1, 3, 5
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 6, 7, 8, 9, 10
  - **Blocked By**: None

  **References**:
  - Spec §6.2 lines 377-385 — Error JSON shape (`code`, `message`, `phase`, `partial_resources`)
  - Spec §6.2 lines 358-375 — Success JSON shape for init
  - Spec §6.2 lines 397-404 — Success JSON shape for destroy
  - Spec §6.2 lines 407-423 — Success JSON shape for add-worker

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: Success JSON prints to stdout and exits 0
    Tool: Bash
    Steps:
      1. Run: python -c "
  import sys, os; sys.path.insert(0, 'src')
  from mesh.cli.commands.json_output import print_json_success
  print_json_success({'cluster_id': 'test', 'status': 'created'})
  " 2>&1; echo "EXIT=$?"
      2. Assert: stdout contains '{"cluster_id": "test", "status": "created"}'
      3. Assert: EXIT=0
    Expected Result: Valid JSON on stdout, exit code 0
    Evidence: .sisyphus/evidence/task-2-success.txt

  Scenario: Error JSON prints to stderr and exits 1
    Tool: Bash
    Steps:
      1. Run: python -c "
  import sys, os; sys.path.insert(0, 'src')
  from mesh.cli.commands.json_output import print_json_error
  print_json_error(code='provision_failed', message='Test error', phase='create_droplet', partial_resources=['do-12345'])
  " 1>/dev/null 2>stderr.txt; echo "EXIT=$?"
      2. Cat stderr.txt, check: contains '"code": "provision_failed"', '"message": "Test error"', '"phase": "create_droplet"', '"partial_resources": ["do-12345"]'
      3. Assert: EXIT=1
    Expected Result: Valid error JSON on stderr, exit code 1
    Evidence: .sisyphus/evidence/task-2-error.txt

  Scenario: Missing required args detected
    Tool: Bash
    Steps:
      1. Run: python -c "
  import sys, os; sys.path.insert(0, 'src')
  from mesh.cli.commands.json_output import require_json_mode_args
  require_json_mode_args(region=None, provider='digitalocean')
  " 2>stderr.txt; echo "EXIT=$?"
      2. Assert: stderr.txt contains '"missing_args": ["region"]'
      3. Assert: EXIT=1
    Expected Result: Error JSON on stderr with missing args list
    Evidence: .sisyphus/evidence/task-2-missing-args.txt
  ```

  **Commit**: YES (with Tasks 1,3,4)
  - Message: `feat(provision): add JSON output serializer and error handler`
  - Files: `src/mesh/cli/commands/json_output.py`

---

- [x] 3. **Boot Script: Daemon Install Modular Script** — new `11-install-daemon.sh`

  **What to do**:
  - Create `src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh` following the established modular script pattern:
    ```bash
    #!/bin/bash
    set -euo pipefail
    
    DAEMON_URL="{{ DAEMON_URL }}"
    DAEMON_TOKEN="{{ DAEMON_TOKEN }}"
    CLUSTER_TIER="{{ CLUSTER_TIER }}"
    NOMAD_ADDR="http://127.0.0.1:4646"
    LISTEN_ADDR="127.0.0.1:8080"
    DATA_DIR="/var/lib/mesh"
    
    # Idempotency: skip if daemon already installed
    if [ -f /usr/local/bin/mesh-daemon ] && [ -f /etc/systemd/system/mesh-daemon.service ]; then
        echo "Mesh daemon already installed, skipping..."
        exit 0
    fi
    
    # ... install steps
    ```
  - Install steps:
    1. Detect architecture: `ARCH=$(uname -m)` → map `x86_64` → `amd64`, `aarch64` → `arm64`
    2. Download binary: `curl -fsSL "${DAEMON_URL}-${ARCH}" -o /usr/local/bin/mesh-daemon && chmod +x /usr/local/bin/mesh-daemon`
    3. Create config dir: `mkdir -p /etc/mesh`
    4. Write config at `/etc/mesh/config.yaml` (per spec §9):
       ```yaml
       listen: "{{ LISTEN_ADDR }}"
       nomad_addr: "http://127.0.0.1:4646"
       consul_addr: ""  # empty in lite mode
       data_dir: "/var/lib/mesh"
       auth_token: "{{ DAEMON_TOKEN }}"
       tier: "{{ CLUSTER_TIER }}"
       ```
    5. Create systemd unit at `/etc/systemd/system/mesh-daemon.service`:
       ```
       [Unit]
       Description=Mesh Daemon — body lifecycle manager
       Requires=network-online.target
       After=network-online.target nomad.service
       [Service]
       Type=simple
       ExecStart=/usr/local/bin/mesh-daemon serve
       Restart=on-failure
       [Install]
       WantedBy=multi-user.target
       ```
    6. Create data dir: `mkdir -p /var/lib/mesh`
    7. Enable and start: `systemctl daemon-reload && systemctl enable mesh-daemon && systemctl start mesh-daemon`
    8. Register Caddy route: `curl -X POST http://127.0.0.1:2019/load -H "Content-Type: application/json" -d '{...caddy config...}'`
  - Skip Caddy route registration if Caddy not installed (lite tier check)
  - Caddy config: reverse proxy `daemon-{CLUSTER_ID}.agentbodies.com` → `127.0.0.1:8080`

  **Must NOT do**:
  - Do NOT add health checks, log forwarding, or restart logic beyond systemd's built-in `Restart=on-failure`
  - Do NOT install the daemon if `/usr/local/bin/mesh-daemon` already exists (idempotent)
  - Do NOT fail the entire boot script if daemon download fails (daemon is non-critical for cluster operation) — use `|| echo "Warning: daemon download failed"` pattern

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Single shell script, well-defined pattern from existing scripts

  **Skills**: [`git-master`]
    - `git-master`: For tracking which files changed and ensuring clean commit

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1, 2, 5
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 4
  - **Blocked By**: None

  **References**:
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/10-install-caddy.sh` — Pattern to follow (idempotency check, install steps, success message)
  - `src/mesh/infrastructure/boot_consul_nomad/scripts/03-install-hashicorp.sh` — Binary download pattern (curl + chmod)
  - Spec §5 lines 131-138 — Daemon deployment details (binary path, config path, listen addr, systemd)
  - Spec §9 lines 755-772 — Daemon config.yaml schema

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: Script is valid bash with proper structure
    Tool: Bash
    Steps:
      1. Run: bash -n src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh
      2. Assert: exit code 0 (no syntax errors)
    Expected Result: Script passes bash syntax check
    Failure Indicators: Exit code 1, syntax error messages
    Evidence: .sisyphus/evidence/task-3-syntax-check.txt

  Scenario: Script follows idempotency pattern
    Tool: Bash
    Steps:
      1. Run: grep -c "already installed, skipping" src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh
      2. Assert: count >= 1
    Expected Result: Script has idempotency check
    Evidence: .sisyphus/evidence/task-3-idempotency.txt
  ```

  **Commit**: YES (with Tasks 1,2,4)
  - Message: `feat(provision): add daemon install modular script`
  - Files: `src/mesh/infrastructure/boot_consul_nomad/scripts/11-install-daemon.sh`

---

- [x] 4. **Boot Script: Template + Generator Changes** — Jinja2 vars and Python params

  **What to do**:
  - Add new Jinja2 variables to `src/mesh/infrastructure/boot_consul_nomad/boot.sh`:
    ```bash
    DAEMON_TOKEN="{{ DAEMON_TOKEN }}"       # daemon auth token (empty if not provided)
    DAEMON_URL="{{ DAEMON_URL }}"           # binary download URL (empty if not provided)
    CLUSTER_ID="{{ CLUSTER_ID }}"           # cluster identifier (for Caddy route)
    ```
  - Add daemon invocation block after existing boot steps (after Caddy install, before systemd restart block, around line 82-85 in current boot.sh):
    ```bash
    # Daemon install (leader only, only if token provided)
    if [ "$ROLE" = "server" ] && [ -n "$DAEMON_TOKEN" ] && [ -n "$DAEMON_URL" ]; then
        bash scripts/11-install-daemon.sh
    fi
    ```
  - Add `daemon_token`, `daemon_url`, `cluster_id` params to `generate_shell_script()` in `src/mesh/infrastructure/boot_consul_nomad/generate_boot_scripts.py`:
    ```python
    def generate_shell_script(
        # ... existing params ...
        daemon_token: Optional[str] = None,
        daemon_url: Optional[str] = None,
        cluster_id: Optional[str] = None,
    ) -> str:
    ```
  - Template render: `DAEMON_TOKEN=daemon_token or ""`, `DAEMON_URL=daemon_url or ""`, `CLUSTER_ID=cluster_id or ""`
  - Ensure `generate_shell_script()` with new params set to `None` renders EXACTLY the same boot.sh as before (no diff)

  **Must NOT do**:
  - Do NOT change the function signature for existing required params (`tailscale_key`, `leader_ip`, `role`)
  - Do NOT add daemon variables to `generate_cloud_init_yaml()` params (it calls `generate_shell_script()` internally — pass through)
  - Do NOT make daemon install mandatory — it's gated by ROLE + DAEMON_TOKEN + DAEMON_URL all being present

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding optional params and template blocks, following existing patterns exactly

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on Task 3 (script must exist)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 6
  - **Blocked By**: Task 3

  **References**:
  - `src/mesh/infrastructure/boot_consul_nomad/boot.sh:1-16` — Existing Jinja2 variable block (add new vars here)
  - `src/mesh/infrastructure/boot_consul_nomad/boot.sh:82-85` — Caddy install block (add daemon after this)
  - `src/mesh/infrastructure/boot_consul_nomad/generate_boot_scripts.py:80-147` — `generate_shell_script()` function signature
  - `src/mesh/infrastructure/boot_consul_nomad/generate_boot_scripts.py:120-135` — Template render call (add new vars)

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: Boot script unchanged when daemon params are None
    Tool: Bash
    Steps:
      1. Run: python -c "
  import sys; sys.path.insert(0, 'src')
  from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import generate_shell_script
  result = generate_shell_script('tskey-test', '10.0.0.1', 'server')
  assert 'mesh-daemon' not in result, 'Daemon found in output without token'
  assert 'DAEMON_TOKEN' not in result, 'DAEMON_TOKEN variable present without token'
  assert 'DAEMON_URL' not in result, 'DAEMON_URL variable present without URL'
  print('PASS: no daemon in output when params are None')
  "
      2. Assert: output contains 'PASS'
    Expected Result: Boot script renders identically to before — no daemon content
    Evidence: .sisyphus/evidence/task-4-backward-compat.txt

  Scenario: Boot script includes daemon when token + URL provided
    Tool: Bash
    Steps:
      1. Run: python -c "
  import sys; sys.path.insert(0, 'src')
  from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import generate_shell_script
  result = generate_shell_script('tskey-test', '10.0.0.1', 'server', daemon_token='tok123', daemon_url='https://rel.example.com/daemon', cluster_id='test-cluster')
  assertions = [
      ('bash scripts/11-install-daemon.sh' in result, 'Daemon install script not invoked'),
      ('tok123' in result, 'Token not in rendered output'),
      ('daemon' in result.lower(), 'daemon not mentioned at all'),
  ]
  failed = [msg for ok, msg in assertions if not ok]
  if failed:
      for f in failed: print(f'FAIL: {f}')
      sys.exit(1)
  print('PASS: daemon install present in output')
  "
      2. Assert: output contains 'PASS'
    Expected Result: Boot script includes daemon install invocation with token
    Evidence: .sisyphus/evidence/task-4-daemon-present.txt
  ```

  **Commit**: YES (with Tasks 1,2,3)
  - Message: `feat(provision): add daemon install step to boot script template and generator`
  - Files: `src/mesh/infrastructure/boot_consul_nomad/boot.sh`, `src/mesh/infrastructure/boot_consul_nomad/generate_boot_scripts.py`

---
- [x] 5. **ProvisionNode Direct Libcloud Extraction** — reusable direct provisioning module

  **What to do**:
  - Create `src/mesh/infrastructure/provision_node/provision_direct.py` — a new module that provisions VMs via Libcloud directly (bypassing Pulumi):
    ```python
    def provision_node_direct(
        name: str,
        provider: str,
        region: str,
        size_id: str,
        api_key: str,
        boot_script: str,
    ) -> dict:
        """
        Provision a single VM via direct Libcloud call.
        Returns: {name, public_ip, private_ip, instance_id, size_id}
        """
    ```
  - Uses the existing Libcloud dynamic provider from `src/mesh/infrastructure/providers/libcloud_dynamic_provider.py`
  - The existing `UniversalCloudNodeProvider.create()` already does direct Libcloud provisioning — extract the core logic:
    - Get provider driver: `libcloud_dynamic_provider._get_driver(provider, api_key, region)`
    - Create node: `driver.create_node(name=name, size=size_obj, image=image_obj, ex_user_data=boot_script, ...)`
    - Poll for IP: reuse existing 120s polling loop from `libcloud_dynamic_provider.py:246`
    - Return structured dict
  - Also add `def provision_cluster_direct(...)` — orchestrates leader + N workers:
    - Provision leader with server boot script → get leader IP
    - For each worker: provision with client boot script (uses leader IP in script)
    - Return all node info
  - Add `def destroy_resources_direct(provider, api_key, region, cluster_name)`:
    - Lists nodes with `cluster_name` prefix in provider
    - Destroys each node
    - Returns list of destroyed instance IDs

  **Must NOT do**:
  - Do NOT remove or refactor the Pulumi `UniversalCloudNodeProvider` — it stays untouched
  - Do NOT touch `automation.py` or any Pulumi code
  - Do NOT add Pulumi dependencies to this module

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Extracting core logic from an existing Pulumi wrapper, careful API surface design, needs to reuse Libcloud internals correctly

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 1, 2, 3 (but should wait for 1 to confirm provider_enums API)
  - **Parallel Group**: Wave 2 (starts after Wave 1, runs parallel with Tasks 6-10)
  - **Blocks**: Task 6
  - **Blocked By**: None (can start immediately, but Task 1 provides provider list)

  **References**:
  - `src/mesh/infrastructure/providers/libcloud_dynamic_provider.py` — `UniversalCloudNodeProvider.create()` method (has the direct Libcloud logic to extract)
  - `src/mesh/infrastructure/providers/__init__.py` — Provider enums and `list_providers()`
  - `src/mesh/infrastructure/provision_node/provision_node.py` — Existing `provision_node()` function (Pulumi-based, shows what outputs to return)
  - `src/mesh/infrastructure/config/env.py` — `EnvVars` and `get_env()` (for credential fallback pattern)

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: Module imports without errors
    Tool: Bash
    Steps:
      1. Run: python -c "import sys; sys.path.insert(0, 'src'); from mesh.infrastructure.provision_node.provision_direct import provision_node_direct, destroy_resources_direct; print('IMPORT_OK')"
      2. Assert: output contains 'IMPORT_OK'
    Expected Result: Module imports cleanly, no circular deps
    Evidence: .sisyphus/evidence/task-5-import.txt

  Scenario: Direct Libcloud DO driver loads (no actual provisioning)
    Tool: Bash
    Steps:
      1. Run: python -c "
  import sys; sys.path.insert(0, 'src')
  from mesh.infrastructure.providers import PROVIDER_ENUMS
  assert 'digitalocean' in [p.value for p in PROVIDER_ENUMS], 'DO not in providers'
  print('PROVIDER_OK')
  "
      2. Assert: output contains 'PROVIDER_OK'
    Expected Result: DigitalOcean provider accessible
    Evidence: .sisyphus/evidence/task-5-provider.txt
  ```

  **Commit**: YES (with Tasks 6,7,8,9,10)
  - Message: `feat(provision): add direct Libcloud provisioning module`
  - Files: `src/mesh/infrastructure/provision_node/provision_direct.py`

---

- [x] 6. **init_json.py — Direct Libcloud Provisioning with JSON Output** — the core new command handler

  **What to do**:
  - Create `src/mesh/cli/commands/init_json.py` — handles `mesh init --output json`:
    ```python
    def run_init_json(
        provider: str, region: str, workers: int,
        leader_size: str, worker_size: str, cluster_name: str,
        api_key: str, daemon_token: str, daemon_url: str,
        demo: bool = False,
    ) -> None:
        """Handle init with --output json. Prints JSON to stdout, errors to stderr."""
    ```
  - Flow:
    1. Validate all required args via `require_json_mode_args()` (Task 2)
    2. Resolve credential: `api_key` or fallback to `get_env(EnvVars.*)`
    3. Detect tier: workers==0 → "lite", workers>=1 → "standard" (reuse `progressive_activation` module)
    4. Generate Tailscale key via `configure_tailscale.create_auth_key()` (if tier != "lite")
    5. Generate boot script via `generate_shell_script()` with NEW params: `daemon_token`, `daemon_url`, `cluster_id=cluster_name`
    6. Provision nodes via `provision_cluster_direct()` (Task 5)
    7. Build JSON response matching spec §6.2 exactly:
       ```json
       {
         "cluster_id": "user-abc-cluster-1",
         "provider": "digitalocean",
         "region": "nyc1",
         "tier": "lite",
         "leader": {"ip": "167.71.45.123", "id": "do-droplet-12345", "size": "s-2vcpu-4gb"},
         "workers": [],
         "nomad_addr": "http://127.0.0.1:4646",
         "daemon_url": "https://daemon-user-abc-cluster-1.agentbodies.com",
         "daemon_token": "$GENERATED_TOKEN",
         "caddy_admin": "http://127.0.0.1:2019",
         "created_at": "2026-05-04T10:00:00Z"
       }
       ```
    8. Call `print_json_success(data)` → prints JSON to stdout, exits 0
  - On any error: call `print_json_error()` with appropriate code, message, phase, partial_resources
  - Demo mode: skip all provisioning, build synthetic JSON with `"demo": true` and realistic fake data

  **Must NOT do**:
  - Do NOT import or use Rich console — only `print_json_success()` / `print_json_error()`
  - Do NOT call `questionary` or any interactive prompt
  - Do NOT import Pulumi or `automation.py`
  - Do NOT touch `init_cmd.py` — this is a separate module

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Orchestrates multiple subsystems (credential resolution, tier detection, Tailscale key gen, boot scripts, direct provisioning, JSON assembly). High integration complexity. Must match spec exactly.

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 8, 9, 10
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 11
  - **Blocked By**: Tasks 1, 2, 4, 5

  **References**:
  - Spec §6.2 lines 346-375 — Exact JSON output shape for `mesh init`
  - Spec §6.2 lines 377-385 — Error JSON shape
  - Spec §10 lines 796-803 — Cluster tiers (lite vs standard)
  - `src/mesh/infrastructure/progressive_activation/tier_config.py` — `detect_tier()` function
  - `src/mesh/infrastructure/configure_tailscale/` — Tailscale auth key generation
  - `src/mesh/infrastructure/boot_consul_nomad/generate_boot_scripts.py` — `generate_shell_script()` (now with daemon params)
  - `src/mesh/cli/commands/json_output.py` — `print_json_success()` and `print_json_error()` (Task 2)

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: JSON mode init with --demo produces valid JSON
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --output json --demo --provider digitalocean --region nyc3 --workers 0 --leader-size s-2vcpu-4gb --api-key test-key --daemon-token tok123 --daemon-url https://example.com/daemon --cluster-name test-cluster 2>stderr.txt
      2. Pipe stdout through: python -c "import sys,json; data=json.load(sys.stdin); print('VALID_JSON'); print(data.get('cluster_id','MISSING')); print(data.get('tier','MISSING'))"
      3. Assert: stdout contains 'VALID_JSON'
      4. Assert: cluster_id = 'test-cluster', tier = 'lite'
      5. Assert: stderr.txt is empty
    Expected Result: Valid JSON on stdout matching spec §6.2 shape, empty stderr
    Evidence: .sisyphus/evidence/task-6-init-json-demo.txt

  Scenario: Missing required arg produces error JSON on stderr
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --output json --provider digitalocean --workers 0 2>stderr.txt; echo "EXIT=$?"
      2. Cat stderr.txt, check: valid JSON with error.code field and mention of missing region
      3. Assert: EXIT=1
      4. Assert: stdout is empty
    Expected Result: Error JSON on stderr with missing args, exit 1
    Evidence: .sisyphus/evidence/task-6-missing-arg-error.txt
  ```

  **Commit**: YES (with Tasks 5,7,8,9,10)
  - Message: `feat(provision): implement JSON mode init via direct Libcloud provisioning`
  - Files: `src/mesh/cli/commands/init_json.py`

---

- [x] 7. **init_cmd.py Routing + Backward Compat** — wire JSON mode into existing init

  **What to do**:
  - In `src/mesh/cli/commands/init_cmd.py` `run_init()` function:
    - Accept new params: `output`, `api_key`, `daemon_token`, `daemon_url`, `leader_size`, `cluster_name`, `worker_size`
    - Add routing decision at the top:
      ```python
      if output == "json":
          from mesh.cli.commands.init_json import run_init_json
          run_init_json(
              provider=provider_name or "digitalocean",
              region=region or "",
              workers=workers or 0,
              leader_size=leader_size or "s-2vcpu-4gb",
              worker_size=worker_size or "s-1vcpu-1gb",
              cluster_name=cluster_name or "mesh-cluster",
              api_key=api_key or "",
              daemon_token=daemon_token or "",
              daemon_url=daemon_url or "",
              demo=demo,
          )
          return
      ```
    - Pass remaining new args through to `_provision_cloud()` if needed (worker_size for future use)
  - Backward compat: When `output != "json"`, existing flow runs UNCHANGED
  - In `src/mesh/cli/main.py` `init()` command function: add all new CLI params to the function signature and pass to `run_init()`

  **Must NOT do**:
  - Do NOT modify the existing init flow logic beyond the routing `if output == "json"` block
  - Do NOT change questionary prompt behavior for interactive mode
  - Do NOT change `_provision_cloud()` or `_provision_multipass()` functions

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple routing logic addition to existing function, no new logic

  **Parallelization**:
  - **Can Run In Parallel**: NO — depends on Task 6 (init_json module must exist)
  - **Parallel Group**: Wave 2 (after Task 6)
  - **Blocks**: Task 11
  - **Blocked By**: Tasks 1, 6

  **References**:
  - `src/mesh/cli/commands/init_cmd.py:246-252` — `run_init()` function signature (add new params here)
  - `src/mesh/cli/commands/init_cmd.py:259` — After `show_banner()` line (add routing decision here)
  - `src/mesh/cli/main.py:59-87` — `init` command with Typer options (add new flags per Task 1)

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: Interactive mode still works unchanged
    Tool: Interactive Bash (tmux)
    Steps:
      1. Create tmux session: new-session -d -s mesh-test
      2. Send keys: echo "Local (Multipass)" | python -m mesh init --yes --demo 2>&1
      3. Capture output
      4. Assert: exit code 0
      5. Assert: output contains Rich-styled text (ANSI codes or "Cluster is ready")
    Expected Result: Interactive mode shows Rich output, no JSON
    Evidence: .sisyphus/evidence/task-7-interactive-compat.txt

  Scenario: JSON mode routes to init_json (via --demo, no real infra)
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --output json --demo --provider digitalocean --region nyc3 --workers 0 --leader-size test --api-key test-key --daemon-token tok --daemon-url http://example.com/d --cluster-name test 2>/dev/null
      2. Assert: exit code 0
      3. Assert: stdout is valid JSON (pipe through python -m json.tool)
    Expected Result: JSON output on stdout, exit 0
    Failure Indicators: Rich output, exit 1, invalid JSON
    Evidence: .sisyphus/evidence/task-7-json-routing.txt
  ```

  **Commit**: YES (with Tasks 5,6,8,9,10)
  - Message: `feat(provision): route JSON mode init to direct Libcloud path`
  - Files: `src/mesh/cli/commands/init_cmd.py`, `src/mesh/cli/main.py`

---

- [x] 8. **destroy.py JSON Mode** — structured teardown output

  **What to do**:
  - In `src/mesh/cli/commands/destroy.py` `run_destroy()`:
    - Accept new params: `output`, `api_key`, `provider`
    - Add routing at the top:
      ```python
      if output == "json":
          _run_destroy_json(cluster_name, api_key, provider, demo)
          return
      ```
  - Implement `_run_destroy_json()`:
    1. Validate args via `require_json_mode_args()` (Task 2)
    2. In demo mode: return synthetic JSON
    3. For real mode: Use `destroy_resources_direct()` (Task 5) to destroy all cluster resources
    4. Return JSON matching spec §6.2:
       ```json
       {
         "cluster_id": "user-abc-cluster-1",
         "destroyed": true,
         "resources_cleaned": ["do-droplet-12345", "do-droplet-12346"]
       }
       ```
    5. Also handle Pulumi path: check if Pulumi stack exists for cluster, destroy via Pulumi if so
  - Error handling: if nothing to destroy, return `{"cluster_id": "...", "destroyed": true, "resources_cleaned": []}` (idempotent success)

  **Must NOT do**:
  - Do NOT change the existing interactive destroy flow (questionary confirmation, Rich panels)
  - Do NOTE: existing destroy.py has `--yes` flag for non-interactive mode — that's fine, keep it

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding JSON mode to existing destroy command, reuses infrastructure from Tasks 2 and 5

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 6, 9, 10
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 1, 2, 5

  **References**:
  - `src/mesh/cli/commands/destroy.py:20-132` — Existing `run_destroy()` (add routing at top)
  - Spec §6.2 lines 397-404 — Destroy JSON shape
  - `src/mesh/cli/commands/json_output.py` — `print_json_success()` / `print_json_error()`
  - `src/mesh/infrastructure/provision_node/provision_direct.py` — `destroy_resources_direct()` (Task 5)

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: JSON mode destroy with --demo
    Tool: Bash
    Steps:
      1. Run: python -m mesh destroy --output json --demo --cluster test-cluster --yes 2>stderr.txt
      2. Pipe stdout through: python -c "import sys,json; d=json.load(sys.stdin); print(d.get('destroyed')); print(d.get('cluster_id'))"
      3. Assert: stdout contains 'True' and 'test-cluster'
      4. Assert: stderr.txt is empty
    Expected Result: Valid destroy JSON on stdout
    Evidence: .sisyphus/evidence/task-8-destroy-json.txt

  Scenario: Interactive destroy mode still works
    Tool: Bash
    Steps:
      1. Run: python -m mesh destroy --demo --yes 2>&1
      2. Assert: exit code 0
      3. Assert: output contains "Destroy" and "Cluster" (Rich-styled content)
    Expected Result: Rich output shows, no JSON
    Evidence: .sisyphus/evidence/task-8-interactive-compat.txt
  ```

  **Commit**: YES (with Tasks 5,6,7,9,10)
  - Message: `feat(provision): add JSON output mode to destroy command`
  - Files: `src/mesh/cli/commands/destroy.py`

---

- [x] 9. **add_worker.py — New Command** — JSON + interactive modes

  **What to do**:
  - Create `src/mesh/cli/commands/add_worker.py` — brand new command:
    ```python
    def run_add_worker(
        cluster_name: str, provider: str, region: str, size: str,
        api_key: str, leader_ip: str,
        output: Optional[str] = None, demo: bool = False,
    ) -> None:
        """Add a worker node to existing cluster."""
    
    def _run_add_worker_json(...) -> None:
        """JSON mode: provision via direct Libcloud, print JSON."""
    
    def _run_add_worker_interactive(...) -> None:
        """Interactive mode: Rich output, questionary prompts."""
    ```
  - **JSON mode** (`_run_add_worker_json`):
    1. Validate all required args (cluster, provider, region, size, api_key, leader_ip must ALL be present)
    2. Resolve credentials (--api-key or Infisical env fallback)  [OUTDATED — see SECRETS-PROTOCOL.md]
    3. Get TAILSCALE_KEY from env (required for worker mesh join)
    4. Generate worker boot script via `generate_shell_script(role="client", leader_ip=leader_ip, ...)`
    5. Provision via `provision_node_direct()` (Task 5)
    6. Return JSON matching spec §6.2:
       ```json
       {
         "node": {
           "ip": "167.71.45.124",
           "id": "do-droplet-12346",
           "role": "worker"
         }
       }
       ```
  - **Interactive mode** (`_run_add_worker_interactive`):
    - Use questionary to prompt for: cluster name, provider, region, size (matching init_cmd.py style)
    - Show Rich progress panels
    - Provision via Pulumi or direct Libcloud (use Pulumi for consistency with interactive init)
  - Register command in `src/mesh/cli/main.py`:
    ```python
    @app.command("add-worker")
    def add_worker(
        cluster: str = typer.Option("mesh-cluster", "--cluster", "-c"),
        provider: Optional[str] = typer.Option(None, "--provider", "-p"),
        region: Optional[str] = typer.Option(None, "--region", "-r"),
        size: Optional[str] = typer.Option(None, "--size", "-s"),
        leader_ip: Optional[str] = typer.Option(None, "--leader-ip"),
        api_key: Optional[str] = typer.Option(None, "--api-key"),
        output: Optional[str] = typer.Option(None, "--output"),
        demo: bool = typer.Option(False, "--demo"),
    ):
        run_add_worker(cluster, provider, region, size, api_key, leader_ip, output, demo)
    ```

  **Must NOT do**:
  - Do NOT create remove-worker, scale-down, or scale-up commands
  - Do NOT import Pulumi in the JSON mode path
  - Do NOT modify existing `init_cmd.py` or `deploy.py` — add-worker is standalone

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New command from scratch — needs CLI registration, both JSON and interactive paths, integration with provisioning and boot scripts. More complex than routing additions.

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 6, 8, 10
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 13
  - **Blocked By**: Tasks 1, 2, 5

  **References**:
  - `src/mesh/cli/commands/init_cmd.py:246-401` — Pattern for command that has both interactive and non-interactive paths
  - `src/mesh/cli/main.py:59-87` — Pattern for registering a Typer command
  - Spec §6.2 lines 407-423 — add-worker JSON output shape
  - `src/mesh/infrastructure/boot_consul_nomad/generate_boot_scripts.py:80-147` — `generate_shell_script(role="client", ...)` for worker boot script
  - `src/mesh/infrastructure/provision_node/provision_direct.py` — `provision_node_direct()` (Task 5)

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: add-worker --output json --demo produces valid JSON
    Tool: Bash
    Steps:
      1. Run: python -m mesh add-worker --output json --demo --cluster test --provider digitalocean --region nyc3 --size s-2vcpu-4gb --api-key test --leader-ip 1.2.3.4 2>stderr.txt
      2. Pipe stdout through: python -c "import sys,json; d=json.load(sys.stdin); print(d['node']['ip']); print(d['node']['role'])"
      3. Assert: node.ip = '1.2.3.4' (or realistic demo IP)
      4. Assert: node.role = 'worker'
    Expected Result: Valid add-worker JSON on stdout
    Evidence: .sisyphus/evidence/task-9-add-worker-json.txt

  Scenario: add-worker without --output json shows Rich interactive mode
    Tool: Bash
    Steps:
      1. Run: python -m mesh add-worker --demo --cluster test --provider digitalocean --region nyc3 --size s-2vcpu-4gb --api-key test --leader-ip 1.2.3.4 2>&1
      2. Assert: exit code 0
      3. Assert: output contains Rich-styled content (not JSON)
    Expected Result: Rich output for interactive mode
    Evidence: .sisyphus/evidence/task-9-interactive-compat.txt
  ```

  **Commit**: YES (with Tasks 5,6,7,8,10)
  - Message: `feat(provision): add add-worker command with JSON and interactive modes`
  - Files: `src/mesh/cli/commands/add_worker.py`, `src/mesh/cli/main.py`

---

- [x] 10. **Demo Mode JSON Support** — synthetic data for testing

  **What to do**:
  - Ensure ALL three commands (init, destroy, add-worker) produce realistic JSON when `--output json --demo`:
    - `init`: synthetic cluster with fake IPs (e.g., `"127.0.0.1"` or `"192.0.2.X"` ranges per RFC 5737), fake droplet IDs, real-looking timestamps
    - `destroy`: synthetic destroyed=true with empty resources_cleaned list
    - `add-worker`: synthetic worker node
  - Add `"demo": true` field to all demo JSON outputs (both success AND error) so consuming code can distinguish
  - Demo mode should:
    - NOT call any cloud API
    - NOT require real credentials (accept any string)
    - Complete in < 1 second
    - Produce structurally identical JSON to real mode (same keys, types, nesting)

  **Must NOT do**:
  - Do NOT make `--demo` required for `--output json` — they're independent flags
  - Do NOT use `"127.0.0.1"` for demo IPs — use RFC 5737 test ranges (`192.0.2.0/24`) so consumers don't think it's localhost

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Add demo handling to each JSON-mode function, straightforward fake data generation

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 6, 8, 9
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 11, 12, 13
  - **Blocked By**: Tasks 1, 2

  **References**:
  - `src/mesh/cli/commands/init_cmd.py:566-568` — Existing demo path in `_provision_cloud()` (shows demo steps, Rich output)
  - `src/mesh/cli/commands/destroy.py:60-69` — Existing demo destroy with rich output
  - Spec §6.2 lines 358-375 — Success JSON shape to replicate in demo

  **Acceptance Criteria**:

  **QA Scenarios**:

  ```
  Scenario: init --output json --demo produces complete JSON matching real schema
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --output json --demo --provider digitalocean --region nyc3 --workers 2 --leader-size s-2vcpu-4gb --api-key test-key --daemon-token tok --daemon-url http://ex.com/d --cluster-name demo-cluster 2>/dev/null | python -c "
  import sys, json
  d = json.load(sys.stdin)
  required_keys = ['cluster_id', 'provider', 'region', 'tier', 'leader', 'workers', 'nomad_addr', 'daemon_url', 'daemon_token', 'caddy_admin', 'created_at']
  leader_keys = ['ip', 'id', 'size']
  for k in required_keys:
      assert k in d, f'Missing key: {k}'
  for k in leader_keys:
      assert k in d['leader'], f'Missing leader key: {k}'
  assert d.get('demo') == True, 'demo field missing or not True'
  print('ALL_KEYS_PRESENT')
  "
      2. Assert: output contains 'ALL_KEYS_PRESENT'
    Expected Result: Demo JSON has all required keys with demo=true
    Evidence: .sisyphus/evidence/task-10-demo-json-complete.txt
  ```

  **Commit**: YES (with Tasks 5,6,7,8,9)
  - Message: `feat(provision): add demo mode JSON support for all commands`
  - Files: `src/mesh/cli/commands/init_json.py`, `src/mesh/cli/commands/destroy.py`, `src/mesh/cli/commands/add_worker.py`

---

- [x] 11. **End-to-End Verification: init --output json** — verify JSON shapes match spec §6.2

  **What to do**:
  - Run `mesh init --output json --demo` with various arg combinations and validate:
    - **Happy path**: All required args → exit 0, valid JSON on stdout matching spec shape exactly
    - **Missing args**: Missing `--region` → exit 1, error JSON on stderr with `missing_args`
    - **Invalid provider**: `--provider badcloud` → exit 1, error JSON with `available_providers`
    - **Workers=0 (Lite tier)**: JSON has `tier: "lite"`, `workers: []`
    - **Workers=2 (Standard tier)**: JSON has `tier: "standard"`, 2 worker entries
    - **Without --daemon-token**: init still works (daemon not installed, but JSON still valid)
  - Validate EXACT field names, types, and nesting against spec §6.2:
    - Top-level: `cluster_id`, `provider`, `region`, `tier`, `leader`, `workers`, `nomad_addr`, `daemon_url`, `daemon_token`, `caddy_admin`, `created_at`
    - Leader: `ip`, `id`, `size`
    - Worker: same shape as leader (when workers > 0)
  - Verify stdout contains ONLY JSON (no ANSI codes, no Rich markup) — pipe through `python -m json.tool` must succeed
  - Verify stderr is empty on success

  **Must NOT do**:
  - Do NOT run real cloud provisioning (use `--demo` flag only)
  - Do NOT modify code during verification — this is pure QA

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Systematic QA with multiple test cases, spec validation, output inspection

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 12, 13
  - **Parallel Group**: Wave 3
  - **Blocks**: None (final verification)
  - **Blocked By**: Tasks 6, 7

  **References**:
  - Spec §6.2 lines 346-375 — Exact JSON output for init
  - Spec §6.2 lines 377-385 — Error JSON shape
  - `src/mesh/cli/commands/init_json.py` — Implementation under test

  **Acceptance Criteria**:
  - [ ] All 6 test cases above pass
  - [ ] JSON from `--output json` parses cleanly with `json.load()`
  - [ ] Exit codes correct (0 for success, 1 for errors)
  - [ ] Error JSON on stderr, NOT stdout

  **QA Scenarios**:

  ```
  Scenario: Full spec compliance — init JSON matches §6.2 exactly
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --output json --demo --provider digitalocean --region nyc3 --workers 0 --leader-size s-2vcpu-4gb --api-key test-key --daemon-token tok123 --daemon-url https://example.com/daemon --cluster-name spec-test 2>/dev/null | python -c "
  import sys, json
  d = json.load(sys.stdin)
  # Exact field validation per §6.2
  assert d['cluster_id'] == 'spec-test', f'cluster_id mismatch: {d[\"cluster_id\"]}'
  assert d['provider'] == 'digitalocean'
  assert d['region'] == 'nyc3'
  assert d['tier'] in ('lite', 'standard')
  assert 'ip' in d['leader'] and 'id' in d['leader'] and 'size' in d['leader']
  assert isinstance(d['workers'], list)
  assert 'nomad_addr' in d and d['nomad_addr'].startswith('http://')
  assert 'daemon_url' in d and d['daemon_url'].startswith('https://')
  assert 'daemon_token' in d
  assert 'caddy_admin' in d
  assert 'created_at' in d
  assert d['demo'] == True
  print('SPEC_COMPLIANT')
  "
      2. Assert: output contains 'SPEC_COMPLIANT'
    Expected Result: All spec-required fields present with correct types
    Failure Indicators: KeyError on any field, type mismatch, wrong nested structure
    Evidence: .sisyphus/evidence/task-11-spec-compliance.txt

  Scenario: Error handling — missing required arg
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --output json --provider digitalocean 2>stderr.txt; echo "EXIT=$?"
      2. Cat stderr.txt, validate: valid JSON, has error.code, error.message mentions missing argument
      3. Assert: EXIT=1
      4. Assert: stdout is empty or only whitespace
    Expected Result: Error JSON on stderr, exit 1, no stdout
    Evidence: .sisyphus/evidence/task-11-error-missing-arg.txt

  Scenario: Error handling — invalid provider
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --output json --provider badcloud --region nyc3 --api-key test-key 2>stderr.txt; echo "EXIT=$?"
      2. Assert: stderr JSON contains error with code 'unknown_provider' and available_providers list
      3. Assert: EXIT=1
    Expected Result: Error JSON with available providers listed
    Evidence: .sisyphus/evidence/task-11-error-invalid-provider.txt

  Scenario: stdout is pure JSON (no ANSI/Rich contamination)
    Tool: Bash
    Steps:
      1. Run: python -m mesh init --output json --demo --provider digitalocean --region nyc3 --workers 0 --leader-size s-2vcpu-4gb --api-key test-key --daemon-token tok --daemon-url http://ex.com/d --cluster-name clean-test 2>/dev/null > raw_stdout.txt
      2. Check: python -c "
  content = open('raw_stdout.txt').read()
  assert content.strip().startswith('{'), f'Does not start with {{: {content[:50]}}'
  assert '\x1b' not in content, 'ANSI escape codes found in stdout'
  import json; json.loads(content)
  print('CLEAN_JSON')
  "
      3. Assert: output contains 'CLEAN_JSON'
    Expected Result: stdout starts with '{', no ANSI codes, valid JSON
    Evidence: .sisyphus/evidence/task-11-clean-stdout.txt
  ```

  **Commit**: YES (with Tasks 12,13)
  - Message: `test(provision): verify init --output json spec compliance`
  - Files: `.sisyphus/evidence/task-11-*.txt`

---

- [x] 12. **End-to-End Verification: destroy --output json** — verify teardown JSON

  **What to do**:
  - Run `mesh destroy --output json --demo` with various arg combinations and validate:
    - **Happy path**: `--cluster test --api-key test-key --yes` → exit 0, valid destroy JSON
    - **Without --cluster**: uses default → JSON output with default cluster name
    - **Without --api-key**: error JSON (if no Infisical env fallback)  [OUTDATED — see SECRETS-PROTOCOL.md]
  - Validate JSON shape against spec §6.2:
    ```json
    {"cluster_id": "test-cluster", "destroyed": true, "resources_cleaned": [...]}
    ```
  - Verify backward compat: `mesh destroy --demo --yes` (no `--output json`) → Rich output

  **Must NOT do**:
  - Do NOT run real destroy operations (use `--demo` flag only)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Systematic QA across multiple test cases

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 11, 13
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: Task 8

  **References**:
  - Spec §6.2 lines 397-404 — Destroy JSON shape
  - `src/mesh/cli/commands/destroy.py` — Implementation under test

  **Acceptance Criteria**:
  - [ ] All test cases pass
  - [ ] Destroy JSON matches spec shape
  - [ ] Interactive mode unchanged

  **QA Scenarios**:

  ```
  Scenario: destroy --output json --demo produces valid JSON
    Tool: Bash
    Steps:
      1. Run: python -m mesh destroy --output json --demo --cluster test-cluster --api-key test-key --yes 2>/dev/null | python -c "
  import sys, json
  d = json.load(sys.stdin)
  assert d['cluster_id'] == 'test-cluster'
  assert d['destroyed'] == True
  assert isinstance(d['resources_cleaned'], list)
  assert d['demo'] == True
  print('DESTROY_JSON_OK')
  "
      2. Assert: output contains 'DESTROY_JSON_OK'
    Expected Result: Valid destroy JSON matching spec
    Evidence: .sisyphus/evidence/task-12-destroy-json.txt

  Scenario: destroy interactive mode still shows Rich output
    Tool: Bash
    Steps:
      1. Run: python -m mesh destroy --demo --yes 2>&1
      2. Assert: exit code 0
      3. Assert: output does NOT contain '{' at start (not JSON)
      4. Assert: output contains Rich-styled text
    Expected Result: Rich output, no JSON
    Evidence: .sisyphus/evidence/task-12-interactive-compat.txt
  ```

  **Commit**: YES (with Tasks 11,13)
  - Message: `test(provision): verify destroy --output json spec compliance`
  - Files: `.sisyphus/evidence/task-12-*.txt`

---

- [x] 13. **End-to-End Verification: Backward Compatibility** — existing behavior preserved

  **What to do**:
  - Run ALL existing commands that should NOT be affected and verify they work unchanged:
    - `mesh init --demo` (interactive wizard) — questionary prompts work
    - `mesh init --provider DigitalOcean --region nyc3 --workers 1 --yes --demo` — Rich output
    - `mesh deploy --demo my-app --image nginx:latest` — works as before
    - `mesh status --demo` — works as before
    - `mesh logs --demo` — works as before
    - `mesh ssh --demo` — works as before
    - `mesh doctor --demo` — works as before
    - `mesh version` — works as before
    - `mesh compare` — works as before
    - `mesh roadmap` — works as before
  - Run existing test suite: `python -m pytest src/mesh -x -q -m "not e2e"` — all existing tests must pass
  - Verify NO JSON output leaks when `--output json` is NOT set
  - Verify `--yes` flag still works (skips confirmation in interactive mode, shows Rich output)

  **Must NOT do**:
  - Do NOT skip any existing test
  - Do NOT mark failing tests as "acceptable" — if a test fails, fix the regression

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Broad regression testing across all commands, test suite execution

  **Parallelization**:
  - **Can Run In Parallel**: YES — with Tasks 11, 12
  - **Parallel Group**: Wave 3
  - **Blocks**: None
  - **Blocked By**: Task 9

  **References**:
  - `src/mesh/cli/main.py` — All command registrations
  - `pyproject.toml:140-163` — Pytest configuration
  - `src/mesh/cli/CONTEXT.md` — Existing command reference

  **Acceptance Criteria**:
  - [ ] All 10 commands above work unchanged
  - [ ] `python -m pytest src/mesh -x -q -m "not e2e"` → ALL pass
  - [ ] No Rich output regression (colors, panels, progress bars all render)
  - [ ] No JSON output when `--output json` is NOT set

  **QA Scenarios**:

  ```
  Scenario: Existing test suite passes unchanged
    Tool: Bash
    Steps:
      1. Run: cd /Users/samanvayayagsen/project/rp-launch/mesh-workspace/mesh-provision && python -m pytest src/mesh -x -q -m "not e2e" --tb=short 2>&1
      2. Assert: exit code 0
      3. Assert: no FAILED test names in output
    Expected Result: All existing tests pass
    Failure Indicators: Any test failure, exit code != 0
    Evidence: .sisyphus/evidence/task-13-test-suite-outcome.txt

  Scenario: deploy command unchanged
    Tool: Bash
    Steps:
      1. Run: python -m mesh deploy --demo test-app --image nginx:latest 2>&1
      2. Assert: exit code 0
      3. Assert: output contains Rich content (not JSON)
    Expected Result: deploy works identically
    Evidence: .sisyphus/evidence/task-13-deploy-unchanged.txt
  ```

  **Commit**: YES (with Tasks 11,12)
  - Message: `test(provision): verify backward compatibility of all existing commands`
  - Files: `.sisyphus/evidence/task-13-*.txt`

---

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle` APPROVED: 5/5 Must Have, 7/7 Must NOT Have, 10/10 Deliverables
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high` APPROVED: ~476 pass, 0 regressions, no critical violations
  Run `python -m pytest src/mesh -x -q` (existing tests). Review all changed files for: `as any` equivalents, bare excepts, print() instead of JSON, Rich imports in JSON path. Check backward compat: existing init/destroy tests still pass.
  Output: `Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` APPROVED: 6/6 scenarios, 3/3 integration
  Execute EVERY QA scenario from EVERY task. Test cross-task integration. Test edge cases from Metis list (partial failure, missing args, invalid provider, IP timeout, demo+json). Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep` APPROVED: 10/10 compliant, 1 minor note
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec. Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(provision): add JSON mode CLI flags and daemon boot script`
- **Wave 2**: `feat(provision): implement JSON output mode for init, destroy, add-worker`
- **Wave 3**: `test(provision): verify JSON output mode and backward compatibility`

---

## Success Criteria

### Verification Commands

```bash
# JSON mode init (simulated)
mesh init --output json --demo --provider digitalocean --region nyc3 --workers 0 \
  --leader-size s-2vcpu-4gb --api-key test --daemon-token tok --daemon-url https://example.com/mesh-daemon | python -m json.tool

# JSON mode destroy
mesh destroy --output json --demo --cluster test-cluster --api-key test --yes | python -m json.tool

# Backward compatibility
echo "Local (Multipass)" | mesh init --yes --demo
# Must show Rich output, exit 0

# Boot script: daemon present with token
python -c "
from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import generate_shell_script
result = generate_shell_script('tskey-test', '10.0.0.1', 'server', daemon_token='mytok', daemon_url='https://example.com/daemon')
assert 'mesh-daemon' in result
assert 'mytok' in result
assert 'systemctl enable mesh-daemon' in result
print('PASS')
"

# Boot script: daemon absent without token
python -c "
from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import generate_shell_script
result = generate_shell_script('tskey-test', '10.0.0.1', 'server')
assert 'mesh-daemon' not in result
print('PASS')
"
```

### Final Checklist

- [ ] `mesh init --output json ...` returns exact spec §6.2 JSON on stdout
- [ ] `mesh init` without `--output json` shows Rich output, questionary works
- [ ] `mesh destroy --output json ...` returns exact spec §6.2 JSON
- [ ] `mesh add-worker --output json ...` returns exact spec §6.2 JSON
- [ ] Boot script installs daemon when `--daemon-token` provided
- [ ] Boot script unchanged when `--daemon-token` absent
- [ ] All existing tests pass
- [ ] All Guardrails (G1-G7) satisfied
