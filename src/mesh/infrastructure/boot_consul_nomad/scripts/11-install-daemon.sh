#!/bin/bash
set -euo pipefail

# Variables injected from boot.sh template
DAEMON_URL="{{ DAEMON_URL }}"
DAEMON_TOKEN="{{ DAEMON_TOKEN }}"
CLUSTER_TIER="{{ CLUSTER_TIER }}"
CLUSTER_ID="{{ CLUSTER_ID }}"

# Skip if token or URL not provided
if [ -z "$DAEMON_TOKEN" ] || [ -z "$DAEMON_URL" ]; then
    echo "Skipping daemon install (no token or URL provided)"
    exit 0
fi

# Idempotency: skip if daemon already installed
if [ -f /usr/local/bin/mesh-daemon ] && [ -f /etc/systemd/system/mesh-daemon.service ]; then
    echo "Mesh daemon already installed, skipping..."
    exit 0
fi

echo ">>> [11] Installing Mesh Daemon..."

# 1. Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    *)       echo "Warning: unsupported architecture: $ARCH"; exit 1 ;;
esac

# 2. Download binary (non-fatal on failure)
echo "Downloading mesh-daemon for $ARCH..."
curl -fsSL "${DAEMON_URL}-${ARCH}" -o /usr/local/bin/mesh-daemon || {
    echo "Warning: daemon download failed (non-fatal)"
    exit 0
}
chmod +x /usr/local/bin/mesh-daemon

# 3. Create config directory
mkdir -p /etc/mesh

# 4. Write daemon config.yaml per spec §9
cat > /etc/mesh/config.yaml << EOF
listen: "127.0.0.1:8080"
nomad_addr: "http://127.0.0.1:4646"
consul_addr: ""
data_dir: "/var/lib/mesh"
auth_token: "${DAEMON_TOKEN}"
tier: "${CLUSTER_TIER}"
EOF

# 5. Generate Caddyfile for lite-mode health proxy
if [ "${CLUSTER_TIER:-}" = "lite" ]; then
    echo ">>> Writing Caddyfile for lite-mode health proxy..."
    mkdir -p /etc/caddy
    cat > /etc/caddy/Caddyfile << 'CADDYEOF'
:80 {
    reverse_proxy /health localhost:8080
    respond "mesh-provision OK" 200
}
CADDYEOF
    echo ">>> Validating Caddyfile..."
    caddy validate --config /etc/caddy/Caddyfile || echo "WARNING: caddy validate failed, continuing..."
    echo ">>> Restarting Caddy with health proxy Caddyfile..."
    systemctl restart caddy || echo "WARNING: caddy restart failed, continuing..."
fi

# 6. Create systemd unit
cat > /etc/systemd/system/mesh-daemon.service << 'SYSTEMDEOF'
[Unit]
Description=Mesh Daemon — body lifecycle manager
Requires=network-online.target
After=network-online.target nomad.service

[Service]
Type=simple
ExecStart=/usr/local/bin/mesh-daemon serve
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
SYSTEMDEOF

# 7. Create data directory
mkdir -p /var/lib/mesh

# 8. Enable and start
systemctl daemon-reload
systemctl enable mesh-daemon
systemctl start mesh-daemon

echo "Mesh daemon installed and started."
