# mesh-provision — Agent Guide

> What an agent needs to know to work in `code/mesh-provision/`

## Purpose

Python CLI that provisions cloud VMs, bootstraps Nomad/Consul/Docker/Tailscale/Caddy, and injects Mesh daemon config via cloud-init. **Always spawned by agent-bodies as a subprocess** — never called directly.

## Quick Start

```bash
# Run all tests (fast, no cluster required)
pytest src/mesh -m "not e2e"

# Run with coverage (default via pyproject.toml)
pytest src/mesh -m "not e2e"

# Run specific test module
pytest src/mesh/commands/test_init.py -v

# 🔐 Run the CLI locally (secrets injected from Infisical)
# Make sure you've done `pip install -e .` first, then:
cd ../.. && infisical run -- python -m mesh init --provider "Local (Multipass)" --workers 0
cd ../.. && infisical run -- python -m mesh status
cd ../.. && infisical run -- python -m mesh destroy --yes
```

> **Secrets:** This workspace uses [Infisical](https://app.infisical.com) for secret
> management. Cloud credentials (`DIGITALOCEAN_API_TOKEN`, `TAILSCALE_KEY`, etc.)
> are managed there. Run `infisical run -- python -m mesh ...` from workspace root
> to inject secrets.

## Key Conventions

- **Tests live next to source**: `src/mesh/commands/init.py` → `src/mesh/commands/test_init.py`
- **pytest config in `pyproject.toml`**: markers, coverage, testpaths all defined there
- **CLI entry**: `mesh` command → `src/mesh/entrypoint.py`
- **Stdin JSON protocol v1**: see `contracts/mesh-provision-protocol.md`
- **No direct CLI use in production**: MANIFEST.yaml declares `direct_use: false`
- **Black + isort + mypy**: `black src/`, `isort src/`, `mypy src/mesh`

## Navigation

| File | What It Is |
|------|------------|
| [`MANIFEST.yaml`](MANIFEST.yaml) | Capability declarations, usage rules, protocol info |
| [`README.md`](README.md) | Full project documentation |
| [`pyproject.toml`](pyproject.toml) | Dependencies, tool configs (pytest, black, mypy, coverage) |
| [`../../specs/SPEC-MESH-PROVISION.md`](../../specs/SPEC-MESH-PROVISION.md) | Required changes spec (G1, G8, G9) |
| [`../../knowledge/architecture/INDEX.md`](../../knowledge/architecture/INDEX.md) | System architecture index |
| `src/mesh/commands/` | CLI commands: init, status, destroy, add-worker, remove-worker |
| `src/mesh/provisioning/` | VM provisioning, boot scripts, health checks |
| `src/mesh/providers/` | Cloud provider drivers (Libcloud) |
| `src/mesh/tiers/` | Tier configuration (lite, standard) |
| [`../../SECRETS-PROTOCOL.md`](../../SECRETS-PROTOCOL.md) | Workspace secret management — env keys, Infisical sync, agent checklist |
| [`../../.workspace-secrets.yml`](../../.workspace-secrets.yml) | The ONE file where humans paste secret values |

## Links

- Root AGENTS.md: `../../AGENTS.md` — workspace-wide rules and boundaries
- Contracts: `../../contracts/mesh-provision-protocol.md` — stdin JSON protocol
- Contracts: `../../contracts/mesh-provision-schema.json` — JSON Schema for validation
