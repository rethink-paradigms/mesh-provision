#!/bin/bash
set -euo pipefail

# Parallel binary downloader for mesh control-plane components.
# Replaces sequential downloads to cut boot time by ~60-70s.
# All downloads run concurrently; failure of any one aborts the entire step.

ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" ]]; then C_ARCH="arm64"; else C_ARCH="amd64"; fi
NOMAD_VERSION="1.9.3"

DL_DIR="/tmp/mesh-dl-$$"
mkdir -p "$DL_DIR"
# shellcheck disable=SC2064
trap "rm -rf '$DL_DIR'" EXIT

log_ok()  { printf "\033[32m OK\033[0m  %s\n" "$*"; }
log_err() { printf "\033[31mERR\033[0m  %s\n" "$*" >&2; }

declare -A PIDS=()
declare -A FAILS=()

# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------
download_file() {
    local name="$1" url="$2" dest="$3" max_time="${4:-60}"
    if curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 10 --max-time "$max_time" \
         "$url" -o "$dest" 2>/dev/null; then
        log_ok "$name downloaded"
        return 0
    else
        log_err "$name download failed"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Fan out downloads
# ---------------------------------------------------------------------------

# 1. Nomad
download_file "nomad" \
    "https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_${C_ARCH}.zip" \
    "$DL_DIR/nomad.zip" 90 &
PIDS["nomad"]=$!

# 2. mesh CLI + mesh-daemon (GitHub releases - install.sh handles both)
#    We pre-download the tarballs so install-mesh.sh can use them locally.
#    install-mesh.sh expects MESH_VERSION to be set.
if [ -n "${MESH_VERSION:-}" ] && [ "$MESH_VERSION" != "latest" ]; then
    RELEASE_TAG="$MESH_VERSION"
    ARCHIVE_VERSION="${RELEASE_TAG#v}"
    BASE_URL="https://github.com/rethink-paradigms/mesh/releases/download/${RELEASE_TAG}"

    download_file "mesh" \
        "${BASE_URL}/mesh_${ARCHIVE_VERSION}_linux_${C_ARCH}.tar.gz" \
        "$DL_DIR/mesh.tar.gz" 90 &
    PIDS["mesh"]=$!

    download_file "mesh-daemon" \
        "${BASE_URL}/mesh-daemon_${ARCHIVE_VERSION}_linux_${C_ARCH}.tar.gz" \
        "$DL_DIR/mesh-daemon.tar.gz" 90 &
    PIDS["mesh-daemon"]=$!
else
    # When version is "latest", install-mesh.sh resolves via GitHub API.
    # We can't pre-download in that case; let install-mesh.sh handle it.
    log_ok "MESH_VERSION=latest - skipping pre-download (install-mesh.sh will resolve)"
fi

# 3. Agent Vault install script
download_file "agent-vault" \
    "https://get.agent-vault.dev" \
    "$DL_DIR/agent-vault-install.sh" 30 &
PIDS["agent-vault"]=$!

# 4. goss (optional - only if GOSS_URL is set)
if [ -n "${GOSS_URL:-}" ]; then
    download_file "goss" "$GOSS_URL" "$DL_DIR/goss" 30 &
    PIDS["goss"]=$!
fi

# ---------------------------------------------------------------------------
# Collect results
# ---------------------------------------------------------------------------
FAIL=0
for name in "${!PIDS[@]}"; do
    if ! wait "${PIDS[$name]}"; then
        FAILS["$name"]=1
        FAIL=1
    fi
done

if [ "$FAIL" -ne 0 ]; then
    log_err "Downloads failed: ${!FAILS[*]}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Install from downloaded archives
# ---------------------------------------------------------------------------

# Nomad
if [ -f "$DL_DIR/nomad.zip" ]; then
    unzip -q -o "$DL_DIR/nomad.zip" -d "$DL_DIR"
    mv -f "$DL_DIR/nomad" /usr/local/bin/nomad
    chmod +x /usr/local/bin/nomad
    log_ok "Nomad installed"
fi

# mesh + mesh-daemon
if [ -f "$DL_DIR/mesh.tar.gz" ]; then
    mkdir -p "$DL_DIR/mesh-extracted"
    tar -xzf "$DL_DIR/mesh.tar.gz" -C "$DL_DIR/mesh-extracted"
    MESH_BIN=$(find "$DL_DIR/mesh-extracted" -type f -name "mesh" | head -1)
    if [ -n "$MESH_BIN" ]; then
        install -m 755 "$MESH_BIN" /usr/local/bin/mesh
        log_ok "mesh CLI installed"
    fi
fi

if [ -f "$DL_DIR/mesh-daemon.tar.gz" ]; then
    mkdir -p "$DL_DIR/mesh-daemon-extracted"
    tar -xzf "$DL_DIR/mesh-daemon.tar.gz" -C "$DL_DIR/mesh-daemon-extracted"
    DAEMON_BIN=$(find "$DL_DIR/mesh-daemon-extracted" -type f -name "mesh-daemon" | head -1)
    if [ -n "$DAEMON_BIN" ]; then
        install -m 755 "$DAEMON_BIN" /usr/local/bin/mesh-daemon
        log_ok "mesh-daemon installed"
    fi
fi

# Agent Vault
if [ -f "$DL_DIR/agent-vault-install.sh" ]; then
    bash "$DL_DIR/agent-vault-install.sh"
    log_ok "Agent Vault installed"
fi

# goss
if [ -f "$DL_DIR/goss" ]; then
    install -m 755 "$DL_DIR/goss" /usr/local/bin/goss
    log_ok "goss installed"
fi

log_ok "All control-plane binaries installed"
