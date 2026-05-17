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
import json
import os
import re
import urllib.request
from typing import Optional

import yaml

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover
    _HAS_JSONSCHEMA = False
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
# Solo and cluster share the same scripts -- only bootstrap_expect and worker count differ.
_TIER_SCRIPTS: dict[str, list[str]] = {
    "solo": [
        "01-install-deps.sh",
        "02-install-tailscale.sh",
        "03-install-hashicorp.sh",
        "07-configure-nomad.sh",
        "10-install-caddy.sh",
    ],
    "cluster": [
        "01-install-deps.sh",
        "02-install-tailscale.sh",
        "03-install-hashicorp.sh",
        "07-configure-nomad.sh",
        "10-install-caddy.sh",
    ],
}

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
_BOOT_SH = os.path.join(os.path.dirname(__file__), "boot.sh")
_INSTALL_SH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "mesh", "scripts", "install.sh")
)

# Path to canonical daemon config schema (workspace root → contracts/)
# boot.py is at code/mesh-provision/src/mesh/provisioning/ ; 5x ".." reaches workspace root
_SCHEMA_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "contracts", "mesh-daemon-config.schema.json")
)


def _validate_daemon_config(config_str: str) -> None:
    """Validate daemon_config YAML against the canonical JSON Schema.

    This is the BOUNDARY GUARD between agent-bodies (generator) and mesh (consumer).
    If the generated config drifts from the canonical schema, this raises BEFORE
    the config reaches the VM, preventing runtime daemon crashes.

    Raises:
        ValueError: If validation fails with a clear, actionable message.
    """
    if not _HAS_JSONSCHEMA:
        # Best-effort: if jsonschema is not installed, skip validation but warn.
        # In production (workspace dev) it is available.
        return

    if not os.path.exists(_SCHEMA_PATH):
        # Schema missing (e.g. packaged install without contracts). Skip.
        return

    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)

    try:
        parsed = yaml.safe_load(config_str)
    except yaml.YAMLError as e:
        raise ValueError(f"daemon_config is not valid YAML: {e}") from e

    if not isinstance(parsed, dict):
        raise ValueError(f"daemon_config must parse to a YAML object (got {type(parsed).__name__})")

    try:
        jsonschema.validate(instance=parsed, schema=schema)
    except jsonschema.ValidationError as e:
        path = "/".join(str(p) for p in e.path) if e.path else "<root>"
        raise ValueError(
            f"daemon_config failed canonical schema validation at '{path}': {e.message}. "
            f"Schema: contracts/mesh-daemon-config.schema.json"
        ) from e


