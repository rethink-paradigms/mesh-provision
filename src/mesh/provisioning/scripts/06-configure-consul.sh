#!/bin/bash
set -e
LEADER_IP=$1
ROLE=$2

echo ">>> [04] Configuring Consul..."

# Tailscale up (step 02) is async — the authkey join may not have completed yet.
# Poll `tailscale status --json` until BackendState is "Running" and we have an IP.
# JSON parsing with grep/cut avoids a dependency on jq at boot time.
MAX_RETRIES=30   # ~60 seconds with 2s intervals
RETRY_DELAY=2
TS_IP=""
for i in $(seq 1 $MAX_RETRIES); do
  STATUS=$(tailscale status --json 2>/dev/null || true)
  STATE=$(echo "$STATUS" | grep -o '"BackendState":"[^"]*"' | cut -d'"' -f4)
  if [ "$STATE" = "Running" ]; then
    TS_IP=$(echo "$STATUS" | grep -o '"TailscaleIPs":\["[^"]*"' | grep -o '"[0-9.]*"' | tr -d '"' | head -1)
    if [ -n "$TS_IP" ]; then
      echo "       Tailscale state: Running, IP: $TS_IP"
      break
    fi
  fi
  echo "       Waiting for Tailscale... state=${STATE:-unknown} (attempt $i/$MAX_RETRIES)"
  sleep $RETRY_DELAY
done

if [ -z "$TS_IP" ]; then
  echo "ERROR: Tailscale did not become Running after $((MAX_RETRIES * RETRY_DELAY)) seconds."
  echo "       Last status:"
  tailscale status --json 2>/dev/null || echo "       (tailscale status unavailable)"
  echo "       Cannot configure Consul without a Tailscale IP for bind_addr."
  exit 1
fi
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
