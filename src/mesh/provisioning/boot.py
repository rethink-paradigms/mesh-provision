"""
Cloud-init YAML generator for VM boot scripts.

This module builds the cloud-init YAML that gets injected as VM userdata
when a node is created. The YAML tells the VM what to do on first boot:
install dependencies, configure Nomad/Consul/Caddy, optionally start the
mesh daemon.

Public API:
    generate_cloud_init(...)  → full "#cloud-config\n..." YAML string

Design decisions:
  - daemon_config is PLAIN TEXT (not base64). The contract says plain text.
    This module does not attempt to decode, re-encode, or transform it.
    It is written verbatim to /etc/mesh/config.yaml on the VM.
  - SSH key injection is EXPLICIT ONLY. No auto-reading ~/.ssh/* files.
    Pass ssh_authorized_keys=[] (or omit) to inject nothing.
  - Scripts are bundled by tier. Lite tier skips Tailscale + Consul scripts.
"""

from __future__ import annotations

import importlib.resources
import os
import re
from typing import Optional

import yaml
from yaml import Dumper as _BaseDumper
from jinja2 import Environment, FileSystemLoader, StrictUndefined


class _LiteralStr(str):
    """Marker class so PyYAML uses literal block scalar style."""


def _literal_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class _LiteralDumper(_BaseDumper):
    pass

_LiteralDumper.add_representer(_LiteralStr, _literal_representer)
_LiteralDumper.add_representer(str, _literal_representer)

from mesh.tiers.tier_config import ClusterTier


# Matches leftover {{ VAR }} after Jinja2 rendering
_UNREPLACED_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

# Scripts run for each tier (in order)
_TIER_SCRIPTS: dict[str, list[str]] = {
    "lite": [
        "01-install-deps.sh",
        "03-install-hashicorp.sh",
        "07-configure-nomad.sh",
        "10-install-caddy.sh",
    ],
    "standard": [
        "01-install-deps.sh",
        "02-install-tailscale.sh",
        "03-install-hashicorp.sh",
        "06-configure-consul.sh",
        "07-configure-nomad.sh",
        "10-install-caddy.sh",
    ],
}

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
_BOOT_SH = os.path.join(os.path.dirname(__file__), "boot.sh")
_INSTALL_SH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "mesh", "scripts", "install.sh")
)


