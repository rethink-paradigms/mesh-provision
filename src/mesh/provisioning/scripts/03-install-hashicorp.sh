#!/bin/bash
set -e
NOMAD_VERSION="1.9.3"

echo ">>> [03] Installing Nomad..."

ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" ]]; then c_arch="arm64"; else c_arch="amd64"; fi

# Nomad
if [ ! -f "/usr/local/bin/nomad" ]; then
    curl -O https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
    unzip -o nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
    mv -f nomad /usr/local/bin/
    rm -f nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
fi
