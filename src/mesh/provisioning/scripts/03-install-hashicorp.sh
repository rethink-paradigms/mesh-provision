#!/bin/bash
set -e
NOMAD_VERSION="1.9.3"

echo ">>> [03] Installing Nomad..."

# Skip if already installed by parallel downloader (04-download-binaries.sh)
if [ -f "/usr/local/bin/nomad" ]; then
    echo "Nomad already installed, skipping."
    exit 0
fi

ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" ]]; then c_arch="arm64"; else c_arch="amd64"; fi

# Nomad
curl -fsSL --retry 3 --retry-delay 2 \
    -O https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
unzip -q -o nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
mv -f nomad /usr/local/bin/
rm -f nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
