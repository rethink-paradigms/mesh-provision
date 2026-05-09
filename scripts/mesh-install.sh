#!/usr/bin/env bash
# mesh-install.sh — Interactive install script for Mesh node setup
# Sets up a Mesh SERVER or CLIENT node on Ubuntu 22.04.
# Run inside the VM: bash mesh-install.sh --role server --tskey <key>
#
# Idempotent: safe to re-run. Each step checks if already installed.

set -euo pipefail

# ─── Constants ────────────────────────────────────────────────────────────────
readonly NOMAD_VERSION="1.9.3"
readonly CONSUL_VERSION="1.17.1"
readonly MESH_CONFIG_DIR="${HOME}/.mesh"
readonly MESH_CONFIG_FILE="${MESH_CONFIG_DIR}/config"
readonly SCRIPT_NAME="$(basename "$0")"

# ─── Defaults ─────────────────────────────────────────────────────────────────
ROLE=""
TS_KEY=""
SERVER_IP=""
CHECK_ONLY=false
DRY_RUN=false

# ─── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()    { echo -e "${GREEN}[mesh]${NC} $*"; }
warn()   { echo -e "${YELLOW}[warn]${NC} $*"; }
error()  { echo -e "${RED}[error]${NC} $*" >&2; }
info()   { echo -e "${CYAN}[info]${NC} $*"; }

# ─── Usage ────────────────────────────────────────────────────────────────────
usage() {
    cat <<'USAGE'
Usage: mesh-install.sh [OPTIONS]

Set up a Mesh node (server or client) on Ubuntu 22.04.

Required:
  --role ROLE           Node role: "server" or "client"
  --tskey KEY           Tailscale auth key (https://login.tailscale.com/admin/settings/keys)

Optional:
  --server-ip IP        IP of the leader/server node (required for client role)
  --check-only          Check prerequisites and exit (no installation)
  --dry-run             Show what would be done without executing
  --help                Show this help message

Server role installs:
  - System dependencies (curl, unzip, docker.io, jq)
  - Tailscale mesh networking
  - Nomad server (scheduler)
  - Consul server (service discovery)
  - Caddy (HTTPS ingress)
  - Systemd services for Nomad and Consul

Client role installs:
  - System dependencies (curl, unzip, docker.io, jq)
  - Tailscale mesh networking
  - Nomad client (workload runner)
  - Consul client (service discovery agent)
  - Systemd services for Nomad and Consul
  - Connects to server via --server-ip (no Caddy)

Examples:
  # Install a server node
  mesh-install.sh --role server --tskey tskey-auth-xxxxx

  # Install a client node
  mesh-install.sh --role client --tskey tskey-auth-xxxxx --server-ip 100.64.0.1

  # Check prerequisites only
  mesh-install.sh --role server --tskey tskey-auth-xxxxx --check-only

  # Dry run (show steps without executing)
  mesh-install.sh --role server --tskey tskey-auth-xxxxx --dry-run
USAGE
    exit 0
}

# ─── Argument Parsing ─────────────────────────────────────────────────────────
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --role)
                ROLE="${2:-}"
                if [[ -z "$ROLE" ]]; then
                    error "--role requires a value: server or client"
                    exit 1
                fi
                shift 2
                ;;
            --tskey)
                TS_KEY="${2:-}"
                if [[ -z "$TS_KEY" ]]; then
                    error "--tskey requires a Tailscale auth key"
                    exit 1
                fi
                shift 2
                ;;
            --server-ip)
                SERVER_IP="${2:-}"
                if [[ -z "$SERVER_IP" ]]; then
                    error "--server-ip requires an IP address"
                    exit 1
                fi
                shift 2
                ;;
            --check-only)
                CHECK_ONLY=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help|-h)
                usage
                ;;
            *)
                error "Unknown option: $1"
                error "Run '${SCRIPT_NAME} --help' for usage."
                exit 1
                ;;
        esac
    done
}

