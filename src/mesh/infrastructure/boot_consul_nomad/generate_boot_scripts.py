"""
Feature: Boot Consul & Nomad - Script Generation
Generates the various boot scripts/cloud-init for node activation.
"""

import os
import re
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined
from typing import Optional, Tuple, List


class TemplateValidationError(Exception):
    """Raised when template validation fails with unreplaced variables."""

    def __init__(self, message: str, unreplaced_variables: List[str]):
        self.unreplaced_variables = unreplaced_variables
        super().__init__(message)

    def __str__(self):
        vars_str = ", ".join(self.unreplaced_variables)
        return f"Template validation failed. Unreplaced variables: {vars_str}"


def validate_rendered_template(content: str) -> Tuple[bool, List[str]]:
    """
    Validates that no unreplaced template variables remain in rendered content.

    Detects leftover Jinja2 variable syntax like {{ VAR }} that wasn't replaced
    during template rendering. Excludes Jinja2 literals, comments, and statements.

    Args:
        content: The rendered template string to validate

    Returns:
        Tuple of (is_valid, list_of_unreplaced_variables)

    Examples:
        >>> validate_rendered_template('KEY="value"')
        (True, [])

        >>> validate_rendered_template('KEY="{{ KEY }}"')
        (False, ['KEY'])
    """
    # Pattern for unreplaced Jinja2 variables
    # Matches {{ VAR_NAME }} but excludes:
    # - {{ "literal" }} - string literals
    # - {% ... %} - statements
    # - {# ... #} - comments
    pattern = r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}"

    matches = re.findall(pattern, content)

    if matches:
        unreplaced = list(set(matches))  # Unique variables
        return False, unreplaced

    return True, []


def _get_jinja2_env(strict: bool = True):
    """
    Get Jinja2 environment with configurable strictness.

    Args:
        strict: If True, use StrictUndefined to catch missing variables at render time.
                If False, use Undefined (renders as empty string).

    Returns:
        Configured Jinja2 Environment
    """
    script_dir = os.path.dirname(__file__)
    return Environment(
        loader=FileSystemLoader(script_dir),
        undefined=StrictUndefined if strict else Undefined,
        autoescape=False,  # We're generating shell scripts, not HTML
    )


def generate_shell_script(
    tailscale_key: str,
    leader_ip: str,
    role: str,
    has_gpu: bool = False,
    cuda_version: Optional[str] = None,
    driver_version: Optional[str] = None,
    enable_spot_handling: bool = False,
    spot_check_interval: int = 5,
    spot_grace_period: int = 90,
    validate: bool = True,
    cluster_tier: str = "production",
    provider: str = "generic",
    daemon_config: Optional[str] = None,
) -> str:
    """
    Generates the shell script content for bootstrapping a node.
    This is suitable for direct execution or AWS User Data.

    Args:
        tailscale_key: Tailscale auth key for mesh networking.
        leader_ip: IP address of the leader node.
        role: Node role ("server" or "client").
        has_gpu: Whether this node has GPU support (default: False).
        cuda_version: CUDA runtime version for GPU nodes (default: "12.1").
        driver_version: NVIDIA driver version (default: "535").
        enable_spot_handling: Enable spot instance interruption handling (default: False).
        spot_check_interval: Polling interval for spot termination notices in seconds (default: 5).
        spot_grace_period: Grace period for workload migration in seconds (default: 90).
        validate: Whether to validate rendered template (default: True).
        cluster_tier: Cluster tier - "lite", "standard", "ingress", "production" (default: "production").
        provider: Cloud provider name, used for provider-specific features like spot handling (default: "generic").
        daemon_config: Base64-encoded YAML content for /etc/mesh/config.yaml (default: None).

    Returns:
        Rendered shell script as a string.

    Raises:
        TemplateValidationError: If validation detects unreplaced template variables.
    """
    enable_caddy = cluster_tier in ("lite", "standard")

    env = _get_jinja2_env(strict=validate)
    template = env.get_template("boot.sh")
    rendered = template.render(
        TAILSCALE_KEY=tailscale_key,
        LEADER_IP=leader_ip,
        ROLE=role,
        HAS_GPU="true" if has_gpu else "false",
        CUDA_VERSION=cuda_version or "12.1",
        DRIVER_VERSION=driver_version or "535",
        ENABLE_SPOT_HANDLING="true" if enable_spot_handling else "false",
        PROVIDER=provider,
        SPOT_CHECK_INTERVAL=str(spot_check_interval),
        SPOT_GRACE_PERIOD=str(spot_grace_period),
        CLUSTER_TIER=cluster_tier,
        ENABLE_CADDY="true" if enable_caddy else "false",
        DAEMON_CONFIG=daemon_config or "",
    )

    # Validate rendered content if validation is enabled
    if validate:
        is_valid, unreplaced = validate_rendered_template(rendered)
        if not is_valid:
            raise TemplateValidationError(
                f"Template validation failed for {role} node. "
                f"Unreplaced variables: {', '.join(unreplaced)}",
                unreplaced,
            )

    return rendered


