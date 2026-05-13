#!/bin/bash
set -e
LEADER_IP=$1
ROLE=$2
TS_IP=$(tailscale ip -4)

echo ">>> [04] Configuring Consul..."
mkdir -p /etc/consul.d
mkdir -p /opt/consul

cat <<EOF > /etc/consul.d/consul.hcl
datacenter = "dc1"
data_dir = "/opt/consul"
bind_addr = "$TS_IP"
client_addr = "0.0.0.0"
retry_join = ["$LEADER_IP"]
EOF

if [ "$ROLE" == "server" ]; then
  cat <<EOF >> /etc/consul.d/consul.hcl
server = true
bootstrap_expect = 1
ui_config {
  enabled = true
}
EOF
fi