# ─── Validation ───────────────────────────────────────────────────────────────
validate_server_ip() {
    local ip="$1"
    if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        return 0
    fi
    if [[ "$ip" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$ ]]; then
        return 0
    fi
    error "Invalid --server-ip: '${ip}'. Must be a valid IP address or hostname."
    exit 1
}

validate_args() {
    if [[ -z "$ROLE" ]]; then
        error "--role is required (server or client)"
        exit 1
    fi

    if [[ "$ROLE" != "server" && "$ROLE" != "client" ]]; then
        error "Invalid role: '${ROLE}'. Must be 'server' or 'client'."
        exit 1
    fi

    if [[ -z "$TS_KEY" ]]; then
        error "--tskey is required. Generate one at https://login.tailscale.com/admin/settings/keys"
        exit 1
    fi

    if [[ "$ROLE" == "client" && -z "$SERVER_IP" ]]; then
        error "--server-ip is required when --role is 'client'"
        exit 1
    fi

    if [[ "$ROLE" == "client" && -n "$SERVER_IP" ]]; then
        validate_server_ip "$SERVER_IP"
    fi
}

# ─── Dry-run helper ───────────────────────────────────────────────────────────
run_cmd() {
    if [[ "$DRY_RUN" == "true" ]]; then
        info "[dry-run] $*"
    else
        "$@"
    fi
}

# ─── Prerequisite Checking ────────────────────────────────────────────────────
check_prerequisites() {
    local ok=true

    # Check root/sudo
    if [[ "$EUID" -ne 0 ]]; then
        error "This script must be run as root (use sudo)."
        ok=false
    fi

    # Check OS
    if [[ ! -f /etc/os-release ]]; then
        warn "Cannot detect OS (/etc/os-release missing)."
    else
        source /etc/os-release
        if [[ "$ID" != "ubuntu" ]] || [[ "$VERSION_ID" != "22.04"* ]]; then
            warn "Designed for Ubuntu 22.04. Detected: ${PRETTY_NAME:-unknown}."
        fi
    fi

    # Check architecture
    local arch
    arch=$(uname -m)
    if [[ "$arch" != "x86_64" && "$arch" != "aarch64" ]]; then
        error "Unsupported architecture: ${arch}. Only x86_64 and aarch64 are supported."
        ok=false
    fi

    # Check internet connectivity
    if ! run_cmd curl -sf --connect-timeout 5 https://tailscale.com > /dev/null 2>&1; then
        if [[ "$DRY_RUN" == "false" ]]; then
            warn "Cannot reach tailscale.com. Internet may be unavailable."
        fi
    fi

    if [[ "$ok" == "false" ]]; then
        return 1
    fi

    log "Prerequisites OK."
    return 0
}

# ─── Step 1: Install Dependencies ────────────────────────────────────────────
install_deps() {
    log "Installing system dependencies..."

    # Idempotency: check if all packages are already installed
    local pkgs_missing=false
    for pkg in curl unzip docker.io jq; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            pkgs_missing=true
            break
        fi
    done

    if [[ "$pkgs_missing" == "false" ]]; then
        log "Dependencies already installed, skipping."
        return 0
    fi

    run_cmd apt-get update -y
    run_cmd apt-get install -y curl unzip docker.io jq

    # Ensure docker is running
    if ! systemctl is-active --quiet docker 2>/dev/null; then
        run_cmd systemctl enable docker
        run_cmd systemctl start docker
    fi

    log "Dependencies installed."
}

