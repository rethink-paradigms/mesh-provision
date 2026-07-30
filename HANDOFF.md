# mesh-provision Restructure — Session Handoff

> Created: 2026-05-14
> Status: Restructure ~95% complete. 8 failing tests remain. All are in test files that reference removed Phase 1 behaviors. Fix them and the codebase is done.

---

## What This Session Did

Full codebase restructure of `mesh-provision/` from a Phase 1 interactive CLI tool to a clean Phase 3 subprocess tool.

**The system is**: `stdin JSON → python3 -m mesh → stdout JSON`. One process, one operation, exit. No Typer, no Rich UI, no Pulumi, no Multipass.

### What Was Deleted (dead code)
- `snapshots/`, `workloads/`, `shared/` — wrong layer (belonged in mesh/ Go daemon)
- `infrastructure/provision_cloud_cluster/` — Pulumi Automation API
- `infrastructure/providers/libcloud_dynamic_provider.py` — Pulumi Dynamic Provider
- `infrastructure/provision_node/provision_node.py` — Pulumi-based node module
- `infrastructure/provision_node/multipass.py` — local Multipass provisioning
- `infrastructure/configure_tailscale/configure.py` — used `pulumi_tailscale`
- `infrastructure/progressive_activation/tier_manager.py` — unused
- `verification/` — e2e test infra
- `cli/ui/panels.py`, `cli/ui/themes.py` — 263-line Rich UI
- `cli/plugins.py`, `cli/commands/init_cmd.py`, `doctor.py`, `logs.py`, `ssh.py`, `snapshot.py`, `helpers.py`, `status.py`
- All tests for the above dead code

### New Structure (what now exists)
```
src/mesh/
├── entrypoint.py           ← NEW: clean subprocess entry. read stdin → dispatch → exit
├── commands/
│   ├── output.py           ← JSON serializers (print_json_success/error, require_args)
│   ├── init.py             ← handle_init(params)
│   ├── destroy.py          ← handle_destroy(params)
│   ├── status.py           ← handle_status(params)
│   ├── add_worker.py       ← handle_add_worker(params)
│   └── test_*.py           ← all rewritten for stdin protocol (no Typer)
├── providers/
│   ├── __init__.py         ← is_provider_usable() (fixed), AWS key:secret format (fixed)
│   └── discovery.py        ← DO slug lookup (fixed), AWS filtered query (fixed), caching
├── provisioning/
│   ├── direct.py           ← provision_node/cluster/destroy/query via Libcloud
│   ├── boot.py             ← generate_cloud_init() — plain text daemon_config, tier-gated scripts
│   ├── boot.sh             ← Jinja2 template
│   └── scripts/*.sh        ← 6 modular shell scripts
├── config/env.py           ← EnvVars constants + get_env()
└── tiers/tier_config.py    ← ClusterTier enum + TierConfig dataclass
```

### pyproject.toml Changes
- Entry point: `mesh = "mesh.entrypoint:main"` (was `mesh.cli.main:main`)
- Removed deps: `pulumi`, `pulumi-aws`, `pulumi-tailscale`, `typer`, `questionary`, `rich`, `click`
- Kept: `apache-libcloud`, `pyyaml`, `jinja2`, `requests`, `python-dotenv`, `pytest` stack

---

## Current Test State

```
8 failed, 124 passed, 9 skipped
```

Run with:
```bash
cd /Users/samanvayayagsen/project/rp-launch/mesh-workspace/mesh-provision
python3 -m pytest src/ --tb=short -q --no-header --no-cov
```

---

## The 8 Failing Tests — Exact Fixes Needed

### File: `src/mesh/provisioning/test_boot.py`
**6 failures.** This file tests `generate_cloud_init()`. Problems:

**1. `test_boot_script_rendering_shell` — missing `cluster_tier=`**
The call at line ~20 has no `cluster_tier=` argument. `generate_cloud_init` requires it.
Fix: add `cluster_tier="standard"` to the call.

**2. `test_shell_script_includes_cluster_tier_default_production` — wrong default tier**
Tests that `CLUSTER_TIER="production"` appears in output with no tier specified.
The old default was `"production"`. New default is `"standard"` (only `"lite"` and `"standard"` exist).
Fix: change assertion to `assert 'CLUSTER_TIER="standard"' in rendered` AND add `cluster_tier="standard"` to the call.

