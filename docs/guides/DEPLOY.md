# Deployment & CLI Guide

**Last Updated:** 2026-04-17
**Status:** Beta (v0.3.0) (Pulumi/CLI) | Implemented (`mesh` CLI)

---

## Part 1: Current Deployment Methods

### Lite Mode (Single VM)

For solo projects and minimal budgets (~$8/month), deploy everything on a single VM with Caddy ingress.

```bash
cd src/mesh/infrastructure/provision_cloud_cluster
pulumi stack init lite-cluster

pulumi config set provider aws
pulumi config set region us-east-1
pulumi config set leader_size t3.micro
pulumi config set worker_node_count 0

pulumi up
```

This automatically triggers **lite mode** (0 workers). Caddy deploys as a Nomad system job with automatic HTTPS via Let's Encrypt. No Consul or Traefik required.

You can also explicitly set the tier:

```bash
pulumi config set cluster_tier lite
```

Deploy an app in lite mode using Nomad CLI directly:

```bash
nomad job run src/mesh/workloads/deploy_web_service/web_service.nomad.hcl \
  -var="app_name=myapp" \
  -var="image=nginx:latest" \
  -var="port=80" \
  -var="host_rule=myapp.localhost"
```

### Cloud Deployment (Pulumi)

The platform supports 13+ cloud providers through Apache Libcloud.

#### Quickstart: DigitalOcean

```bash
cd src/mesh/infrastructure/provision_cloud_cluster
pulumi stack init do-cluster

pulumi config set provider digitalocean
pulumi config set region nyc3
pulumi config set leader_size s-2vcpu-4gb
pulumi config set worker_size s-1vcpu-1gb

pulumi config set --secret tailscale:apiKey sk_your_tailscale_key
pulumi config set --secret digitalocean:token dop_v1_your_do_token

pulumi up
```

#### Quickstart: AWS

```bash
cd src/mesh/infrastructure/provision_cloud_cluster
pulumi stack init aws-cluster

pulumi config set provider aws
pulumi config set region us-east-1
pulumi config set leader_size t3.small
pulumi config set worker_size t3.micro

pulumi config set --secret tailscale:apiKey sk_your_tailscale_key
pulumi config set --secret aws:accessKey AKIA...
pulumi config set --secret aws:secretKey your_secret_key

pulumi up
```

#### Quickstart: Google Cloud

```bash
pulumi config set provider gcp
pulumi config set region us-central1
pulumi config set leader_size n1-standard-2
pulumi config set worker_size n1-standard-1
pulumi config set --secret gcp:credentials '{"type": "service_account", ...}'
```

#### Quickstart: Azure

```bash
pulumi config set provider azure
pulumi config set region eastus
pulumi config set leader_size Standard_B2s
pulumi config set worker_size Standard_B1s
pulumi config set --secret azure:clientId your_client_id
pulumi config set --secret azure:clientSecret your_client_secret
```

### Supported Providers

| Provider | Config Value | Credential Environment Variables |
|----------|--------------|----------------------------------|
| **AWS** | `aws` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| **DigitalOcean** | `digitalocean` | `DIGITALOCEAN_API_TOKEN` |
| **Google Cloud** | `gcp` | `GOOGLE_CREDENTIALS` |
| **Azure** | `azure` | `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` |
| **Linode** | `linode` | `LINODE_API_KEY` |
| **Vultr** | `vultr` | `VULTR_API_KEY` |
| **UpCloud** | `upcloud` | `UPCLOUD_USERNAME`, `UPCLOUD_PASSWORD` |
| **Scaleway** | `scaleway` | `SCALEWAY_ACCESS_KEY`, `SCALEWAY_SECRET_KEY` |
| **Exoscale** | `exoscale` | `EXOSCALE_API_KEY` |
| **OVHcloud** | `ovh` | `OVH_ENDPOINT`, `OVH_APPLICATION_KEY`, `OVH_APPLICATION_SECRET`, `OVH_CONSUMER_KEY` |
| **Equinix Metal** | `equinixmetal` | `EQUINIXMETAL_API_KEY`, `EQUINIXMETAL_PROJECT_ID` |

Full list: https://libcloud.readthedocs.io/en/stable/compute/supported_providers.html

### Configuration Reference

**Required:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `provider` | Cloud provider | `aws` |
| `region` | Provider region | `us-east-1` |
| `leader_size` | Leader node size | `t3.small` |
| `worker_size` | Worker node size | `t3.micro` |

**Optional:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `leader_node_count` | Number of leader nodes | `1` |
| `worker_node_count` | Number of worker nodes | `1` |
| `cluster_tier` | Cluster tier: `lite`, `standard`, `ingress`, `production` | Auto-detected from node count |

### Size Reference

**DigitalOcean:**

| Size Slug | CPU | RAM | Price/month |
|-----------|-----|-----|-------------|
| `s-1vcpu-1gb` | 1 | 1 GB | $6 |
| `s-2vcpu-2gb` | 2 | 2 GB | $12 |
| `s-2vcpu-4gb` | 2 | 4 GB | $24 |
| `s-4vcpu-8gb` | 4 | 8 GB | $48 |

**AWS:**