# ─── Step 2: Install & Configure Tailscale ────────────────────────────────────
install_tailscale() {
    log "Installing Tailscale..."

    if command -v tailscale &>/dev/null; then
        log "Tailscale already installed ($(tailscale version 2>/dev/null | head -1 || echo 'unknown'))."
    else
        TMP=$(mktemp) && run_cmd curl -fsSL https://tailscale.com/install.sh -o "$TMP" && run_cmd bash "$TMP" && rm "$TMP"
        log "Tailscale installed."
    fi

    # Enable IP forwarding for Tailscale
    if [[ "$(sysctl -n net.ipv4.ip_forward 2>/dev/null || echo 0)" != "1" ]]; then
        run_cmd sysctl -w net.ipv4.ip_forward=1
    fi
    if [[ "$(sysctl -n net.ipv6.conf.all.forwarding 2>/dev/null || echo 0)" != "1" ]]; then
        run_cmd sysctl -w net.ipv6.conf.all.forwarding=1
    fi

    # Persist forwarding across reboots
    if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.d/99-tailscale.conf 2>/dev/null; then
        cat <<EOF | run_cmd tee /etc/sysctl.d/99-tailscale.conf
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
    fi

    # Bring Tailscale up if not already connected
    if ! tailscale status &>/dev/null; then
        local hostname
        hostname=$(cat /etc/hostname)
        run_cmd tailscale up --authkey="$TS_KEY" --hostname="node-${hostname}" --reset
        log "Tailscale connected."
    else
        log "Tailscale already connected."
    fi
}

# ─── Step 3: Install HashiCorp Binaries ───────────────────────────────────────
install_hashicorp() {
    log "Installing HashiCorp binaries (Nomad ${NOMAD_VERSION}, Consul ${CONSUL_VERSION})..."

    local arch c_arch
    arch=$(uname -m)
    if [[ "$arch" == "aarch64" ]]; then
        c_arch="arm64"
    else
        c_arch="amd64"
    fi

    # Consul
    if [[ -f "/usr/local/bin/consul" ]]; then
        log "Consul already installed ($(consul version 2>/dev/null | head -1 || echo 'unknown'))."
    else
        run_cmd curl -fO "https://releases.hashicorp.com/consul/${CONSUL_VERSION}/consul_${CONSUL_VERSION}_linux_${c_arch}.zip"
        run_cmd unzip -o "consul_${CONSUL_VERSION}_linux_${c_arch}.zip"
        run_cmd mv -f consul /usr/local/bin/
        run_cmd rm -f "consul_${CONSUL_VERSION}_linux_${c_arch}.zip"
        log "Consul ${CONSUL_VERSION} installed."
    fi

    # Nomad
    if [[ -f "/usr/local/bin/nomad" ]]; then
        log "Nomad already installed ($(nomad version 2>/dev/null | head -1 || echo 'unknown'))."
    else
        run_cmd curl -fO "https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_${c_arch}.zip"
        run_cmd unzip -o "nomad_${NOMAD_VERSION}_linux_${c_arch}.zip"
        run_cmd mv -f nomad /usr/local/bin/
        run_cmd rm -f "nomad_${NOMAD_VERSION}_linux_${c_arch}.zip"
        log "Nomad ${NOMAD_VERSION} installed."
    fi
}

# ─── Step 4: Configure Consul (Server) ───────────────────────────────────────
configure_consul_server() {
    log "Configuring Consul server..."

    run_cmd mkdir -p /etc/consul.d /opt/consul

    local ts_ip
    ts_ip=$(tailscale ip -4 2>/dev/null || echo "0.0.0.0")

    # Always write fresh config (idempotent overwrite)
    cat <<EOF | run_cmd tee /etc/consul.d/consul.hcl
datacenter = "dc1"
data_dir = "/opt/consul"
bind_addr = "${ts_ip}"
client_addr = "0.0.0.0"
retry_join = ["${ts_ip}"]
server = true
bootstrap_expect = 1
ui_config {
  enabled = true
}
EOF

    log "Consul server configured."
}

# ─── Step 5: Configure Nomad (Server) ────────────────────────────────────────
configure_nomad_server() {
    log "Configuring Nomad server..."

    run_cmd mkdir -p /etc/nomad.d /opt/nomad

    cat <<EOF | run_cmd tee /etc/nomad.d/nomad.hcl
datacenter = "dc1"
data_dir = "/opt/nomad"
bind_addr = "0.0.0.0"

client {
  enabled = true
  meta {
    role = "server"
  }
}

server {
  enabled = true
  bootstrap_expect = 1
}

ui {
  enabled = true
}
EOF

    log "Nomad server configured."
}

