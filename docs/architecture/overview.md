# Architecture Overview

Mesh combines four open-source tools into a unified platform that turns any collection of VMs into a single deployment target.

---

## High-Level Topology

```
                    ┌─────────────────────┐
                    │   EXTERNAL WORLD    │
                    │   Users / CI/CD     │
                    └──────────┬──────────┘
                               │ HTTP/HTTPS + Pulumi API
                    ┌──────────┴──────────┐
                    │   LEADER NODE (VM-1) │
                    │  Traefik or Caddy    │
                    │  Nomad + Consul      │
                    │  Tailscale + Docker  │
                    └──────────┬──────────┘
                               │
                 Tailscale WireGuard Mesh (100.x.y.z)
                    ┌──────────┴──────────┐
                    │                     │
           ┌────────┴────────┐  ┌─────────┴───────┐
            │  WORKER (VM-2)  │  │  WORKER (VM-N)  │
            │  AWS / DO / GCP  │  │  Azure / ... │
           │  App Containers │  │  App Containers │
           └─────────────────┘  └─────────────────┘
```

---

## How It Works — Step by Step

### 1. Provisioning (Pulumi + Libcloud)

When you run `mesh init`, the CLI:

1. Uses **Apache Libcloud** to provision VMs on your chosen provider (13+ supported)
2. Routes through `provision_node` which provides a unified interface for both local (Multipass) and cloud paths
3. Each node gets a modular **boot script** rendered from Jinja2 templates via `boot_consul_nomad`

The provisioning layer is provider-agnostic. The `UniversalCloudNode` Pulumi Dynamic Resource accepts `provider`, `region`, `size_id`, and `boot_script` — no provider-specific code in the orchestration layer.

### 2. Bootstrapping (~2 minutes)

Each VM runs a modular boot sequence:

| Phase | Script | Purpose |
|:---|:---|:---|
| 01 | `install-deps.sh` | Docker, curl, base packages |
| 02 | `install-tailscale.sh` | WireGuard mesh networking |
| 03 | `install-hashicorp.sh` | Nomad, Consul binaries |
| 06 | `configure-consul.sh` | Service discovery setup |
| 07 | `configure-nomad.sh` | Container scheduling setup |
| 10 | `install-caddy.sh` | (Lite mode only) HTTPS ingress |

Scripts are rendered via Jinja2 with `StrictUndefined` — missing variables fail loudly, never silently.

### 3. Mesh Networking (Tailscale)

All nodes join a **Tailscale WireGuard mesh** (100.x.y.z addresses). This provides:

- **Encrypted** point-to-point communication between all nodes
- **Zero-config** NAT traversal — no need to open firewall ports
- **Multi-cloud** by default — AWS, DigitalOcean, and GCP nodes talk directly

The `configure_tailscale` module generates ephemeral, tagged auth keys (`tag:mesh`) via the Tailscale API.

### 4. Container Scheduling (Nomad)

**Nomad** schedules Docker containers across the cluster using:

- **Resource-aware bin-packing** — maximizes utilization per node
- **Automatic rescheduling** — if a worker fails, Nomad moves its containers
- **Job specification** via HCL templates parameterized by the workloads domain

Applications are deployed via Nomad job files directly or through the `deploy_web_service` module for Traefik-routed deployments.

### 5. Service Discovery (Consul)

**Consul** provides health-checked DNS for all services:

- Automatic registration when containers start
- Health check integration with Nomad task states
- DNS-based service resolution (`myapp.service.consul`)
- WAN federation for multi-region Production tier (manual setup required)

### 6. HTTPS Ingress (Traefik / Caddy)

Mesh uses two ingress controllers depending on cluster tier:

| Controller | Tier | RAM | Features |
|:---|:---|:---|:---|
| **Caddy** | Lite, Standard | ~20MB | Automatic HTTPS, admin API, lightweight |
| **Traefik** | Ingress, Production | ~256MB | Consul catalog integration, dynamic routing |

Both provision Let's Encrypt certificates automatically. No manual cert management.

---

## Deployment Tiers

The `progressive_activation` module automatically detects cluster topology and activates the correct services:

| | **Lite** | **Standard** | **Ingress** | **Production** |
|:---|:---|:---|:---|:---|
| **Trigger** | 1 node | 2+ nodes, 1 region | multi-region | spot instances |
| **Nomad** | Yes | Yes | Yes | Yes |
| **Tailscale** | No | Yes | Yes | Yes |
| **Caddy** | Yes | Yes | No | No |
| **Consul** | No | Yes | Yes | Yes (WAN) |
| **Traefik** | No | No | Yes | Yes |
| **Telegraf** | No | No | No | Yes |
| **RAM overhead** | ~200MB | ~350MB | ~530MB | ~530MB+ |
| **Status** | Available | Available | Manual Traefik Setup Required | Manual Traefik Setup Required |
| **Monthly cost** | ~$8 | ~$15 | ~$25 | ~$50+ |

The `ClusterTier` enum and `detect_cluster_tier()` function handle this automatically. You can override with `--tier` or `cluster_tier` config.

---

## Data Flow: Deploying an App

```
User prepares a Nomad job file or uses deploy_web_service
                    │
                    ▼
            ┌───────────────┐
            │  deploy_web_  │  Creates Nomad HCL with
            │  service      │  Consul tags for Traefik
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  Nomad API    │  Submits job, schedules
            │  (leader:4646)│  containers to workers
            └───────────────┘
```

---

## Secrets Management

Mesh uses a **zero-infrastructure** secrets approach:

1. Store secrets in **GitHub Secrets** (or your CI/CD platform)
2. Use Nomad's `template` stanza to inject them into containers as environment variables
3. Alternatively, set secrets directly via the Nomad Variables API

No Vault, no etcd, no encrypted S3 buckets. The trust boundary is your CI/CD platform.

---

## Security Model

| Layer | Protection |
|:---|:---|
| **Transit** | WireGuard encryption (Tailscale) on all inter-node traffic |
| **External** | TLS/HTTPS on all public endpoints (Let's Encrypt) |
| **Isolation** | Docker container isolation with resource limits |
| **Access** | Zero SSH required for deployment — all configuration is declarative via Pulumi/Nomad |
| **Secrets** | Ephemeral — synced from CI/CD, stored in Nomad Variables |

---

## Component Reference

| Module | Purpose | Key Interface |
|:---|:---|:---|
| `provision_node` | Provision a VM on any provider | `provision_node(name, provider, role, size, ...)` |
| `providers` | Libcloud driver wrapper | `UniversalCloudNode` Pulumi Dynamic Resource |
| `boot_consul_nomad` | Render boot scripts | Jinja2 templates → shell/cloud-init |
| `configure_tailscale` | Generate auth keys | `key_name`, `ephemeral`, `tags` → `auth_key` |
| `progressive_activation` | Tier detection | `detect_cluster_tier(nodes)` → `TierConfig` |
| `deploy_web_service` | Traefik-routed deploy | Nomad HCL with Consul tags |
| `deploy_traefik` | Traefik ingress setup | ACME config, Consul integration |
| `deploy_lite_ingress` | Caddy ingress setup | `LiteIngressConfig`, `RouteManager` |