def generate_cloud_init(
    role: str,
    cluster_tier: str,
    tailscale_key: str = "",
    leader_ip: str = "",
    daemon_config: Optional[str] = None,
    ssh_authorized_keys: Optional[list[str]] = None,
    validate: bool = True,
) -> str:
    """Build a cloud-init YAML string for a VM.

    Args:
        role:               "server" (leader) or "client" (worker).
        cluster_tier:       "lite" or "standard".
        tailscale_key:      Tailscale auth key (required for standard tier).
        leader_ip:          Leader's public IP (required for worker nodes in standard tier).
        daemon_config:      Full /etc/mesh/config.yaml content as PLAIN TEXT.
                            Written verbatim to the VM. Not transformed.
                            Only provided for leader nodes.
        ssh_authorized_keys: List of SSH public key strings to inject.
                            Nothing is injected if omitted or empty.
        validate:           If True, raise if any {{ VAR }} remains unreplaced.

    Returns:
        A "#cloud-config\\n..." YAML string ready for use as VM userdata.
    """
    enable_caddy = True  # always — even lite tier runs Caddy for HTTPS
    enable_consul = cluster_tier == "standard"
    enable_tailscale = cluster_tier == "standard"

    # Render boot.sh via Jinja2
    env = Environment(
        loader=FileSystemLoader(os.path.dirname(__file__)),
        undefined=StrictUndefined if validate else __import__("jinja2").Undefined,
        autoescape=False,
    )
    template = env.get_template("boot.sh")
    rendered_script = template.render(
        TAILSCALE_KEY=tailscale_key,
        LEADER_IP=leader_ip,
        ROLE=role,
        HAS_GPU="false",
        CUDA_VERSION="12.1",
        DRIVER_VERSION="535",
        ENABLE_SPOT_HANDLING="false",
        PROVIDER="generic",
        SPOT_CHECK_INTERVAL="5",
        SPOT_GRACE_PERIOD="90",
        CLUSTER_TIER=cluster_tier,
        ENABLE_CADDY="true" if enable_caddy else "false",
        DAEMON_CONFIG="",  # daemon handled separately via write_files
    )

    if validate:
        leftover = _UNREPLACED_VAR.findall(rendered_script)
        if leftover:
            raise ValueError(
                f"Unreplaced template variables in boot.sh: {list(set(leftover))}"
            )

    # Expand tabs → spaces so PyYAML uses literal block scalars (|) not double-quoted style.
    # Bash scripts work correctly with spaces; double-quoted YAML escapes " → \" making
    # content assertions in tests and cloud-init parsing more fragile.
    rendered_script = rendered_script.expandtabs(4)

    # Build cloud-init structure
    cloud_config: dict = {
        "package_update": True,
        "packages": ["curl", "git"],
        "chpasswd": {"expire": False},
        "ssh_pwauth": False,
        "write_files": [
            {
                "path": "/opt/ops-platform/startup.sh",
                "permissions": "0755",
                "content": rendered_script,
            }
        ],
        "runcmd": ["cd /opt/ops-platform && ./startup.sh"],
    }

    # Bundle tier-appropriate modular scripts
    for script_name in _TIER_SCRIPTS.get(cluster_tier, _TIER_SCRIPTS["standard"]):
        script_path = os.path.join(_SCRIPTS_DIR, script_name)
        if os.path.exists(script_path):
            with open(script_path) as f:
                cloud_config["write_files"].append({
                    "path": f"/opt/ops-platform/scripts/{script_name}",
                    "permissions": "0755",
                    "content": f.read(),
                })

    # Daemon config injection (leader only, plain text pass-through)
    if daemon_config:
        install_sh_content = ""
        if os.path.exists(_INSTALL_SH):
            with open(_INSTALL_SH) as f:
                install_sh_content = f.read()

        cloud_config["write_files"] += [
            {
                "path": "/etc/mesh/config.yaml",
                "permissions": "0600",
                "content": daemon_config,
            },
            {
                "path": "/etc/systemd/system/mesh-daemon.service",
                "permissions": "0644",
                "content": _DAEMON_SYSTEMD_UNIT,
            },
        ]
        if install_sh_content:
            cloud_config["write_files"].append({
                "path": "/tmp/install-mesh.sh",
                "permissions": "0755",
                "content": install_sh_content,
            })
            cloud_config["runcmd"] += [
                "MESH_SKIP_INIT=1 MESH_VERSION=v0.1.1 bash /tmp/install-mesh.sh",
                # Ensure ~/.mesh/ and sub-dirs exist (store + plugin dir needed at daemon start)
                "mkdir -p /root/.mesh/plugins /root/.mesh/agents",
                # Try daemon directly for 2s to capture any startup error
                "timeout 2 /usr/local/bin/mesh-daemon serve --config /etc/mesh/config.yaml 2>/tmp/daemon-stderr.txt || true; cat /tmp/daemon-stderr.txt > /tmp/daemon-diag.txt 2>/dev/null; echo '--- diag end ---' >> /tmp/daemon-diag.txt",
                "systemctl daemon-reload && systemctl enable mesh-daemon && systemctl start mesh-daemon",
            ]

    # goss health spec (optional — silently skipped if not present)
    goss_spec = _load_goss_spec()
    if goss_spec:
        cloud_config["write_files"].append({
            "path": "/etc/mesh/goss.yaml",
            "permissions": "0644",
            "content": goss_spec,
        })
        cloud_config["runcmd"].append(
            "curl -fsSL --connect-timeout 10 --max-time 30 "
            "https://github.com/goss-org/goss/releases/download/v0.4.9/goss-linux-amd64 "
            "-o /usr/local/bin/goss && chmod +rx /usr/local/bin/goss"
        )

    # SSH keys — explicit only, no auto-discovery
    if ssh_authorized_keys:
        valid = _validated_ssh_keys(ssh_authorized_keys)
        if valid:
            cloud_config["ssh_authorized_keys"] = valid

    return "#cloud-config\n" + yaml.dump(
        cloud_config,
        default_flow_style=False,
        allow_unicode=True,
        Dumper=_LiteralDumper,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DAEMON_SYSTEMD_UNIT = """\
[Unit]
Description=Mesh Daemon -- Portable agent-body runtime
After=network-online.target docker.service

[Service]
Type=simple
ExecStart=/usr/local/bin/mesh-daemon serve --config /etc/mesh/config.yaml
Restart=on-failure
RestartSec=5
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

_SSH_KEY_PATTERN = re.compile(
    r"^ssh-(ed25519|rsa|ecdsa|dss) [A-Za-z0-9+/=]+(\s+\S+)?\s*$"
)


def _validated_ssh_keys(keys: list[str]) -> list[str]:
    return [k for k in keys if _SSH_KEY_PATTERN.match(k.strip())]


def _load_goss_spec() -> Optional[str]:
    """Load goss spec from workspace scripts/goss/ if available.

    Uses a search relative to this file's known location in the repo.
    Returns None silently if not found — goss is optional.
    """
    # Walk up to find workspace root (mesh-provision is 3 levels above provisioning/)
    candidate = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "goss", "mesh-daemon-goss.yaml")
    )
    if os.path.exists(candidate):
        with open(candidate) as f:
            return f.read()
    return None


def validate_rendered_template(content: str) -> tuple[bool, list[str]]:
    """Check if any {{ VAR }} placeholders remain unreplaced in rendered content.

    Returns:
        (is_valid, list_of_unreplaced_variables)
    """
    matches = _UNREPLACED_VAR.findall(content)
    if matches:
        return False, list(set(matches))
    return True, []


class TemplateValidationError(ValueError):
    """Raised when rendered template still contains unreplaced {{ VAR }} variables."""
    def __init__(self, message: str, unreplaced_variables: list[str]):
        self.unreplaced_variables = unreplaced_variables
        super().__init__(f"Template validation failed. {message} Unreplaced: {', '.join(unreplaced_variables)}")


def _get_jinja2_env(strict: bool = True):
    """Return a configured Jinja2 Environment (for testing/inspection)."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined as _Undefined
    return Environment(
        loader=FileSystemLoader(os.path.dirname(__file__)),
        undefined=StrictUndefined if strict else _Undefined,
        autoescape=False,
    )