def generate_cloud_init(
    role: str,
    cluster_tier: str,
    tailscale_key: str = "",
    leader_ip: str = "",
    daemon_config: Optional[str] = None,
    ssh_authorized_keys: Optional[list[str]] = None,
    validate: bool = True,
    mesh_version: str = "latest",
    bootstrap_expect: int = 1,
    has_gpu: bool = False,
) -> str:
    """Build a cloud-init YAML string for a VM.

    Args:
        role:               "server" (leader) or "client" (worker).
        cluster_tier:       "solo" or "cluster".
        tailscale_key:      Tailscale auth key (required for standard tier).
        leader_ip:          Leader's public IP (required for worker nodes in standard tier).
        daemon_config:      Full /etc/mesh/config.yaml content as PLAIN TEXT.
                            Written verbatim to the VM. Not transformed.
                            Only provided for leader nodes.
        ssh_authorized_keys: List of SSH public key strings to inject.
                            Nothing is injected if omitted or empty.
        validate:           If True, raise if any {{ VAR }} remains unreplaced.
        mesh_version:       Mesh release version to install (e.g. "1.0.0").
                            Defaults to "latest" which resolves from GitHub API.
        bootstrap_expect:   Expected number of Nomad server nodes for raft quorum.
                            Defaults to 1 (single-server cluster).
        has_gpu:            Whether to include NVIDIA GPU plugin configuration.
                            Defaults to False.

    Returns:
        A "#cloud-config\\n..." YAML string ready for use as VM userdata.
    """
    resolved_version = _resolve_mesh_version(mesh_version)

    # Boundary guard: validate daemon_config against canonical schema before it
    # reaches the VM. Catches drift between agent-bodies generator and mesh Go parser.
    if daemon_config:
        _validate_daemon_config(daemon_config)

    enable_caddy = True  # always
    enable_tailscale = True  # always -- Tailscale installed for both solo and cluster

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
    # 07-configure-nomad.sh is a Jinja2 template -- render it with provision-time values
    # All other scripts are static files bundled verbatim
    for script_name in _TIER_SCRIPTS.get(cluster_tier, _TIER_SCRIPTS["cluster"]):
        if script_name == "07-configure-nomad.sh":
            nomad_env = Environment(
                loader=FileSystemLoader(_SCRIPTS_DIR),
                undefined=StrictUndefined if validate else __import__("jinja2").Undefined,
                autoescape=False,
            )
            nomad_template = nomad_env.get_template("07-configure-nomad.sh.j2")
            rendered_nomad = nomad_template.render(
                role=role,
                has_gpu=has_gpu,
                bootstrap_expect=bootstrap_expect,
                cluster_tier=cluster_tier,
            )
            if validate:
                leftover = _UNREPLACED_VAR.findall(rendered_nomad)
                if leftover:
                    raise ValueError(
                        f"Unreplaced template variables in 07-configure-nomad.sh.j2: {list(set(leftover))}"
                    )
            cloud_config["write_files"].append({
                "path": f"/opt/ops-platform/scripts/07-configure-nomad.sh",
                "permissions": "0755",
                "content": rendered_nomad,
            })
        else:
            script_path = os.path.join(_SCRIPTS_DIR, script_name)
            if os.path.exists(script_path):
                with open(script_path) as f:
                    cloud_config["write_files"].append({
                        "path": f"/opt/ops-platform/scripts/{script_name}",
                        "permissions": "0755",
                        "content": f.read(),
                    })

    # Always-bundled boot-ordering scripts (not tier-specific)
    # 99-wait-for-nomad.sh -- polls Nomad leader before issuing API commands
    # 99-validate-daemon.sh -- validates config without starting the HTTP server
    for bootstrap_script in ("99-wait-for-nomad.sh", "99-validate-daemon.sh"):
        script_path = os.path.join(_SCRIPTS_DIR, bootstrap_script)
        if os.path.exists(script_path):
            with open(script_path) as f:
                cloud_config["write_files"].append({
                    "path": f"/opt/ops-platform/scripts/{bootstrap_script}",
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
        ]
        if install_sh_content:
            cloud_config["write_files"].append({
                "path": "/tmp/install-mesh.sh",
                "permissions": "0755",
                "content": install_sh_content,
            })
            cloud_config["runcmd"] += [
                f"MESH_SKIP_INIT=1 MESH_VERSION={resolved_version} bash /tmp/install-mesh.sh",
                # Ensure ~/.mesh/ and sub-dirs exist (store + plugin dir needed at daemon start)
                "mkdir -p /root/.mesh/plugins /root/.mesh/agents",
                # Validate binary and config WITHOUT starting the server.
                # The old 'timeout 2 mesh-daemon serve ...' leaked PID files and
                # port state, racing against the systemctl start on the next line.
                "bash /opt/ops-platform/scripts/99-validate-daemon.sh",
                "systemctl daemon-reload && systemctl enable mesh-daemon && systemctl start mesh-daemon",
            ]

    # goss health spec (optional -- silently skipped if not present)
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

    # SSH keys -- explicit only, no auto-discovery
    if ssh_authorized_keys:
        valid = _validated_ssh_keys(ssh_authorized_keys)
        if valid:
            cloud_config["ssh_authorized_keys"] = valid

    # Pre-flight validation -- catch issues BEFORE they reach the VM
    if validate:
        _validate_cloud_init(cloud_config)

    return "#cloud-config\n" + yaml.dump(
        cloud_config,
        default_flow_style=False,
        allow_unicode=True,
        Dumper=_LiteralDumper,
    )


# ---------------------------------------------------------------------------
# Pre-flight validation -- catch cloud-init issues before VM deployment
# ---------------------------------------------------------------------------

# Characters that break PyYAML/cloud-init on Ubuntu 22.04
# (cloud-init uses Python's yaml module which rejects control chars & some UTF-8)
_YAML_UNSAFE_CHARS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f\u2013\u2014\u2018\u2019\u201c\u201d]")


