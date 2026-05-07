# Blockers

## T8: Real DO Token E2E Verification
- **Status**: BLOCKED
- **Attempts**: 1
- **Reason**: DO API returns "Unable to authenticate you" — token in `.env` is invalid/expired
  - Token format looks correct (`dop_v1_...`, 71 chars)
  - Direct `curl` to `api.digitalocean.com/v2/account` also returns 401
  - NOT a mesh-provision code issue
- **Impact**: Cannot provision real droplet to verify health endpoint works end-to-end
- **Workaround**: Mock-based tests (T3, T5, T7) verify the logic paths. Health check polling uses sleep-first pattern matching `_poll_for_ip()`. Caddyfile generation verified via grep. Transform functions verified via 28 unit tests.
- **Resolution**: Generate a new DO API token at https://cloud.digitalocean.com/account/api/tokens, update `.env`, and re-run T8