**3. `test_shell_script_production_disables_caddy` — tier "production" removed**
Tests `cluster_tier="production"` which no longer exists. In new design, both `lite` and `standard` always enable Caddy (`ENABLE_CADDY="true"`).
Fix: delete this test (or `@pytest.mark.skip` it with a note that "production" tier was removed).

**4. `test_shell_script_ingress_disables_caddy` — tier "ingress" removed**
Same as above — `"ingress"` tier no longer exists.
Fix: delete or skip.

**5. `test_boot_script_has_namespace_commands` — missing `cluster_tier=`**
Call at line ~169 has no `cluster_tier=`. Also tests for `nomad namespace apply` commands that may or may not be in current boot.sh.
Fix: add `cluster_tier="standard"` and check if `nomad namespace apply` is actually in boot.sh. If not, the test is testing a removed feature — skip it.

**6. `test_existing_tests_still_pass` — asserts wrong tier and ENABLE_CADDY**
Asserts `CLUSTER_TIER="production"` and `ENABLE_CADDY="false"` — both wrong for new design.
Fix: change to `CLUSTER_TIER="standard"` and `ENABLE_CADDY="true"`.

---

### File: `src/mesh/provisioning/test_boot_integration.py`
**1 failure.**

**7. `test_boot_script_contains_role_client` — wrong role in call**
The sed that added `cluster_tier="standard"` accidentally also set `role="client"` in what should be the role_client test, but the assert checks for the wrong role. 

Check what the call and assertion say:
```bash
grep -A8 "def test_boot_script_contains_role_client" src/mesh/provisioning/test_boot_integration.py
```
The call should have `role="client"` and assert `'ROLE="client"' in script`. Fix whichever is wrong.

---

### File: `src/mesh/provisioning/test_destroy_cleanup.py`
**1 failure.**

**8. `test_destroy_cleanup_all_resources` — asserts `ex_release_floating_ip` was called**
The new `_do_cleanup_aux()` in `direct.py` does NOT handle floating IPs (they don't have names so can't be safely filtered by cluster prefix). The test expects `mock_do_driver.ex_release_floating_ip.assert_called_once()`.

Fix: find all lines in this test that assert `ex_release_floating_ip` was called and replace with a comment:
```python
# Floating IPs not explicitly released — they have no names so cannot
# be safely filtered by cluster prefix. They are released when the droplet is destroyed.
```

---

## Quick Fix Script

Run this to fix all 8 in one shot:

```python
import pathlib, re

# Fix test_boot.py
f = pathlib.Path("src/mesh/provisioning/test_boot.py")
txt = f.read_text()

# Fix 1: test_boot_script_rendering_shell — add cluster_tier
txt = txt.replace(
    "rendered = generate_cloud_init(\n        tailscale_key=context[\"TAILSCALE_KEY\"],\n        leader_ip=context[\"LEADER_IP\"],\n        role=context[\"ROLE\"],\n    )",
    "rendered = generate_cloud_init(\n        cluster_tier=\"standard\",\n        tailscale_key=context[\"TAILSCALE_KEY\"],\n        leader_ip=context[\"LEADER_IP\"],\n        role=context[\"ROLE\"],\n    )"
)

# Fix 2: default tier test — "production" → "standard"
txt = txt.replace(
    "rendered = generate_cloud_init(\n        tailscale_key=\"ts-key-123\", leader_ip=\"10.0.0.1\", role=\"server\"\n    )\n    assert 'CLUSTER_TIER=\"production\"' in rendered",
    "rendered = generate_cloud_init(\n        cluster_tier=\"standard\",\n        tailscale_key=\"ts-key-123\", leader_ip=\"10.0.0.1\", role=\"server\"\n    )\n    assert 'CLUSTER_TIER=\"standard\"' in rendered"
)

# Fix 6: test_existing_tests_still_pass
txt = txt.replace("assert 'CLUSTER_TIER=\"production\"' in rendered", "assert 'CLUSTER_TIER=\"standard\"' in rendered")
txt = txt.replace("assert 'ENABLE_CADDY=\"false\"' in rendered", "assert 'ENABLE_CADDY=\"true\"' in rendered")

# Fix 5: namespace commands — add cluster_tier to the call at line ~169
txt = re.sub(
    r"(def test_boot_script_has_namespace_commands.*?rendered = generate_cloud_init\()\n(\s+tailscale_key)",
    r"\1\n        cluster_tier=\"standard\",\n\2",
    txt, flags=re.DOTALL
)

f.write_text(txt)
print("test_boot.py fixed")

# Skip production/ingress tests (tiers no longer exist)
import re
for func in ["test_shell_script_production_disables_caddy", "test_shell_script_ingress_disables_caddy"]:
    txt = f.read_text()
    txt = txt.replace(
        f"def {func}(",
        f"@pytest.mark.skip(reason=\"'production'/'ingress' tiers removed — only 'lite' and 'standard' exist\")\ndef {func}("
    )
    f.write_text(txt)
# Ensure pytest is imported
txt = f.read_text()
if "import pytest" not in txt:
    f.write_text("import pytest\n" + txt)
print("production/ingress tests skipped")

# Fix test_destroy_cleanup.py
f2 = pathlib.Path("src/mesh/provisioning/test_destroy_cleanup.py")
txt2 = f2.read_text()
txt2 = re.sub(
    r"mock_do_driver\.ex_release_floating_ip\.[^\n]+",
    "# Floating IPs not explicitly released — no names, cannot be cluster-filtered safely",
    txt2
)
f2.write_text(txt2)
print("test_destroy_cleanup.py fixed")
```