def _validate_cloud_init(cloud_config: dict) -> None:
    """Run all pre-flight validations on the cloud-init config.

    Raises ValueError with a clear message if any check fails.
    This prevents broken cloud-init from reaching the VM.
    """
    # 1. Check all write_files content for non-ASCII / YAML-breaking characters
    _validate_write_files_content(cloud_config)

    # 2. YAML round-trip: dump then parse to ensure validity
    _validate_yaml_roundtrip(cloud_config)

    # 3. Validate shell script syntax with bash -n
    _validate_shell_syntax(cloud_config)


def _validate_write_files_content(cloud_config: dict) -> None:
    """Ensure all write_files content is safe for cloud-init YAML embedding."""
    write_files = cloud_config.get("write_files", [])
    for i, wf in enumerate(write_files):
        content = wf.get("content", "")
        path = wf.get("path", f"<entry {i}>")
        match = _YAML_UNSAFE_CHARS.search(content)
        if match:
            char = match.group()
            pos = match.start()
            snippet = content[max(0, pos - 20):pos + 20]
            raise ValueError(
                f"cloud-init write_files[{i}] (path={path}) contains "
                f"YAML-unsafe character U+{ord(char):04X} ({repr(char)}) at position {pos}. "
                f"Snippet: ...{snippet}..."
            )


def _validate_yaml_roundtrip(cloud_config: dict) -> None:
    """Dump to YAML and parse back to verify cloud-init compatibility."""
    dumped = yaml.dump(
        cloud_config,
        default_flow_style=False,
        allow_unicode=True,
        Dumper=_LiteralDumper,
    )
    try:
        yaml.safe_load(dumped)
    except yaml.YAMLError as exc:
        raise ValueError(
            f"Generated cloud-init YAML is invalid: {exc}. "
            "This usually means embedded scripts contain special characters."
        ) from exc


def _validate_shell_syntax(cloud_config: dict) -> None:
    """Run 'bash -n' on every shell script in write_files."""
    import subprocess
    import tempfile

    write_files = cloud_config.get("write_files", [])
    for i, wf in enumerate(write_files):
        path = wf.get("path", "")
        content = wf.get("content", "")
        if not path.endswith(".sh") or not content:
            continue
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            result = subprocess.run(
                ["bash", "-n", tmp],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                raise ValueError(
                    f"Shell syntax error in write_files[{i}] (path={path}): {stderr}"
                )
        finally:
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SSH_KEY_PATTERN = re.compile(
    r"^ssh-(ed25519|rsa|ecdsa|dss) [A-Za-z0-9+/=]+(\s+\S+)?\s*$"
)


def _validated_ssh_keys(keys: list[str]) -> list[str]:
    return [k for k in keys if _SSH_KEY_PATTERN.match(k.strip())]


def _load_goss_spec() -> Optional[str]:
    """Load goss spec from workspace scripts/goss/ if available.

    Uses a search relative to this file's known location in the repo.
    Returns None silently if not found -- goss is optional.
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


def _resolve_mesh_version(version: str) -> str:
    """Resolve mesh version for install.sh.

    - If version is not "latest", return it as-is.
    - If "latest", query GitHub API for the newest release tag.
    - On any failure, fall back to "latest" (install.sh will also resolve it).
    """
    if version != "latest":
        return version
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/rethink-paradigms/mesh/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "mesh-provision"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag_name", "")
            if tag:
                return tag
    except Exception:
        pass
    return "latest"


def _get_jinja2_env(strict: bool = True):
    """Return a configured Jinja2 Environment (for testing/inspection)."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined as _Undefined
    return Environment(
        loader=FileSystemLoader(os.path.dirname(__file__)),
        undefined=StrictUndefined if strict else _Undefined,
        autoescape=False,
    )
