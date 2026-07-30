# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

<!-- towncrier release notes start -->

## [0.4.0] - 2026-04-22

### Added

- Add MVP golden path E2E test suite and install script integration tests (125+ test cases total).
- Add `mesh snapshot` CLI commands (create/restore/list/delete) with Rich-formatted output.
- Add container volume snapshot engine with tar-based create/restore/list/delete operations and local filesystem storage backend.
- Add interactive mesh-install.sh for 2-VM cluster bootstrap (server + client) via Tailscale mesh networking.
- Add shared type definitions module with SnapshotMetadata, NodeRole, SnapshotStatus enums, and snapshot/Nomad constants.

### Changed

- Strip broken Traefik automation and INGRESS/PRODUCTION tiers. Simplify tier system to LITE/STANDARD only.

### Fixed

- Fix NOMAD_ADDR discovery with config file fallback chain (env var, ~/.mesh/config, default). Remove silent demo fallbacks from MVP commands.


## [0.3.0] - 2026-04-17

First public open-source release.

### Added

- **CLI commands**: `init`, `deploy`, `status`, `logs`, `ssh`, `destroy`,
  `compare`, `version`, and `roadmap` — all backed by a Typer-based
  application with Rich-formatted terminal output (panels, tables, trees,
  progress bars).
- **Demo mode** (`--demo`) on every command for testing without real
  infrastructure.
- **Multi-cloud provisioning** across 50+ providers via Apache Libcloud,
  with first-class adapters for AWS, Hetzner, DigitalOcean, and local
  Multipass clusters.
- **Progressive activation / tier detection** — automatically configures
  the cluster for LITE (1 VM, Caddy HTTPS), STANDARD (multi-node),
  INGRESS (Traefik), or PRODUCTION (multi-region, full stack) based on
  topology.
- **Caddy lightweight ingress** for single-VM (lite) clusters with
  automatic HTTPS via Let's Encrypt or self-signed certs.
- **Traefik TLS ingress** for multi-node clusters with dynamic Consul
  routing and Let's Encrypt certificate management.
- **Nomad-based container scheduling** with resource-aware bin-packing
  across cluster nodes.
- **Consul service discovery** with health-checked DNS for all deployed
  workloads.
- **Tailscale WireGuard mesh networking** — encrypted overlay network
  connecting all cluster nodes across providers with zero manual
  configuration.
- **Modular boot scripts** rendered with Jinja2 templates to install
  Docker, Nomad, Consul, and Tailscale on provisioned VMs.
- **Plugin architecture** via Python `entry_points` (`mesh.plugins`)
  allowing third-party and enterprise extensions to register new CLI
  commands without modifying core.
- **Deployment templates**: `deploy_web_service`, `deploy_lite_web_service`,
  `deploy_lite_ingress`, and `deploy_traefik` — tier-aware unified
  deployment API.
- **Secret management** via `manage_secrets` — syncs GitHub Secrets to
  Nomad Variables with zero additional infrastructure.
- **E2E test suites** for app deployment, lite mode validation, and
  multi-node fault-tolerance scenarios.
- **Local development cluster** via Multipass — spin up a full cluster
  on your laptop in under 5 minutes.
- **Resource comparison** (`mesh compare`) showing Mesh vs Kubernetes
  cost and overhead benchmarks.
- **Vision roadmap** (`mesh roadmap`) displaying the platform capability
  timeline.

### Changed

- Package layout is now `src/mesh/…` (src-layout). Python imports are
  `from mesh.*` in both library code and consumers.

[Unreleased]: https://github.com/rethink-paradigms/mesh/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/rethink-paradigms/mesh/releases/tag/v0.3.0
