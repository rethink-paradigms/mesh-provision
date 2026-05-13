#!/bin/bash
set -e
ROLE=$1
HAS_GPU="${2:-false}"  # "true" or "false"

echo ">>> [07] Configuring Nomad..."
mkdir -p /etc/nomad.d
mkdir -p /opt/nomad

# Base client configuration
cat <<EOF > /etc/nomad.d/nomad.hcl
datacenter = "dc1"
data_dir = "/opt/nomad"
bind_addr = "0.0.0.0"

client {
  enabled = true
  meta {
    role = "$ROLE"
  }
}
EOF

# NVIDIA plugin configuration (only if HAS_GPU == "true")
if [ "$HAS_GPU" == "true" ]; then
    cat <<EOF >> /etc/nomad.d/nomad.hcl

# Nomad NVIDIA Device Plugin Configuration
client {
  options = {
    "driver.allowlist" = "docker,nvidia"
  }
}

plugin "nvidia" {
  config {
    fingerprint_period = "30s"
  }
}
EOF
fi

# Server configuration (unchanged)
if [ "$ROLE" == "server" ]; then
  cat <<EOF >> /etc/nomad.d/nomad.hcl
server {
  enabled = true
  bootstrap_expect = 1
}
ui {
  enabled = true
}
EOF
fi
