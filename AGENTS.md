# mesh-provision — Agent Guide

> What an agent needs to know to work in `code/mesh-provision/`

## Purpose

Python **HTTP provisioning service** that creates and destroys cloud VMs, bootstraps the infrastructure stack (Docker, Tailscale, Caddy, Nomad), and injects the mesh-daemon config via cloud-init. **Called by agent-bodies via HTTP API (port 8100)** — never called directly.

## Quick Start

```bash
# Run all tests (fast, no cluster required)
pytest src/mesh -m "not e2e"

# Run with coverage (default via pyproject.toml)
pytest src/mesh -m "not e2e"

# Run specific test module
pytest src/mesh/commands/test_init.py -v

# 🔐 Start the HTTP server (production path)
make up-mesh-provision

# Or manually
cd code/mesh-provision && infisical run -- uvicorn mesh.http_server:app --host 127.0.0.1 --port 8100

# 🔐 Dev/debug only — bypass the manifest guard to use the legacy CLI
MESH_PROVISION_ALLOW_DIRECT=1 infisical run -- python -m mesh init --provider "Local (Multipass)" --workers 0
MESH_PROVISION_ALLOW_DIRECT=1 infisical run -- python -m mesh status
```

> **Secrets:** This workspace uses [Infisical](https://app.infisical.com) for secret
> management. Cloud credentials (`DIGITALOCEAN_API_TOKEN`, `TAILSCALE_KEY`, etc.)
> are managed there. Run `make up-mesh-provision` from workspace root to auto-inject secrets.

## Key Conventions

- **Tests live next to source**: `src/mesh/commands/init.py` → `src/mesh/commands/test_init.py`
- **pytest config in `pyproject.toml`**: markers, coverage, testpaths all defined there
- **HTTP entry**: `mesh/http_server.py` (FastAPI on port 8100) — **this is the primary interface**
- **Legacy CLI**: `src/mesh/entrypoint.py` — mechanically blocked in production by `manifest.py`; only available via `MESH_PROVISION_ALLOW_DIRECT=1` for dev/E2E
- **Production guard**: MANIFEST.yaml declares `direct_use: false`. The HTTP API (port 8100) is unaffected.
- **Black + isort + mypy**: `black src/`, `isort src/`, `mypy src/mesh`

## Navigation

| File | What It Is |
|------|------------|
| [`MANIFEST.yaml`](MANIFEST.yaml) | Capability declarations, usage rules, protocol info |
| [`README.md`](README.md) | Full project documentation |
| [`pyproject.toml`](pyproject.toml) | Dependencies, tool configs (pytest, black, mypy, coverage) |
| File | What It Is |
|------|------------|
| [`MANIFEST.yaml`](MANIFEST.yaml) | Capability declarations, usage rules, protocol info (HTTP + legacy CLI) |
| [`README.md`](README.md) | Full project documentation |
| [`pyproject.toml`](pyproject.toml) | Dependencies, tool configs (pytest, black, mypy, coverage) |
| [`../../specs/SPEC-MESH-PROVISION.md`](../../specs/SPEC-MESH-PROVISION.md) | Required changes spec (G1, G8, G9) |
| [`../../knowledge/architecture/INDEX.md`](../../knowledge/architecture/INDEX.md) | System architecture index |
| `src/mesh/http_server.py` | **HTTP server (FastAPI, port 8100)** — primary interface |
| `src/mesh/provisioning/` | VM provisioning, boot scripts, health checks |
| `src/mesh/manifest.py` | MANIFEST.yaml loader and direct-use guard — blocks CLI unless bypassed |
| `src/mesh/providers/` | Cloud provider drivers (Libcloud) |
| `src/mesh/tiers/` | Tier configuration (solo, cluster) |
| `src/mesh/commands/` | Legacy CLI commands (blocked by manifest.py in production) |
| [`../../SECRETS-PROTOCOL.md`](../../SECRETS-PROTOCOL.md) | Workspace secret management — env keys, Infisical sync, agent checklist |
| [`../../.workspace-secrets.yml`](../../.workspace-secrets.yml) | The ONE file where humans paste secret values |

## Links

- Root AGENTS.md: `../../AGENTS.md` — workspace-wide rules and boundaries
- Contracts: `../../contracts/mesh-provision.interface.md` — HTTP + legacy protocol docs
