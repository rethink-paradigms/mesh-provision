"""
Tests for Feature: Boot Consul & Nomad
"""

import os
import pytest
import yaml
from mesh.provisioning.boot import generate_cloud_init, generate_cloud_init


def test_boot_script_rendering_shell():
    """
    Test_BootScript_Rendering_Shell: Verify boot.sh template renders with correct variables.
    """
    context = {
        "TAILSCALE_KEY": "ts-key-12345",
        "LEADER_IP": "10.0.0.1",
        "ROLE": "server",
    }

    rendered = generate_cloud_init(
        cluster_tier="standard",
        tailscale_key=context["TAILSCALE_KEY"],
        leader_ip=context["LEADER_IP"],
        role=context["ROLE"],
    )

    assert f'TAILSCALE_KEY="{context["TAILSCALE_KEY"]}"' in rendered
    assert f'LEADER_IP="{context["LEADER_IP"]}"' in rendered
    assert f'ROLE="{context["ROLE"]}"' in rendered
    assert "bash scripts/01-install-deps.sh" in rendered


def test_boot_script_rendering_cloud_init():
    """
    Test_BootScript_Rendering_CloudInit: Verify cloud-init YAML is correctly generated.
    """
    context = {"TAILSCALE_KEY": "ts-key-abc", "LEADER_IP": "10.0.0.2", "ROLE": "client"}

    rendered_yaml = generate_cloud_init(cluster_tier="standard", 
        tailscale_key=context["TAILSCALE_KEY"],
        leader_ip=context["LEADER_IP"],
        role=context["ROLE"],
    )

    # Verify it's valid YAML and contains the cloud-init header
    assert rendered_yaml.startswith("#cloud-config")

    # Load and check some expected structure
    cloud_config = yaml.safe_load(rendered_yaml.replace("#cloud-config\n", ""))
    assert cloud_config["package_update"] is True
    assert "cd /opt/ops-platform && ./startup.sh" in cloud_config["runcmd"]

    # Check if the shell script content is inside write_files
    startup_script_content = None
    for item in cloud_config["write_files"]:
        if item["path"] == "/opt/ops-platform/startup.sh":
            startup_script_content = item["content"]
            break

    assert startup_script_content is not None
    assert f'TAILSCALE_KEY="{context["TAILSCALE_KEY"]}"' in startup_script_content
    assert f'LEADER_IP="{context["LEADER_IP"]}"' in startup_script_content
    assert f'ROLE="{context["ROLE"]}"' in startup_script_content


def test_boot_script_files_exist():
    """
    Test_BootScript_Files_Exist: Basic check that modular scripts exist.
    Note: GPU scripts (04, 05, 08) and spot script (09) were planned but not yet
    implemented; numbering skips them (01, 02, 03, 06, 07, 10).
    """
    feature_dir = os.path.dirname(__file__)
    scripts_dir = os.path.join(feature_dir, "scripts")

    # Core scripts (always required)
    expected_scripts = [
        "01-install-deps.sh",
        "02-install-tailscale.sh",
        "03-install-hashicorp.sh",
        "06-configure-consul.sh",
        "07-configure-nomad.sh",
        "10-install-caddy.sh",
    ]

    for script in expected_scripts:
        path = os.path.join(scripts_dir, script)
        assert os.path.exists(path), f"Missing script: {script}"


def test_shell_script_includes_cluster_tier_default_standard():
    rendered = generate_cloud_init(
        cluster_tier="standard",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server"
    )
    assert 'CLUSTER_TIER="standard"' in rendered


def test_shell_script_includes_cluster_tier_lite():
    rendered = generate_cloud_init( 
        tailscale_key="ts-key-123",
        leader_ip="10.0.0.1",
        role="server",
        cluster_tier="lite",
    )
    assert 'CLUSTER_TIER="lite"' in rendered


def test_shell_script_lite_enables_caddy():
    rendered = generate_cloud_init(
        tailscale_key="ts-key-123",
        leader_ip="10.0.0.1",
        role="server",
        cluster_tier="lite",
    )
    assert 'ENABLE_CADDY="true"' in rendered


def test_shell_script_standard_enables_caddy():
    rendered = generate_cloud_init(
        tailscale_key="ts-key-123",
        leader_ip="10.0.0.1",
        role="server",
        cluster_tier="standard",
    )
    assert 'ENABLE_CADDY="true"' in rendered


@pytest.mark.skip(reason="'production' tier removed — only 'lite' and 'standard' exist")
def test_shell_script_production_disables_caddy():
    rendered = generate_cloud_init(
        tailscale_key="ts-key-123",
        leader_ip="10.0.0.1",
        role="server",
        cluster_tier="production",
    )
    assert 'ENABLE_CADDY="false"' in rendered


@pytest.mark.skip(reason="'ingress' tier removed — only 'lite' and 'standard' exist")
def test_shell_script_ingress_disables_caddy():
    rendered = generate_cloud_init(
        tailscale_key="ts-key-123",
        leader_ip="10.0.0.1",
        role="server",
        cluster_tier="ingress",
    )
    assert 'ENABLE_CADDY="false"' in rendered


def test_cloud_init_passes_cluster_tier():
    rendered_yaml = generate_cloud_init(
        tailscale_key="ts-key-abc",
        leader_ip="10.0.0.2",
        role="client",
        cluster_tier="lite",
    )
    cloud_config = yaml.safe_load(rendered_yaml.replace("#cloud-config\n", ""))
    startup_script_content = None
    for item in cloud_config["write_files"]:
        if item["path"] == "/opt/ops-platform/startup.sh":
            startup_script_content = item["content"]
            break
    assert startup_script_content is not None
    assert 'CLUSTER_TIER="lite"' in startup_script_content
    assert 'ENABLE_CADDY="true"' in startup_script_content


def test_boot_script_has_namespace_commands():
    """
    Test_BootScript_NamespaceCommands: Verify boot.sh creates Nomad namespaces
    for mesh-infra and mesh-bodies after Nomad service starts.
    """
    rendered = generate_cloud_init(
        cluster_tier="standard",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server"
    )
    assert 'nomad namespace apply -description "Mesh infrastructure (Caddy, monitoring)" mesh-infra' in rendered
    assert 'nomad namespace apply -description "Mesh agent bodies (daemon-managed)" mesh-bodies' in rendered


def test_boot_script_namespace_commands_after_nomad_restart():
    """
    Test_BootScript_NamespaceOrdering: Verify namespace commands appear
    after the nomad restart block (daemon section was removed — namespaces
    are now the final boot.sh content).
    """
    rendered = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server"
    )
    nomad_restart_pos = rendered.index("systemctl restart nomad")
    namespace_infra_pos = rendered.index("mesh-infra")
    assert namespace_infra_pos > nomad_restart_pos
    # DAEMON_CONFIG was removed — no need to assert a following section exists


def test_existing_tests_still_pass():
    rendered = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server"
    )
    assert 'TAILSCALE_KEY="ts-key-123"' in rendered
    assert 'LEADER_IP="10.0.0.1"' in rendered
    assert 'ROLE="server"' in rendered
    assert 'CLUSTER_TIER="standard"' in rendered
    assert 'ENABLE_CADDY="true"' in rendered
