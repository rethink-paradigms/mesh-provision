#!/bin/bash
set -e
echo ">>> [01] Installing Dependencies..."
apt-get update -y
apt-get install -y curl unzip docker.io jq
