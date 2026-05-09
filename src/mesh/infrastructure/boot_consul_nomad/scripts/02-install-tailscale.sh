#!/bin/bash
set -e
TS_KEY=$1

echo ">>> [02] Installing & Joining Tailscale..."
if ! command -v tailscale &> /dev/null; then
  TMP=$(mktemp) && curl -fsSL https://tailscale.com/install.sh -o "$TMP" && bash "$TMP" && rm "$TMP"
fi
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1

tailscale up --authkey=$TS_KEY --hostname=node-$(cat /etc/hostname) --reset
