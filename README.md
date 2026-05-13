# Mesh Provision

Infrastructure provisioner for the Mesh daemon.

[![PyPI Version](https://img.shields.io/pypi/v/rethink-mesh)](https://pypi.org/project/rethink-mesh/)
[![Python](https://img.shields.io/pypi/pyversions/rethink-mesh)](https://pypi.org/project/rethink-mesh/)
[![License](https://img.shields.io/pypi/l/rethink-mesh)](https://github.com/rethink-paradigms/mesh)

**Provision cloud VMs, bootstrap Nomad/Consul/Docker/Tailscale/Caddy infrastructure stack, and inject Mesh daemon configuration for agent body orchestration.**

Provision VMs across cloud providers, bootstrap a Nomad + Consul + Docker + Tailscale + Caddy stack, and get back cluster connection details. Thats the scope. The Mesh daemon (separate project) handles agent body scheduling, ingress routing, and the REST API.

---

## Quick Start

```bash
# Install
pip install rethink-mesh

# Initialize a cluster
mesh init

# Check status
mesh status

# View logs
mesh logs
```

**From install to running:** ~5 minutes

---

## What It Does

* **Provisions VMs** — Spins up cloud instances on DigitalOcean, Multipass (local dev), and other providers via Apache Libcloud
* **Bootstraps the stack** — Installs and configures Nomad + Consul + Docker + Tailscale + Caddy on each node
* **Deploys infrastructure workloads** — Caddy ingress as a Nomad system job for lite and standard tiers
* **Returns cluster facts** — Leader IP, worker IPs, Tailscale network info, and connection details (JSON output for automation)

---

## Installation

### Prerequisites

* **Python 3.11 or later**
* **Docker** (for local development, optional for cloud deployments)
* **Cloud account** — DigitalOcean, AWS, Linode, or any supported provider
* **Tailscale account** — Free tier sufficient for mesh networking

### Install

```bash
pip install rethink-mesh
```

### Verify Installation

```bash
mesh doctor
```

---

## Configuration

Mesh reads configuration from environment variables. Copy the example file and add your credentials:

```bash
cp .env.example .env
```

### Required Variables

```bash
# Tailscale authentication key (required for all providers)
# Generate at: https://login.tailscale.com/admin/settings/keys
TAILSCALE_KEY=tskey-auth-example-yyyyy

# Choose one cloud provider:
# DigitalOcean
DIGITALOCEAN_API_TOKEN=do_token_xxxxx

# AWS
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJalr...
```

See `.env.example` for the full list of supported providers.

---

## CLI Commands

### mesh init

Provisions a new cluster interactively. Guides you through provider selection, region, instance sizing, and worker count.

```bash
mesh init

# Skip prompts with flags
mesh init --provider "Local (Multipass)" --workers 2
mesh init --provider "DigitalOcean" --region nyc3 --workers 1 --yes
```

Use `--output json` or `--input stdin` for automated or scripted provisioning. Use the daemon_config stdin parameter to inject the Mesh daemon configuration via cloud-init write_files + runcmd during VM bootstrap.

### mesh status

Shows cluster health, node topology, and running jobs.

```bash
mesh status
```

### mesh destroy

Tears down a cluster. Stops all jobs, terminates all nodes. Requires confirmation.

```bash
mesh destroy
mesh destroy --cluster my-cluster --yes
```

### mesh logs

Views or streams logs from Nomad jobs running on the cluster.

```bash
mesh logs                  # List all running jobs
mesh logs my-app           # Show logs for a specific job
mesh logs my-app --follow  # Stream logs in real-time
mesh logs my-app --tail 50 --stderr
```

### mesh ssh

SSH into cluster nodes. Without a node name, lists all available nodes. Tries Tailscale IPs when available.

```bash
mesh ssh
mesh ssh mesh-leader
mesh ssh mesh-worker-1 --user admin
```

### mesh doctor

Checks if your environment is ready. Verifies Python version, Docker, Pulumi, Tailscale, and environment variables.

```bash
mesh doctor
```

### mesh demo

Runs the full provisioning experience in demo mode without creating real infrastructure.

```bash
mesh demo
```

### mesh add-worker

Adds a worker node to an existing cluster.

```bash
mesh add-worker --cluster my-cluster --provider digitalocean
mesh add-worker --cluster my-cluster --provider digitalocean --region nyc3 --size s-1vcpu-1gb
```

---

## What It Does NOT Do

Mesh provisioner has a focused scope. It is NOT:

* **An application deployment platform** — The Mesh daemon handles workload scheduling. Mesh provisioner creates the cluster; the daemon runs agent bodies on it.
* **An agent runner** — Agent body lifecycle (start, stop, destroy) belongs to agent-bodies and the gateway.
* **A secrets manager** — No secrets storage, rotation, or access control.
* **A lightweight K8s alternative** — It is an infrastructure provisioner with a specific job: VMs + Nomad + Consul + Caddy. It does not attempt to replace container orchestration platforms.

---

## How It Works

```
mesh-provision / mesh CLI
  Provisions VMs, bootstraps Nomad+Consul,
  installs Docker+Tailscale, deploys Caddy
         |
         | Returns cluster facts (JSON)
         v
CLUSTER (Tailscale Mesh)
  Leader VM:  Nomad server, Consul, Docker,
              Caddy, Tailscale
  Worker VM:  Nomad client, Docker, Tailscale
```

**Architecture stack:**

1. **Apache Libcloud** provisions VMs across supported cloud providers
2. **Tailscale** creates an encrypted WireGuard mesh across all VMs
3. **Nomad** schedules infrastructure workloads with resource-aware bin-packing
4. **Consul** provides health-checked service discovery
5. **Caddy** handles HTTPS ingress with automatic Let's Encrypt

### Infrastructure vs Application Workloads

Mesh provisioner deploys infrastructure workloads only: Caddy ingress as a Nomad system job. Application workloads (agent bodies) are the Mesh daemon's responsibility. The provisioner creates the cluster and installs the foundation; the daemon uses it.

---

## Supported Providers

| Provider | Status | Notes |
|----------|--------|-------|
| DigitalOcean | Tested | Working, primary cloud provider |
| Multipass | Tested | Local development only |
| AWS | Mapped | Driver configured, not recently tested |
| Linode | Mapped | Driver configured, not tested |
| Vultr | Mapped | Driver configured, not tested |
| UpCloud | Mapped | Driver configured, not tested |
| Exoscale | Mapped | Driver configured, not tested |
| Scaleway | Mapped | Driver configured, not tested |
| OVH | Mapped | Driver configured, not tested |
| Equinix Metal | Mapped | Driver configured, not tested |

Providers are mapped via Apache Libcloud drivers. Additional providers can be added through the Libcloud provider registry.

---

## Development

### Running Tests

```bash
# Unit and integration tests (fast, no cluster required)
pytest src/mesh -m "not e2e"

# Full test suite (requires running cluster)
pytest src/mesh

# E2E tests only
RUN_E2E=1 ./run_tests.sh
```

### Project Structure

```
src/mesh/
├── cli/                    # CLI commands and UI
│   ├── commands/            # init, status, logs, ssh, destroy
│   └── ui/                 # Rich-formatted panels and themes
├── infrastructure/          # VM provisioning and networking
│   ├── provision_node/      # Multi-provider VM provisioning
│   ├── boot_consul_nomad/  # Modular boot scripts
│   ├── configure_tailscale/  # Tailscale auth key generation
│   └── providers/           # Libcloud provider implementations
├── workloads/               # Infrastructure workload deployment
│   └── deploy_lite_ingress/  # Caddy system job
└── verification/            # E2E test suites
```

Each directory contains a `CONTEXT.md` with interface contracts and design decisions.

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Quick start:**

```bash
# Clone and install
git clone https://github.com/rethink-paradigms/mesh.git
cd mesh
pip install -e ".[dev]"

# Run tests
pytest src/mesh -m "not e2e"
```

---

## Security

* WireGuard encryption on all mesh traffic via Tailscale
* TLS/HTTPS on all external endpoints via Let's Encrypt
* Docker container isolation with resource limits
* Declarative infrastructure -- SSH optional for cluster management

---

## License

MIT -- see [LICENSE](LICENSE) for details.

---

## Links

* [Documentation](https://github.com/rethink-paradigms/mesh/tree/main/docs)
* [Architecture Overview](https://github.com/rethink-paradigms/mesh/tree/main/docs)