| Instance Type | CPU | RAM | Price/month |
|---------------|-----|-----|-------------|
| `t3.nano` | 2 | 0.5 GB | $4 |
| `t3.micro` | 1 | 1 GB | $8 |
| `t3.small` | 2 | 2 GB | $15 |
| `t3.medium` | 2 | 4 GB | $30 |

### Local Development (Multipass)

```bash
# Start local cluster
cd src/mesh/infrastructure/provision_local_cluster
python3 cli.py up

# Check status
python3 cli.py status

# Destroy
python3 cli.py down
```

**Requirements:** Multipass (macOS), 3GB free RAM, Tailscale auth key in `.env`.

---

## Part 2: Deploying Applications

### Deploy a Web Service

```bash
nomad job run src/mesh/workloads/deploy_web_service/web_service.nomad.hcl \
  -var="app_name=myapp" \
  -var="image=nginx" \
  -var="image_tag=latest" \
  -var="port=80" \
  -var="host_rule=myapp.localhost" \
  -var="domain=example.com" \
  -var="count=1"
```

### Deploy Traefik (TLS/HTTPS)

```python
from mesh.workloads.deploy_traefik import deploy_traefik

deploy_traefik(
    acme_email="admin@example.com",
    acme_ca_server="letsencrypt-production"  # or "letsencrypt-staging"
)
```



## Part 3: `mesh` CLI

The `mesh` CLI is fully implemented and provides interactive cluster provisioning, deployment, and management. Install the package and run `mesh init` to get started.

### Available Commands

| Command | Purpose | Interactive? |
|---------|---------|-------------|
| `mesh init` | Interactive cluster creation | Yes |
| `mesh status` | Cluster health monitoring | No |
| `mesh logs` | Tail service logs | No |
| `mesh ssh` | SSH into cluster nodes | No |
| `mesh destroy` | Cluster teardown | Yes (confirmation) |
| `mesh compare` | Mesh vs Kubernetes resource comparison | No |
| `mesh roadmap` | Show capability roadmap | No |
| `mesh version` | Show CLI version | No |

### Onboarding Flow (`mesh init`)

1. **Prerequisites validation** — Check Python, Docker, Pulumi installed
2. **Provider selection** — Interactive menu with 13+ cloud providers
3. **Credential collection** — Validate API tokens, open browser to console
4. **Region selection** — Test latency to each region
5. **Size selection** — Show pricing alongside sizes
6. **Worker count** — How many workers
7. **Tailscale configuration** — Auth key validation
8. **Cluster name** — Name your cluster
9. **Confirmation** — Summary with estimated monthly cost
10. **Provisioning** — Progress bar through all steps
11. **Success** — Show IPs, UIs, next steps

### Quick Start

```bash
# Install mesh
pip install -e ".[dev]"

# Initialize a cluster
mesh init

# Check status
mesh status

# View logs
mesh logs my-app --follow

# SSH into a node
mesh ssh mesh-leader

# Tear down
mesh destroy
```

### Architecture

```
src/mesh/cli/
├── main.py                    # Typer app, command registration, plugin discovery
├── plugins.py                 # Plugin discovery via entry_points
├── commands/
│   ├── init_cmd.py            # mesh init — interactive provisioning wizard
│   ├── status.py              # mesh status — cluster health display
│   ├── logs.py                # mesh logs — stream/view Nomad job logs
│   ├── ssh.py                 # mesh ssh — SSH into cluster nodes
│   ├── destroy.py             # mesh destroy — cluster teardown
│   └── helpers.py             # Shared CLI helpers (get_nomad_addr, etc.)
└── ui/
    ├── panels.py              # Rich UI components (banners, panels, progress)
    └── themes.py              # Color constants and status icons
```

### Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| **typer** | CLI argument parsing | Installed |
| **questionary** | Interactive prompts | Installed |
| **rich** | Progress bars, colored output | Installed |
| **pulumi-automation** | Programmatic pulumi up | Installed |

### Roadmap Commands

The following commands are planned for future releases:

| Command | Purpose | Status |
|---------|---------|--------|
| `mesh scale` | Add/remove nodes dynamically | Planned |
| `mesh doctor` | Health diagnostics and troubleshooting | Planned |
| `mesh check` | Prerequisites and dependency check | Planned |

### Performance Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Time to first deploy | <15 min | <15 min |
| Onboarding success rate | >90% | >95% |
| Documentation reads before deploy | <500 words | <200 words |

---

### Enterprise / Planned Features

The following features are available in `mesh-enterprise` or planned for future releases:

<details>
<summary>Monitoring (Enterprise/Planned)</summary>

```python
from mesh.workloads.deploy_monitoring import deploy_monitoring_job

deploy_monitoring_job(
    output_type="datadog",  # or "influxdb", "prometheus"
    api_key="your-datadog-key",
    site="us"
)
```

</details>

<details>
<summary>GPU Workloads (Enterprise/Planned)</summary>

```bash
nomad job run src/mesh/workloads/deploy_gpu_service/gpu_service.nomad.hcl \
  -var="app_name=pytorch-training" \
  -var="image=pytorch/pytorch:2.1.0-cuda12.1-runtime" \
  -var="gpu_count=1" \
  -var="memory=16384"
```

</details>

---

*Deployment guide reflects v0.3 capabilities with the implemented `mesh` CLI.*