def generate_cloud_init_yaml(
    tailscale_key: str,
    leader_ip: str,
    role: str,
    has_gpu: bool = False,
    cuda_version: Optional[str] = None,
    driver_version: Optional[str] = None,
    enable_spot_handling: bool = False,
    spot_check_interval: int = 5,
    spot_grace_period: int = 90,
    validate: bool = True,
    cluster_tier: str = "production",
    provider: str = "generic",
    daemon_config: Optional[str] = None,
) -> str:
    """
    Generates the cloud-init YAML content for bootstrapping a node.
    This is suitable for systems supporting cloud-init (e.g., Multipass, some cloud providers).

    Args:
        tailscale_key: Tailscale auth key for mesh networking.
        leader_ip: IP address of the leader node.
        role: Node role ("server" or "client").
        has_gpu: Whether this node has GPU support (default: False).
        cuda_version: CUDA runtime version for GPU nodes (default: "12.1").
        driver_version: NVIDIA driver version (default: "535").
        enable_spot_handling: Enable spot instance interruption handling (default: False).
        spot_check_interval: Polling interval for spot termination notices in seconds (default: 5).
        spot_grace_period: Grace period for workload migration in seconds (default: 90).
        validate: Whether to validate rendered template (default: True).
        daemon_config: Mesh daemon configuration YAML content to write to /etc/mesh/config.yaml (default: None).

    Returns:
        Cloud-init YAML as a string.

    Raises:
        TemplateValidationError: If validation detects unreplaced template variables.
    """
    shell_script_content = generate_shell_script(
        tailscale_key,
        leader_ip,
        role,
        has_gpu,
        cuda_version,
        driver_version,
        enable_spot_handling,
        spot_check_interval,
        spot_grace_period,
        validate=validate,
        cluster_tier=cluster_tier,
        provider=provider,
        daemon_config=daemon_config,
    )

    # Cloud-init structure to execute the shell script
    cloud_config = {
        "package_update": True,
        "packages": ["curl", "git"],
        "write_files": [
            {
                "path": "/opt/ops-platform/startup.sh",
                "permissions": "0755",
                "content": shell_script_content,
            }
        ],
        "runcmd": ["cd /opt/ops-platform && ./startup.sh"],
    }

    # Bundle all modular scripts from the 'scripts/' directory
    script_dir = os.path.dirname(__file__)
    scripts_path = os.path.join(script_dir, "scripts")
    if os.path.exists(scripts_path) and os.path.isdir(scripts_path):
        for filename in os.listdir(scripts_path):
            if filename.endswith(".sh"):
                file_path = os.path.join(scripts_path, filename)
                with open(file_path, "r") as f:
                    content = f.read()
                cloud_config["write_files"].append(
                    {
                        "path": f"/opt/ops-platform/scripts/{filename}",
                        "permissions": "0755",
                        "content": content,
                    }
                )

    if daemon_config:
        cloud_config["write_files"].append({
            "path": "/etc/mesh/config.yaml",
            "permissions": "0600",
            "content": daemon_config,
        })
        cloud_config.setdefault("runcmd", []).append(
            'sh -c \'INSTALL_URL="${MESH_DAEMON_INSTALL_URL:-https://raw.githubusercontent.com/rethink-paradigms/mesh/main/scripts/install.sh}" && curl -fsSL "$INSTALL_URL" | MESH_SKIP_INIT=1 bash\''
        )

    # Install goss binary for daemon health verification
    cloud_config.setdefault("runcmd", []).append(
        'curl -fsSL https://github.com/goss-org/goss/releases/latest/download/goss-linux-amd64 '
        '-o /usr/local/bin/goss && chmod +rx /usr/local/bin/goss'
    )

    # Write goss spec to VM — read from workspace root for auto-propagation
    import pathlib
    # parents[0] = boot_consul_nomad, [1] = infrastructure, [2] = mesh, [3] = src, [4] = mesh-provision, [5] = mesh-workspace
    workspace_root = pathlib.Path(__file__).resolve().parents[5]
    goss_spec_file = workspace_root / 'scripts' / 'goss' / 'mesh-daemon-goss.yaml'
    if goss_spec_file.exists():
        goss_content = goss_spec_file.read_text()
        cloud_config["write_files"].append({
            "path": "/etc/mesh/goss.yaml",
            "permissions": "0644",
            "content": goss_content,
        })
    # If goss_spec_file does not exist: skip silently — goss is optional

    yaml_content = yaml.dump(cloud_config, default_flow_style=False)
    return "#cloud-config\n" + yaml_content
