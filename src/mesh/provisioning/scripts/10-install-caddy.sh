#!/bin/bash
set -euo pipefail

if command -v caddy &>/dev/null; then
	echo "Caddy already installed, skipping install..."
else
	echo "Installing Caddy..."

	sudo apt-get update -qq
	sudo apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
	sudo apt-get update -qq
	sudo apt-get install -y -qq caddy

	echo "Caddy installed successfully"
	caddy version
fi

# Write a Caddyfile that reverse-proxies to the mesh-daemon on :8080
# and explicitly enables the admin API for the daemon's ingress adapter.
cat <<'CADDY_EOF' > /etc/caddy/Caddyfile
{
    admin 127.0.0.1:2019
}

:80 {
    reverse_proxy localhost:8080
}
CADDY_EOF

systemctl reload caddy
echo "Caddy configured: port 80 -> mesh-daemon :8080, admin API on :2019"