# ─── Step 6: Install Caddy ───────────────────────────────────────────────────
install_caddy() {
    log "Installing Caddy..."

    if command -v caddy &>/dev/null; then
        log "Caddy already installed ($(caddy version 2>/dev/null || echo 'unknown'))."
        return 0
    fi

    run_cmd apt-get update -qq
    run_cmd apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl
    run_cmd curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | run_cmd gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    run_cmd curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | run_cmd tee /etc/apt/sources.list.d/caddy-stable.list
    run_cmd apt-get update -qq
    run_cmd apt-get install -y -qq caddy

    run_cmd mkdir -p /opt/caddy/data

    # Add caddy-data host volume to Nomad config
    if ! grep -q "caddy-data" /etc/nomad.d/nomad.hcl 2>/dev/null; then
        cat <<EOF | run_cmd tee -a /etc/nomad.d/nomad.hcl

host_volume "caddy-data" {
  path = "/opt/caddy/data"
  read_only = false
}
EOF
    fi

    log "Caddy installed."
}

# ─── Step 4b: Configure Consul (Client) ───────────────────────────────────────
configure_consul_client() {
    log "Configuring Consul client (joining ${SERVER_IP})..."

    run_cmd mkdir -p /etc/consul.d /opt/consul

    local ts_ip
    ts_ip=$(tailscale ip -4 2>/dev/null || echo "0.0.0.0")

    cat <<EOF | run_cmd tee /etc/consul.d/consul.hcl
datacenter = "dc1"
data_dir = "/opt/consul"
bind_addr = "${ts_ip}"
client_addr = "0.0.0.0"
retry_join = ["${SERVER_IP}"]
server = false
EOF

    log "Consul client configured (joining server at ${SERVER_IP})."
}

# ─── Step 5b: Configure Nomad (Client) ────────────────────────────────────────
configure_nomad_client() {
    log "Configuring Nomad client (joining ${SERVER_IP})..."

    run_cmd mkdir -p /etc/nomad.d /opt/nomad

    cat <<EOF | run_cmd tee /etc/nomad.d/nomad.hcl
datacenter = "dc1"
data_dir = "/opt/nomad"
bind_addr = "0.0.0.0"

server {
  enabled = false
}

client {
  enabled = true
  server_join {
    retry_join = ["${SERVER_IP}:4647"]
  }
  meta {
    role = "client"
  }
}
EOF

    log "Nomad client configured (joining server at ${SERVER_IP}:4647)."
}

# ─── Step 7: Create Systemd Services ─────────────────────────────────────────
create_systemd_services() {
    log "Creating systemd services..."

    # Consul service
    cat <<EOF | run_cmd tee /etc/systemd/system/consul.service
[Unit]
Description=Consul Agent
Requires=network-online.target
After=network-online.target

[Service]
Restart=on-failure
ExecStart=/usr/local/bin/consul agent -config-dir=/etc/consul.d

[Install]
WantedBy=multi-user.target
EOF

    # Nomad service
    cat <<EOF | run_cmd tee /etc/systemd/system/nomad.service
[Unit]
Description=Nomad Agent
Requires=network-online.target
After=network-online.target

[Service]
Restart=on-failure
ExecStart=/usr/local/bin/nomad agent -config=/etc/nomad.d

[Install]
WantedBy=multi-user.target
EOF

    run_cmd systemctl daemon-reload
    run_cmd systemctl enable consul nomad
    run_cmd systemctl restart consul nomad

    log "Systemd services created and started."
}

