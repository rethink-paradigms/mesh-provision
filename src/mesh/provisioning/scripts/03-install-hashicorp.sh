#!/bin/bash
set -e
NOMAD_VERSION="1.9.3"
CONSUL_VERSION="1.17.1"

echo ">>> [03] Installing HashiCorp Binaries..."

ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" ]]; then c_arch="arm64"; else c_arch="amd64"; fi

# Consul
if [ ! -f "/usr/local/bin/consul" ]; then
    curl -O https://releases.hashicorp.com/consul/${CONSUL_VERSION}/consul_${CONSUL_VERSION}_linux_${c_arch}.zip
    unzip -o consul_${CONSUL_VERSION}_linux_${c_arch}.zip
    mv -f consul /usr/local/bin/
    rm -f consul_${CONSUL_VERSION}_linux_${c_arch}.zip
fi

# Nomad
if [ ! -f "/usr/local/bin/nomad" ]; then
    curl -O https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
    unzip -o nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
    mv -f nomad /usr/local/bin/
    rm -f nomad_${NOMAD_VERSION}_linux_${c_arch}.zip
fi
