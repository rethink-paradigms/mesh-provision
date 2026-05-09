# Learnings: handoff-03-provisioner-protocol

## Task 1 — Parameterize _run_destroy_json()

- `print_json_error()` already supports an `available_providers` kwarg — no changes needed there.
- Provider validation follows the existing pattern from `providers/__init__.py`: check `provider not in PROVIDER_ENUMS or provider in UNSUPPORTED_PROVIDERS`.
- `UNSUPPORTED_PROVIDERS` is a `frozenset({"gcp", "google", "azure"})`.
- `run_destroy()` is the CLI-mode entrypoint — it now passes `provider="digitalocean"` and `region=""` defaults to maintain backward compatibility.
- The `_run_destroy_json()` function uses local imports (inside the function body), so `PROVIDER_ENUMS` and `UNSUPPORTED_PROVIDERS` are imported locally too — consistent with the existing pattern.
- All 2 existing destroy JSON tests pass unchanged.