# ─── Step 8: Write Config & Print Summary ────────────────────────────────────
write_config() {
    mkdir -p "$MESH_CONFIG_DIR"

    local ts_ip public_ip nomad_addr consul_addr
    ts_ip=$(tailscale ip -4 2>/dev/null || echo "unknown")
    public_ip=$(curl -sf ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "unknown")

    if [[ "$ROLE" == "client" ]]; then
        nomad_addr="http://${SERVER_IP}:4646"
        consul_addr="http://${SERVER_IP}:8500"
    else
        nomad_addr="http://${public_ip}:4646"
        consul_addr="http://${public_ip}:8500"
    fi

    cat <<EOF > "$MESH_CONFIG_FILE"
# Mesh node configuration — generated by mesh-install.sh
# Modify with caution. Re-run mesh-install.sh to update.
NOMAD_ADDR="${nomad_addr}"
CONSUL_ADDR="${consul_addr}"
TAILSCALE_IP="${ts_ip}"
PUBLIC_IP="${public_ip}"
ROLE="${ROLE}"
SERVER_IP="${SERVER_IP}"
EOF

    export NOMAD_ADDR="${nomad_addr}"

    log "Config written to ${MESH_CONFIG_FILE}"
}

print_summary() {
    local ts_ip public_ip
    ts_ip=$(tailscale ip -4 2>/dev/null || echo "unknown")
    public_ip=$(curl -sf ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "unknown")

    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo -e "${GREEN}  Mesh Server Node Installed Successfully${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "  Role:          ${ROLE}"
    echo "  Public IP:     ${public_ip}"
    echo "  Tailscale IP:  ${ts_ip}"
    echo ""
    echo "  Nomad UI:      http://${public_ip}:4646"
    echo "  Consul UI:     http://${public_ip}:8500"
    echo ""
    echo "  Config file:   ${MESH_CONFIG_FILE}"
    echo ""
    echo "  Environment:"
    echo "    export NOMAD_ADDR=\"http://${public_ip}:4646\""
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo ""
}

# ─── Server Install Flow ─────────────────────────────────────────────────────
install_server() {
    log "=== Installing Mesh SERVER node ==="

    install_deps
    install_tailscale
    install_hashicorp
    configure_consul_server
    configure_nomad_server
    install_caddy
    create_systemd_services
    write_config
    print_summary

    log "=== Server installation complete ==="
}

print_client_summary() {
    local ts_ip public_ip
    ts_ip=$(tailscale ip -4 2>/dev/null || echo "unknown")
    public_ip=$(curl -sf ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "unknown")

    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo -e "${GREEN}  Mesh Client Node Installed Successfully${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "  Role:          ${ROLE}"
    echo "  Server IP:     ${SERVER_IP}"
    echo "  Public IP:     ${public_ip}"
    echo "  Tailscale IP:  ${ts_ip}"
    echo ""
    echo "  Nomad Server:  http://${SERVER_IP}:4646"
    echo "  Consul Server: http://${SERVER_IP}:8500"
    echo ""
    echo "  Config file:   ${MESH_CONFIG_FILE}"
    echo ""
    echo "  Environment:"
    echo "    export NOMAD_ADDR=\"http://${SERVER_IP}:4646\""
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo ""
}

# ─── Client Install Flow ─────────────────────────────────────────────────────
install_client() {
    log "=== Installing Mesh CLIENT node ==="

    install_deps
    install_tailscale
    install_hashicorp
    configure_consul_client
    configure_nomad_client
    create_systemd_services
    write_config
    print_client_summary

    log "=== Client installation complete ==="
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    parse_args "$@"
    validate_args

    if [[ "$CHECK_ONLY" == "true" ]]; then
        log "Running prerequisite checks..."
        check_prerequisites
        log "Prerequisite check passed. Exiting (--check-only)."
        exit 0
    fi

    check_prerequisites

    case "$ROLE" in
        server)
            install_server
            ;;
        client)
            install_client
            ;;
        *)
            error "Unknown role: ${ROLE}"
            exit 1
            ;;
    esac
}

main "$@"
