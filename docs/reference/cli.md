# CLI Commands Reference

Complete reference for all `mesh` CLI commands.

> **⚠️ Production Warning:** In production, mesh-provision is ONLY invoked by
> agent-bodies as a subprocess via the stdin JSON protocol. Direct CLI use
> bypasses Auth0 auth, database tracking, and audit logging. See
> [`MANIFEST.yaml`](../../MANIFEST.yaml) and
> [`contracts/mesh-provision.interface.md`](../../../contracts/mesh-provision.interface.md).
>
> **Workspace:** Use `infisical run -- python -m mesh ...` from workspace root.
> See [`SERVICES.md`](../../SERVICES.md).

---

## `mesh init`

Interactive cluster provisioning wizard. Creates a new Mesh cluster on any supported provider.

Supports stdin JSON protocol for automated provisioning. The `daemon_config` parameter (passed via stdin JSON, not CLI flag) injects Mesh daemon configuration via cloud-init `write_files` + `runcmd` during VM bootstrap.

```bash
mesh init [OPTIONS]
```

**Options:**

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `--provider` / `-p` | string | interactive | Cloud provider name (e.g., `"DigitalOcean"`, `"AWS"`, `"Local (Multipass)"`) |
| `--workers` / `-w` | int | `1` | Number of worker nodes |
| `--input` | string | — | Read provisioning config from stdin (JSON protocol v1) |
| `--output` | string | — | Output format: `json` for structured results |
| `--demo` | flag | false | Run in demo mode (no real infrastructure) |

**Stdin JSON protocol parameters:**

| Parameter | Type | Description |
|:---|:---|:---|
| `cluster_name` | string | Unique cluster identifier |
| `provider` | string | Cloud provider name |
| `region` | string | Provider region |
| `workers` | int | Number of worker nodes |
| `daemon_config` | object | Mesh daemon configuration injected via cloud-init. Includes API URL, JWT public key, cluster ID, etc. |

**Examples:**

```bash
# Interactive wizard (recommended for first use)
mesh init

# Skip wizard, provision directly
mesh init --provider "DigitalOcean" --workers 2

# Local development cluster
mesh init --provider "Local (Multipass)" --workers 2

# Demo mode (try without credentials)
mesh init --demo
```

---

## `mesh deploy`

Deploy a containerized application to the cluster.

```bash
mesh deploy <name> [OPTIONS]
```

**Arguments:**

| Arg | Required | Description |
|:---|:---|:---|
| `name` | Yes | Application name (used for routing and identification) |

**Options:**

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `--image` / `-i` | string | required | Docker image (e.g., `nginx`, `node:20`) |
| `--tag` / `-t` | string | `latest` | Image tag |
| `--port` / `-p` | int | `8080` | Container port to expose |
| `--domain` / `-d` | string | auto | Custom domain for HTTPS ingress |
| `--cpu` / `-c` | int | `100` | CPU allocation (MHz) |
| `--memory` / `-m` | int | `128` | Memory allocation (MB) |
| `--count` / `-n` | int | `1` | Number of instances |
| `--datacenter` | string | `dc1` | Nomad datacenter |
| `--tier` | string | auto | Force cluster tier |
| `--demo` | flag | false | Run in demo mode |

**Examples:**

```bash
# Deploy nginx
mesh deploy my-api --image nginx:latest --port 8080

# Deploy with custom domain and resources
mesh deploy web-app --image node:20 --port 3000 --domain app.example.com --cpu 200 --memory 512

# Deploy multiple instances
mesh deploy worker --image python:3.11 --count 3
```

---

## `mesh status`

View cluster health, nodes, and running applications. Can query existing VMs by cluster_name via the stdin JSON protocol.

```bash
mesh status [OPTIONS]
```

**Options:**

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `--input` | string | — | Read query from stdin (JSON protocol v1). Includes `cluster_name` to look up existing VMs. |
| `--output` | string | — | Output format: `json` for structured results |
| `--demo` | flag | false | Show demo output |
| `--compare` | flag | false | Show K8s comparison |
| `--roadmap` | flag | false | Show capability roadmap |

**Stdin JSON protocol (status):**

```json
{"action": "status", "cluster_name": "my-cluster"}
```

**Output includes:**

- Cluster name and detected tier
- Node list with IP addresses and health status
- Running deployments with resource usage
- Consul service health (if applicable)

---

## `mesh logs`

Stream application logs from a deployed service.

```bash
mesh logs [job_name] [OPTIONS]
```

**Arguments:**

| Arg | Required | Description |
|:---|:---|:---|
| `job_name` | No | Job name to fetch logs for. When omitted, lists all running jobs. |

**Options:**

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `--follow` / `-f` | flag | false | Stream logs continuously (like `tail -f`) |
| `--tail` / `-n` | int | `20` | Number of recent lines to show |
| `--alloc` / `-a` | string | none | Specific allocation ID |
| `--stderr` | flag | false | Show stderr instead of stdout |

---

## `mesh ssh`

Connect to a cluster node via SSH (through the Tailscale mesh).

```bash
mesh ssh [node_name] [OPTIONS]
```

**Arguments:**

| Arg | Required | Description |
|:---|:---|:---|
| `node_name` | No | Node name to connect to. When omitted, lists all available nodes. |

**Options:**

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `--user` / `-u` | string | `ubuntu` | SSH user |

---

## `mesh destroy`

Tear down a Mesh cluster and release all cloud resources.

```bash
mesh destroy [OPTIONS]
```

**Options:**

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `--cluster` / `-c` | string | `mesh-cluster` | Cluster name |
| `--cleanup-all` | flag | false | Remove compute + volumes + firewalls + floating IPs — full teardown |
| `--yes` / `-y` | flag | false | Skip confirmation prompt |
| `--demo` | flag | false | Run in demo mode |

!!! warning "Destructive"
    This permanently deletes all VMs, data, and deployed applications. Cannot be undone. Use `--cleanup-all` for complete resource removal including associated volumes, firewalls, and floating IPs.

---

## `mesh compare`

Show resource comparison between Mesh and Kubernetes.

```bash
mesh compare
```

Displays a side-by-side comparison of RAM usage, cost, and complexity.

---

## `mesh roadmap`

Show the capability roadmap and future vision.

```bash
mesh roadmap
```

Displays the platform feature timeline and upcoming capabilities.

---

## `mesh version`

Show the installed Mesh version.

```bash
mesh version
```

---

## Global Options

These flags work with all commands:

| Flag | Description |
|:---|:---|
| `--help` | Show command help and usage |
| `--demo` | Run without real infrastructure (for testing and evaluation) |

---

## Plugin Commands

Mesh supports extending the CLI via Python entry points. Enterprise and third-party plugins can add commands:

```toml
# In your plugin's pyproject.toml:
[project.entry-points."mesh.plugins"]
my-command = "my_package.cli:register"
```

See [CONTRIBUTING.md](https://github.com/rethink-paradigms/mesh/blob/main/CONTRIBUTING.md) for plugin development details.
