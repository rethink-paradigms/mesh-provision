# FAQ & Troubleshooting

Common questions and solutions for Mesh users.

---

## General

### What is Mesh?

Mesh is a lightweight infrastructure orchestration platform that turns any collection of VMs — across AWS, DigitalOcean, Google Cloud, and 13+ cloud providers — into a single unified deployment target. It uses Pulumi for provisioning, Tailscale for mesh networking, Nomad for scheduling, and Consul for service discovery.

### How is Mesh different from Kubernetes?

Mesh uses Nomad instead of Kubernetes for container scheduling. This means 90% less control plane overhead (530MB vs 2GB+) and a much simpler setup. Mesh is opinionated — it handles the common case (deploy containers, get HTTPS, scale out) with minimal configuration. See [Comparisons](comparisons.md) for details.

### What providers are supported?

13+ cloud providers via Apache Libcloud, including AWS, DigitalOcean, Google Cloud, Azure, Linode, Vultr, UpCloud, Exoscale, Scaleway, OVHcloud, Equinix Metal, Gridscale, CloudScale. For local development, Multipass is supported.

Full list: [libcloud.readthedocs.io](https://libcloud.readthedocs.io/en/stable/compute/supported_providers.html)

### How much does it cost?

| Tier | Nodes | RAM overhead | Approximate cost |
|:---|:---|:---|:---|
| Lite | 1 VM | ~200MB | ~$8/mo |
| Standard | 2+ VMs | ~350MB | ~$15/mo |
| Ingress | 2+ VMs | ~530MB | ~$25/mo | Manual Traefik Setup Required |
| Production | 3+ VMs, multi-region | ~530MB+ | ~$50+/mo | Manual Traefik Setup Required |

Pricing depends on your cloud provider and instance sizes.

---

## Installation

### `pip install rethink-mesh` fails

**Problem:** Installation errors, usually related to Python version or build dependencies.

**Solution:**

1. Ensure Python 3.11 or later: `python --version`
2. Upgrade pip: `pip install --upgrade pip`
3. On macOS, you may need: `xcode-select --install`
4. If Pulumi installation fails, install it separately: `brew install pulumi`

### Typer / Click version conflict

**Problem:** Error about `typer` or `click` versions.

**Solution:** This is a known minor conflict with the `together` package. It's non-blocking. If you see import errors:

```bash
pip install "click>=8.0.0" "typer>=0.9.0"
```

---

## Cluster Setup

### `mesh init` can't find provider credentials

**Problem:** CLI shows "Missing credentials" or "API key not found".

**Solution:**

> **Workspace:** Secrets are managed in Infisical. Run commands via `infisical run -- python -m mesh ...` from workspace root. See [`SERVICES.md`](../../SERVICES.md).

For standalone/public use, set environment variables in your shell or a local `.env` file:

=== "AWS"
    ```bash
    export AWS_ACCESS_KEY_ID=AKIA...
    export AWS_SECRET_ACCESS_KEY=...
    ```

=== "DigitalOcean"
    ```bash
    export DIGITALOCEAN_API_TOKEN=dop_v1_...
    ```

=== "Google Cloud"
    ```bash
    export GOOGLE_CREDENTIALS='{"type": "service_account", ...}'
    ```

=== "Azure"
    ```bash
    export AZURE_CLIENT_ID=...
    export AZURE_CLIENT_SECRET=...
    export AZURE_SUBSCRIPTION_ID=...
    export AZURE_TENANT_ID=...
    ```

See [`SECRETS-PROTOCOL.md`](../../SECRETS-PROTOCOL.md) for the workspace secret management protocol and canonical env var names.

### Multipass VMs won't start

**Problem:** `mesh init --provider "Local (Multipass)"` fails to create VMs.

**Solution:**

1. Ensure Multipass is installed: `multipass version`
2. Check available resources: you need **3GB+ free RAM**
3. On macOS, check if Docker Desktop is consuming all resources
4. Reset Multipass if needed: `multipass delete --all && multipass purge`
5. On Apple Silicon, ensure you're using the latest Multipass version

### Tailscale auth key is rejected

**Problem:** "Invalid auth key" or "key expired" during provisioning.

**Solution:**

1. Generate a new key at [tailscale.com/admin/authkeys](https://login.tailscale.com/admin/authkeys)
2. Ensure the key is **reusable** and **ephemeral** (Mesh creates these by default via API)
3. If using a manually created key, check it hasn't expired
4. Verify your Tailscale account hasn't reached its device limit (free tier: 3 devices)

### How do I upgrade Mesh?

```bash
pip install --upgrade mesh
```

Mesh uses rolling updates when possible. For major version upgrades, check the [CHANGELOG](https://github.com/rethink-paradigms/mesh/blob/main/CHANGELOG.md) for breaking changes. Cluster workloads continue running during upgrades — only the CLI is updated.

### How do I add/remove nodes from a running cluster?

To add a node:

```bash
mesh init --add-worker --provider aws --region us-east-1
```

To remove a node:

```bash
mesh destroy --node worker-1
```

Nomad automatically reschedules workloads from the removed node to healthy nodes before decommissioning.

### What happens when a node fails?

Nomad detects node failures via health checks and automatically reschedules affected containers to healthy nodes. For Production tier clusters with spot instances, the spot handler gracefully drains workloads before instance termination. Consul updates service discovery within seconds.

### Can I run databases on Mesh?

Yes, but with caveats. Nomad supports persistent volumes via host volumes. For stateful workloads:

1. Use node affinity to pin the database to a specific node
2. Configure host volumes in the Nomad job specification for data persistence
3. Consider managed database services (RDS, Cloud SQL) for production workloads that need automated backups and replication

For development, PostgreSQL and MySQL run fine as Nomad jobs with persistent storage.

### Provisioning times out

**Problem:** `mesh init` hangs during provisioning.

**Solution:**

1. Boot scripts typically take 2-4 minutes. If it's been >5 min, something is wrong
2. Check your cloud provider's status page
3. Verify your API key has the right permissions
4. Try a different region — some regions are slower to provision
5. Check the Tailscale coordination server isn't down: [status.tailscale.com](https://status.tailscale.com)

---

## Deployment

### App shows "pending" status

**Problem:** `mesh deploy` succeeds but the app stays in "pending" state.

**Solution:**

1. Check Nomad allocation status — the app may not have enough resources
2. Increase CPU/memory: `mesh deploy myapp --image nginx --cpu 200 --memory 512`
3. Ensure the Docker image exists and is accessible from the cluster nodes
4. Check node health: `mesh status` — if a worker is down, Nomad can't schedule

### HTTPS / TLS certificate not provisioning

**Problem:** Domain is accessible via HTTP but not HTTPS.

**Solution:**

1. Ensure your domain's DNS points to the leader node's public IP
2. Let's Encrypt requires port 80 and/or 443 to be accessible from the internet
3. Check if your cloud provider's firewall allows inbound traffic on 80/443
4. For staging/testing, use the Let's Encrypt staging server to avoid rate limits
5. Certificate provisioning can take 1-2 minutes after DNS propagation

### Can't access app from external traffic

**Problem:** App is running but not accessible from the internet.

**Solution:**

1. Verify the app deployed successfully: `mesh status`
2. Check the domain is configured: `mesh deploy myapp --domain myapp.example.com`
3. Ensure DNS is pointing to the correct IP
4. Check firewall rules on the cloud provider
5. In Lite mode, Caddy must be running on port 80/443

---

## Networking

### Nodes can't communicate

**Problem:** Workers can't reach the leader or other nodes.

**Solution:**

1. Verify Tailscale is running on all nodes: check `tailscale status`
2. Ensure all nodes show as "connected" in the Tailscale admin console
3. Check the Tailscale auth key was valid and nodes joined the same tailnet
4. Verify no firewall is blocking WireGuard (UDP 41641)

### Cross-cloud connectivity issues

**Problem:** AWS and DigitalOcean nodes can't reach each other.

**Solution:**

1. Tailscale handles NAT traversal automatically, but some restrictive firewalls may block it
2. Ensure outbound UDP traffic is allowed on all nodes
3. Check Tailscale DERP relay status: `tailscale netcheck`
4. If DERP relays are unreachable, Tailscale will fall back to direct connections where possible

---

## Performance

### High memory usage on leader node

**Problem:** Leader node is using more RAM than expected.

**Solution:**

1. Control plane overhead should be ~530MB (full mode) or ~200MB (lite mode)
2. Check if Traefik is consuming too much RAM (default 256MB limit)
3. Reduce Traefik memory in the deployment config if needed
4. For Lite mode, ensure you're using Caddy (20MB) not Traefik (256MB)

### App deployment is slow

**Problem:** `mesh deploy` takes a long time.

**Solution:**

1. First deployment pulls the Docker image — subsequent deploys are faster
2. Use smaller images (Alpine-based, distroless)
3. Pre-pull images on worker nodes if you deploy frequently
4. Check network bandwidth between the cluster and Docker Hub

---

## Uninstalling

### How do I destroy a cluster?

```bash
mesh destroy
```

This tears down all VMs, releases cloud resources, and removes the Tailscale mesh. **Cannot be undone.**

### How do I uninstall Mesh?

```bash
pip uninstall mesh
```

This removes the CLI. Any running clusters continue to exist on your cloud provider — run `mesh destroy` first to clean up resources.

---

## Still having issues?

- [Open a GitHub issue](https://github.com/rethink-paradigms/mesh/issues) with your error output
- Check [existing issues](https://github.com/rethink-paradigms/mesh/issues?q=is%3Aissue) for similar problems
- Report security vulnerabilities via [GitHub private reporting](https://github.com/rethink-paradigms/mesh/security/advisories/new)
