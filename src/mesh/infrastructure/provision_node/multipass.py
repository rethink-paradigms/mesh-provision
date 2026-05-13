"""
Adapter: Multipass Provisioner for Nodes
Handles provisioning of nodes on Multipass using subprocess calls.
"""

import os
import subprocess
import json
import yaml
import click  # Used by the original cli.py for styling output
from typing import Dict, Any, Optional, Union, List

MULTIPASS_CMD = "multipass"


def generate_cloud_init_yaml(
    boot_script_content: str,
    daemon_config: Optional[str] = None,
    ssh_authorized_keys: Optional[List[str]] = None,
) -> str:
    """
    Generate the cloud-init YAML content to execute the boot script.

    Args:
        boot_script_content: The shell script content to execute on boot.
        daemon_config: Mesh daemon configuration YAML content to write
                       to /etc/mesh/config.yaml (default: None).
        ssh_authorized_keys: Optional list of SSH public keys to inject into cloud-init.
            Auto-reads ~/.ssh/mesh_test_key.pub if None. (default: None).

    Returns:
        Cloud-init YAML as a string prefixed with "#cloud-config".
    """
    cloud_config = {
        "package_update": True,
        "packages": ["curl", "git"],
        "write_files": [
            {
                "path": "/opt/ops-platform/startup.sh",
                "permissions": "0755",
                "content": boot_script_content,
            }
        ],
        "runcmd": ["/opt/ops-platform/startup.sh"],
    }

    # Daemon runs on leader only; workers get Nomad/Consul only
    if daemon_config:
        cloud_config["write_files"].append({
            "path": "/etc/mesh/config.yaml",
            "permissions": "0600",
            "content": daemon_config,
        })
        cloud_config.setdefault("runcmd", []).append(
            'sh -c \'INSTALL_URL="${MESH_DAEMON_INSTALL_URL:-https://releases.mesh.dev/daemon/latest/install.sh}" && curl -fsSL "$INSTALL_URL" | bash\''
        )

    # Inject SSH authorized keys for test VM access
    if ssh_authorized_keys is None:
        import pathlib
        key_file = pathlib.Path.home() / ".ssh" / "mesh_test_key.pub"
        if key_file.exists():
            ssh_authorized_keys = [key_file.read_text().strip()]
    if ssh_authorized_keys:
        import re
        KEY_PATTERN = re.compile(r'^ssh-(ed25519|rsa|ecdsa|dss) [A-Za-z0-9+/=]+(\s+\S+)?\s*$')
        valid_keys = [k for k in ssh_authorized_keys if KEY_PATTERN.match(k)]
        if valid_keys:
            cloud_config.setdefault("ssh_authorized_keys", []).extend(valid_keys)

    # Dump to string, then prepend #cloud-config
    yaml_content = yaml.dump(cloud_config, default_flow_style=False)
    return "#cloud-config\n" + yaml_content


def provision_multipass_node(
    name: str,
    instance_size: str,  # e.g., "2CPU,1GB"
    role: str,  # "server" or "client"
    boot_script_content: Union[str, Any],  # Can be Pulumi Output in orchestration context
    opts: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Provisions a node on Multipass using subprocess calls.
    """

    # Runtime check for Pulumi Output
    # We check if it has 'apply' attribute as a duck-type check for pulumi.Output
    if hasattr(boot_script_content, "apply"):
        raise TypeError(
            "Multipass adapter received a Pulumi Output. "
            "It currently requires a resolved string. "
            "Please use .apply() in the caller to resolve the value before calling this function "
            "or run this adapter outside of a Pulumi stack."
        )

    # 1. Parse Instance Size
    cpus = "1"
    mem = "512M"

    if "," in instance_size:
        parts = instance_size.split(",")
        for part in parts:
            part = part.strip()
            if "CPU" in part:
                cpus = part.replace("CPU", "")
            elif "GB" in part:
                mem = part.replace("GB", "G")
            elif "MB" in part:
                mem = part.replace("MB", "M")
            elif "G" in part or "M" in part:
                mem = part

    # 2. Prepare Cloud-Init
    cloud_init_content = generate_cloud_init_yaml(boot_script_content)
    temp_cloud_init_path = f"/tmp/cloud-init-{name}.yaml"
    with open(temp_cloud_init_path, "w") as f:
        f.write(cloud_init_content)

    # 3. Check Status & Launch
    node_exists = False
    is_running = False

    res = subprocess.run(
        [MULTIPASS_CMD, "info", name, "--format", "json"], capture_output=True, text=True
    )
    if res.returncode == 0:
        try:
            info = json.loads(res.stdout)
            node_info = info.get("info", {}).get(name)
            if node_info:
                node_exists = True
                if node_info.get("state") == "Running":
                    is_running = True
                    click.echo(f"     ✅ {name} is already running.")
                else:
                    click.echo(
                        f"     🔄 {name} exists but is {node_info.get('state')}. Starting..."
                    )
                    subprocess.run([MULTIPASS_CMD, "start", name], check=True)
                    is_running = True
        except json.JSONDecodeError:
            pass

    if not node_exists:
        click.echo(f"     🚀 Launching {name} ({cpus} CPU, {mem} RAM)...")
        cmd = [
            MULTIPASS_CMD,
            "launch",
            "lts",
            "--name",
            name,
            "--cpus",
            cpus,
            "--memory",
            mem,
            "--cloud-init",
            temp_cloud_init_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            click.echo(f"     ✅ {name} Launched.")
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"     ❌ Failed to launch {name}: {e.stderr}", fg="red"))
            if os.path.exists(temp_cloud_init_path):
                os.remove(temp_cloud_init_path)
            raise

    # 4. Retrieve IP Address
    res_info = subprocess.run(
        [MULTIPASS_CMD, "info", name, "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(res_info.stdout)
    ipv4_list = info.get("info", {}).get(name, {}).get("ipv4", [])

    public_ip = ipv4_list[0] if ipv4_list else "unknown"

    # 5. Cleanup
    if os.path.exists(temp_cloud_init_path):
        os.remove(temp_cloud_init_path)

    return {"public_ip": public_ip, "private_ip": public_ip, "instance_id": name}
