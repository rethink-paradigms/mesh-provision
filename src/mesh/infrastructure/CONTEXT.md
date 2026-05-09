# Domain: Infrastructure Provisioning

**Description:**
Encapsulates all concerns related to creating, configuring, and managing the core infrastructure components (VMs, Networking, Operating Systems).

## 🧩 Public Interface

| Feature | Input | Output | Description |
|:---|:---|:---|:---|
| `UniversalCloudNode` | name, provider, region, size_id, boot_script, [credentials] | public_ip, private_ip, instance_id | Dynamic Resource provisioning nodes across 50+ providers via Apache Libcloud with runtime discovery |
| `ProvisionNode` | name, provider, role, size, tailscale_auth_key, leader_ip, boot_script | public_ip, private_ip, instance_id | Provisions generic compute node (VM or bare metal) on specified provider |
| `GenerateBootScripts` | tailscale_key, leader_ip, role, [cluster_tier] | boot_script_sh, boot_script_cloud_init_yaml | Renders modular Jinja2 boot scripts for node initialization |
| `ConfigureTailscale` | key_name, [ephemeral], [reusable], [tags] | auth_key | Generates Tailscale authentication keys for mesh network joining |
| `ProvisionCloudCluster` | (Pulumi config) | leader_public_ip, worker_public_ip | Composes infrastructure primitives to deploy cloud cluster |
| `ProgressiveActivation` | [nodes], [override_tier] | TierConfig | Detects cluster tier from node topology and returns configuration for enabled services |

## 📦 Dependencies

- **Pulumi (Python)** - Infrastructure as Code framework
- **Apache Libcloud** - Multi-cloud provider abstraction (50+ providers)
- **Tailscale API** - Authentication key generation
- **Jinja2** - Boot script template rendering with StrictUndefined mode
- **Multipass CLI** - Local VM provisioning for development
- **Caddy** - Optional lightweight HTTPS server (lite/standard tiers)

## 🏗 Features

### `providers/` - Multi-Cloud Provider Abstraction
**Purpose:** Enables infrastructure provisioning across 50+ cloud providers using Pulumi Dynamic Resources powered by Apache Libcloud.

**Key Features:**
- Runtime discovery: Query providers for available options in real-time
- Exact values: Use provider-specific size_id, region, image_id without abstractions
- No configuration files: All metadata comes directly from provider APIs
- Auto-updating: New instance types, regions, and images appear automatically

**Status:** Production Ready

### `provision_node/` - Core Abstraction Layer
**Purpose:** Provides a unified interface for provisioning compute nodes across different providers (AWS, DigitalOcean, Multipass, and 40+ more via Libcloud).

**Key Files:**
- `provision_node.py` - Main abstraction with provider dispatcher
- `multipass.py` - Multipass VM provider adapter
- `test_*.py` - Comprehensive unit tests

### `boot_consul_nomad/` - Modular Boot Scripts
**Purpose:** Generates modular Jinja2 templates for node initialization, with validation and fail-fast mechanisms.

**Scripts:**
1. `01-install-deps.sh` - Base dependencies (curl, wget, git)
2. `02-install-tailscale.sh` - Mesh networking installation
3. `03-install-hashicorp.sh` - Nomad/Consul binary installation
4. `06-configure-consul.sh` - Service discovery configuration
5. `07-configure-nomad.sh` - Scheduler configuration
6. `10-install-caddy.sh` - Caddy installation (optional, lite/standard tiers)

### `configure_tailscale/` - Network Authentication
**Purpose:** Manages Tailscale authentication key generation for mesh network onboarding.

### `provision_cloud_cluster/` - Cloud Orchestration
**Purpose:** Composes lower-level provisioning primitives to deploy the standard mesh topology on cloud providers.

### `provision_local_cluster/` - Local Development
**Purpose:** Orchestrates the creation and management of a local development cluster using Multipass VMs.

### `progressive_activation/` - Tier Detection and Configuration
**Purpose:** Detects cluster tier and provides tier-aware configuration.

**Tiers:**
- LITE (1 VM, Caddy)
- STANDARD (2+ VMs same region, Caddy+Consul+Tailscale)
- INGRESS (multi-region, Traefik)
- PRODUCTION (full stack)

## 🧪 Test Coverage

- **27 provider tests** in `providers/test_libcloud_dynamic_provider.py`
- **20 Pulumi unit tests** in `provision_node/test_provision_node.py`
- **50 boot script tests** in `boot_consul_nomad/test_*.py`

## 🔗 Dependencies on Other Domains

- **workloads/deploy_traefik** - Depends on leader node provisioned by `provision_node`

## 📝 Design Decisions

- **Modular Boot Scripts:** Each script has a single responsibility (ADR-012)
- **Provider Abstraction:** Single interface for multi-cloud support
- **Memory Constraints:** 1.5GB Leader / 300MB Worker overhead (ADR-006)
