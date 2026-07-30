# 15-Minute Quickstart

Get a running Mesh cluster and deploy your first application in under 15 minutes.

> **Workspace:** If you're working in the Mesh workspace, use workspace-level commands.
> See [`SERVICES.md`](../../SERVICES.md) and [`services.json`](../../services.json).
> The instructions below are for public/standalone installation.

---

## Prerequisites

| Requirement | Install | Check |
|:---|:---|:---|
| Python 3.11+ | [python.org](https://python.org) | `python --version` |
| Tailscale account | [tailscale.com](https://tailscale.com) (free tier) | — |
| Cloud API key | Any supported provider | — |

For **local development** (no cloud account needed), also install [Multipass](https://multipass.run):

```bash
brew install --cask multipass     # macOS
snap install multipass            # Linux
```

---

## Option A: Cloud Cluster (Recommended)

### Step 1: Install Mesh

```bash
pip install rethink-mesh
```

### Step 2: Initialize your cluster

```bash
mesh init
```

The interactive wizard walks you through:

1. **Provider selection** — AWS, DigitalOcean, Google Cloud, Azure, and 9+ more
2. **Region selection** — Choose the closest or cheapest region
3. **Instance sizing** — See pricing alongside each option
4. **Worker count** — 0 workers for Lite mode, 1+ for multi-node
5. **Tailscale key** — Paste your auth key (get one at [tailscale.com/admin/authkeys](https://login.tailscale.com/admin/authkeys))
6. **Confirmation** — Review estimated monthly cost before proceeding

```
╭──────────────────────────────────────╮
│        Mesh Cluster Setup            │
│                                      │
│  Provider: DigitalOcean              │
│  Region:   nyc3                      │
│  Leader:   s-2vcpu-4gb ($24/mo)     │
│  Workers:  2x s-1vcpu-1gb ($6/mo)  │
│                                      │
│  Estimated total: ~$36/mo            │
╰──────────────────────────────────────╯

  Provisioning leader...    ━━━━━ 100%
  Provisioning worker-1...  ━━━━━ 100%
  Provisioning worker-2...  ━━━━━ 100%
  Bootstrapping Consul...   ━━━━━ 100%
  Bootstrapping Nomad...    ━━━━━ 100%
  Joining Tailscale mesh... ━━━━━ 100%

  ✓ Cluster ready in 3m 42s
```

### Step 3: Deploy your first app

```bash
mesh deploy hello --image nginx:latest --port 80
```

> **Note:** The default port is 8080. The `--port 80` above is an explicit override for HTTP traffic.

### Step 4: Check it's running

```bash
mesh status
```

```
╭──────────────────────────────────────╮
│       Cluster: mesh-prod             │
│       Tier:    Ingress               │
│       Nodes:   3 healthy             │
╰──────────────────────────────────────╯

  Deployments
  ┌────────────┬─────────┬─────────┬──────┐
  │ App        │ Image   │ Status  │ CPU  │
  ├────────────┼─────────┼─────────┼──────┤
  │ hello      │ nginx   │ running │ 2%   │
  └────────────┴─────────┴─────────┴──────┘
```

Done! Your app is running with automatic HTTPS via Let's Encrypt.

---

## Option B: Local Cluster (Free, $0)

### Step 1: Install prerequisites

```bash
brew install --cask multipass
```

### Step 2: Clone and configure

```bash
git clone https://github.com/rethink-paradigms/mesh.git
cd mesh
pip install -e ".[dev]"
```

Set environment variables in your shell or a local `.env` file:

```bash
export TAILSCALE_KEY=tskey-auth-xxxxx
# Also set your cloud provider token, e.g.:
# export DIGITALOCEAN_API_TOKEN=...
```

### Step 3: Launch

```bash
mesh init --provider "Local (Multipass)" --workers 2
```

### Step 4: Deploy

```bash
mesh deploy hello --image nginx:latest
mesh status
```

---

## Next Steps

- [Configure a custom domain](../guides/deploy.md) for your app
- [Add environment variables and secrets](../guides/deploy.md)
- [Understand deployment tiers](../architecture/overview.md#deployment-tiers) and when to scale
- [View the full CLI reference](../reference/cli.md)
- [Compare with alternatives](../comparisons.md)

---

## Common Issues

| Problem | Solution |
|:---|:---|
| `pip install rethink-mesh` fails | Ensure Python 3.11+: `python --version` |
| `mesh init` can't find provider credentials | Set env vars in your shell or a local `.env` file |
| Multipass VMs won't start | Ensure 3GB+ free RAM. On macOS: check Docker Desktop isn't consuming all resources |
| Tailscale key rejected | Generate a new key at [tailscale.com/admin/authkeys](https://login.tailscale.com/admin/authkeys). Keys expire |

More solutions in the [FAQ](../faq.md).
