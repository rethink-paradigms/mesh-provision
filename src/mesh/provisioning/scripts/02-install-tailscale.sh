#!/bin/bash
set -e
TS_KEY=$1

echo ">>> [02] Installing & Joining Tailscale..."

if [ -z "$TS_KEY" ]; then
  echo "WARN: TAILSCALE_KEY is empty - skipping Tailscale join."
  echo "      To enable Tailscale, pass tailscale_key in the provision payload."
  exit 0
fi

if ! command -v tailscale &> /dev/null; then
  TMP=$(mktemp) && curl -fsSL https://tailscale.com/install.sh -o "$TMP" && bash "$TMP" && rm "$TMP"
fi
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1

tailscale up --authkey="$TS_KEY" --hostname=node-$(cat /etc/hostname) --reset
