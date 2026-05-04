# F3. Real Manual QA — Evidence

**Date:** Mon May 4 2026  
**Run by:** Sisyphus-Junior

## Test Results

| # | Scenario | Result |
|---|----------|--------|
| T1 | `init --output json --demo` — JSON shape: cluster_id, tier=lite, demo=True | ✓ PASS |
| T2 | `destroy --output json --demo` — JSON shape: destroyed=True, demo=True | ✓ PASS |
| T3 | `add-worker --output json --demo` — JSON shape: demo=True | ✓ PASS |
| T4 | Interactive backward compat (no --output json) — non-JSON output, non-empty | ✓ PASS |
| T5 | Boot script WITH daemon params — contains `bash scripts/11-install-daemon.sh` and token | ✓ PASS |
| T6 | Boot script WITHOUT daemon params — no `bash scripts/11-install-daemon.sh`, no `mesh-daemon` | ✓ PASS |

## Fix Applied

**Test 6 initially FAILED.** Root cause: `boot.sh` used a shell-level conditional for the daemon section:

```bash
# OLD (shell runtime check — line always present in rendered output)
if [ "$ROLE" = "server" ] && [ -n "$DAEMON_TOKEN" ] && [ -n "$DAEMON_URL" ]; then
    bash scripts/11-install-daemon.sh
fi
```

Fixed by converting to a Jinja2-level conditional (template-time check):

```jinja2
{% if DAEMON_TOKEN and DAEMON_URL %}
# Daemon install (leader only, token + URL provided at provision time)
if [ "$ROLE" = "server" ]; then
    bash scripts/11-install-daemon.sh
fi
{% endif %}
```

This means `bash scripts/11-install-daemon.sh` is absent from the rendered script when no daemon params are passed.

## Summary

```
Scenarios [6/6 pass] | Integration [3/3] | Edge Cases [2 tested] | VERDICT: APPROVE
```
