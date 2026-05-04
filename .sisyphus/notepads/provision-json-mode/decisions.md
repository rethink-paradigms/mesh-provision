# Architecture Decisions — provision-json-mode

## Key Decisions

### 1. Direct Libcloud vs Pulumi for JSON mode
- JSON mode uses direct Libcloud (bypasses Pulumi)
- Interactive mode stays with Pulumi (unchanged)
- No import of Pulumi or automation.py in JSON path

### 2. Daemon scope
- Install only on leader (ROLE="server")
- Gated by daemon_token + daemon_url presence
- systemd unit: mesh-daemon.service, binary: /usr/local/bin/mesh-daemon
- Config: /etc/mesh/config.yaml
- Idempotent: checks existing binary before installing

### 3. Output format
- JSON to stdout on success, exit 0
- Error JSON to stderr, exit 1
- No Rich/ANSI in JSON mode
- Demo mode includes "demo": true field

### 4. Credential resolution
- --api-key wins if provided
- Falls back to .env if not provided
- Single-token providers only (DO, Linode, Vultr)

### 5. Error codes
- missing_required_args → missing CLI args
- unknown_provider → invalid provider
- missing_credentials → no API key
- provision_failed → provisioning error with phase

## Audit Findings (F1)

### Plan Compliance: APPROVE

Must Have: 5/5 PASS
1. CLI args enforced in JSON mode
2. Rich/ANSI suppressed
3. Direct Libcloud provisioning
4. Daemon gated by ROLE=server
5. Boot script idempotent

Must NOT Have: 7/7 PASS
G1-G7 all verified

Deliverables: 10/10 PASS
All files exist and match plan

Test Results: 377 passed, 3 pre-existing failures unrelated