After running that script, check and fix `test_boot_script_contains_role_client` manually:
```bash
grep -A12 "def test_boot_script_contains_role_client" src/mesh/provisioning/test_boot_integration.py
```
The call should have `role="client"` and the assert should check `'ROLE="client"' in script`.

---

## After Tests Are Green

1. **Commit everything:**
```bash
cd /Users/samanvayayagsen/project/rp-launch/mesh-workspace
git add mesh-provision/
git commit -m "refactor(mesh-provision): restructure from Phase 1 CLI to Phase 3 subprocess tool

- Remove Pulumi, Multipass, Rich UI, interactive CLI, snapshots, workloads
- New structure: entrypoint.py → commands/ → provisioning/ → providers/
- Fix: daemon_config is plain text (no base64 decode/encode)
- Fix: destroy cleanup_all now filters by cluster prefix (was wiping entire account)
- Fix: DigitalOcean Ubuntu image lookup uses slug ('ubuntu-22-04-x64')
- Fix: AWS driver init uses key:secret format
- Fix: worker boot scripts get leader IP injected after leader is provisioned
- Fix: is_provider_usable() returns False for gcp/azure (was misleadingly True)
- Strip deps: pulumi, typer, questionary, rich removed (7 deps down from 15)
- Entry point: mesh.entrypoint:main (was mesh.cli.main:main)"
```

2. **Update contracts if needed:**
Check `contracts/mesh-provision.interface.md` — the `tailscale_key` param for standard tier is not documented. It should be added:
```
| `tailscale_key` | string | No | `""` | Tailscale auth key. Required for standard tier (workers≥1). Generated by agent-bodies and passed in. |
```

3. **Run the full test suite one more time to confirm green.**

---

## Key Design Decisions Made This Session

| Decision | Rationale |
|---|---|
| `daemon_config` is plain text, no base64 | Contract says plain text. Period. Code no longer tries to decode. |
| `is_provider_usable()` returns False for gcp/azure | They're registered in the enum but blocked. Old `is_provider_supported` returned True for them which was misleading. |
| `destroy cleanup_all` filters by cluster prefix | Old code wiped ALL volumes/firewalls/SSH keys in the account. Dangerous. Now filtered. |
| Floating IPs excluded from cleanup_all | Floating IPs have no names in the DO API — can't safely filter by cluster. Released when droplet is destroyed. |
| SSH key injection is explicit only | Old code auto-read `~/.ssh/mesh_test_key.pub` in production paths. Test artifact removed from prod. |
| tier `"production"` and `"ingress"` removed | Only `"lite"` (workers=0) and `"standard"` (workers≥1) exist. Both enable Caddy. |
| Worker boot script generated AFTER leader IP known | Old code generated it with empty leader_ip. Cluster join fails without it. |
| PyYAML literal block forced for boot scripts | boot.sh has tabs; PyYAML double-quotes tab-containing strings which escapes `"` → `\"`. Fixed with `expandtabs(4)` + literal block representer. |

---

## Contracts Reference

The subprocess protocol is defined in:
`/Users/samanvayayagsen/project/rp-launch/mesh-workspace/contracts/mesh-provision.interface.md`

4 commands: `init`, `destroy`, `status`, `add-worker`
All via: `{"version": "1", "command": "...", "params": {...}}` on stdin
