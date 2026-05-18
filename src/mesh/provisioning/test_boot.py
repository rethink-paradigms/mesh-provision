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
        cluster_tier="cluster",
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

    rendered_yaml = generate_cloud_init(cluster_tier="cluster", 
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


def test_journald_persistence_in_cloud_init():
    """Test_JournaldPersistence: Verify cloud-init creates /var/log/journal for persistent logs."""
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
    )
    assert "mkdir -p /var/log/journal" in rendered
    assert "systemd-tmpfiles --create --prefix /var/log/journal" in rendered


def test_journald_persistence_before_startup_script():
    """Test_JournaldPersistence_Ordering: Verify journald setup runs before startup.sh."""
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
    )
    journald_pos = rendered.index("mkdir -p /var/log/journal")
    startup_pos = rendered.index("cd /opt/ops-platform && ./startup.sh")
    assert journald_pos < startup_pos, "journald persistence must run before startup.sh"


def test_boot_script_files_exist():
    """
    Test_BootScript_Files_Exist: Basic check that modular scripts exist.
    Note: GPU scripts (04, 05, 08) and spot script (09) were planned but not yet
    implemented; numbering skips them (01, 02, 03, 06, 07, 10).
    07-configure-nomad.sh is now a Jinja2 template (.j2) rendered at provision time.
    """
    feature_dir = os.path.dirname(__file__)
    scripts_dir = os.path.join(feature_dir, "scripts")

    # Core scripts (always required)
    expected_scripts = [
        "01-install-deps.sh",
        "02-install-tailscale.sh",
        "03-install-hashicorp.sh",
        "07-configure-nomad.sh.j2",  # Jinja2 template, rendered at provision time
        "10-install-caddy.sh",
        # Boot-ordering scripts bundled for all tiers
        "99-wait-for-nomad.sh",
        "99-validate-daemon.sh",
    ]

    for script in expected_scripts:
        path = os.path.join(scripts_dir, script)
        assert os.path.exists(path), f"Missing script: {script}"


def test_shell_script_includes_cluster_tier_default_standard():
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server"
    )
    assert 'CLUSTER_TIER="cluster"' in rendered


def test_shell_script_includes_cluster_tier_lite():
    rendered = generate_cloud_init( 
        tailscale_key="ts-key-123",
        leader_ip="10.0.0.1",
        role="server",
        cluster_tier="solo",
    )
    assert 'CLUSTER_TIER="solo"' in rendered


def test_shell_script_lite_enables_caddy():
    rendered = generate_cloud_init(
        tailscale_key="ts-key-123",
        leader_ip="10.0.0.1",
        role="server",
        cluster_tier="solo",
    )
    assert 'ENABLE_CADDY="true"' in rendered


def test_shell_script_standard_enables_caddy():
    rendered = generate_cloud_init(
        tailscale_key="ts-key-123",
        leader_ip="10.0.0.1",
        role="server",
        cluster_tier="cluster",
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
        cluster_tier="solo",
    )
    cloud_config = yaml.safe_load(rendered_yaml.replace("#cloud-config\n", ""))
    startup_script_content = None
    for item in cloud_config["write_files"]:
        if item["path"] == "/opt/ops-platform/startup.sh":
            startup_script_content = item["content"]
            break
    assert startup_script_content is not None
    assert 'CLUSTER_TIER="solo"' in startup_script_content
    assert 'ENABLE_CADDY="true"' in startup_script_content


def test_boot_script_has_namespace_commands():
    """
    Test_BootScript_NamespaceCommands: Verify boot.sh creates Nomad namespaces
    for mesh-infra and mesh-bodies after Nomad service starts.
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
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
    rendered = generate_cloud_init(cluster_tier="cluster", 
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server"
    )
    nomad_restart_pos = rendered.index("systemctl restart nomad")
    namespace_infra_pos = rendered.index("mesh-infra")
    assert namespace_infra_pos > nomad_restart_pos
    # DAEMON_CONFIG was removed — no need to assert a following section exists


def test_existing_tests_still_pass():
    rendered = generate_cloud_init(cluster_tier="cluster", 
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server"
    )
    assert 'TAILSCALE_KEY="ts-key-123"' in rendered
    assert 'LEADER_IP="10.0.0.1"' in rendered
    assert 'ROLE="server"' in rendered
    assert 'CLUSTER_TIER="cluster"' in rendered
    assert 'ENABLE_CADDY="true"' in rendered


def test_nomad_template_renders_bootstrap_expect():
    """
    Test_NomadTemplate_RendersBootstrapExpect: Verify rendered nomad script
    contains the correct bootstrap_expect value.
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
        bootstrap_expect=3,
    )
    assert "bootstrap_expect = 3" in rendered


def test_nomad_template_default_bootstrap_expect_is_one():
    """
    Test_NomadTemplate_DefaultBootstrapExpectIsOne: Verify default is 1.
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
    )
    assert "bootstrap_expect = 1" in rendered


def test_nomad_template_server_role_includes_server_block():
    """
    Test_NomadTemplate_ServerRoleIncludesServerBlock: Verify server nodes
    get the server stanza in their Nomad config.
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
    )
    assert "server {" in rendered
    assert 'role = "server"' in rendered


def test_nomad_template_client_role_no_server_block():
    """
    Test_NomadTemplate_ClientRoleNoServerBlock: Verify worker nodes
    do NOT get the server stanza.
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="client",
    )
    assert "server {" not in rendered
    assert 'role = "client"' in rendered


def test_nomad_template_gpu_enables_nvidia_config():
    """
    Test_NomadTemplate_GpuEnablesNvidiaConfig: Verify has_gpu=True includes
    NVIDIA plugin configuration in the rendered Nomad script.
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
        has_gpu=True,
    )
    import yaml
    config = yaml.safe_load(rendered.replace("#cloud-config\n", ""))
    nomad_script = None
    for item in config.get("write_files", []):
        if "07-configure-nomad.sh" in item.get("path", ""):
            nomad_script = item.get("content", "")
            break
    assert nomad_script is not None, "07-configure-nomad.sh not found in write_files"
    assert "nvidia" in nomad_script.lower()
    assert "driver.allowlist" in nomad_script


def test_nomad_template_no_gpu_omits_nvidia():
    """
    Test_NomadTemplate_NoGpuOmitsNvidia: Verify has_gpu=False (default)
    does NOT include NVIDIA plugin config in the rendered Nomad script.
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
    )
    # Extract the 07-configure-nomad.sh content from write_files
    import yaml
    config = yaml.safe_load(rendered.replace("#cloud-config\n", ""))
    nomad_script = None
    for item in config.get("write_files", []):
        if "07-configure-nomad.sh" in item.get("path", ""):
            nomad_script = item.get("content", "")
            break
    assert nomad_script is not None, "07-configure-nomad.sh not found in write_files"
    assert "nvidia" not in nomad_script.lower(), "NVIDIA config should not appear when has_gpu=False"


# ---------------------------------------------------------------------------
# Feature: Boot ordering — synchronisation primitives (F8)
# ---------------------------------------------------------------------------


def test_boot_script_includes_wait_for_nomad():
    """
    Test_BootScript_IncludesWaitForNomad: Verify boot.sh calls wait-for-nomad
    before issuing Nomad API commands.

    Without this, `nomad namespace apply` races against Nomad's Raft leader
    election and silently fails (the || true swallows the error).
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
    )
    # The wait script must be called BEFORE namespace apply but AFTER restart
    nomad_restart_pos = rendered.index("systemctl restart nomad")
    wait_pos = rendered.index("99-wait-for-nomad.sh")
    namespace_pos = rendered.index("mesh-infra")
    assert nomad_restart_pos < wait_pos, "wait-for-nomad must appear after nomad restart"
    assert wait_pos < namespace_pos, "wait-for-nomad must appear before namespace apply"


def test_boot_script_replaces_timeout_two_with_validate_daemon():
    """
    Test_BootScript_ReplacesTimeoutTwo: Verify the old `timeout 2 mesh-daemon serve`
    diagnostic has been replaced with a config-validation approach that doesn't
    start the HTTP server.

    The old approach leaked PID/port state that raced against the subsequent
    `systemctl start mesh-daemon`.
    """
    rendered = generate_cloud_init(
        cluster_tier="cluster",
        tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
        daemon_config='''daemon:\n  cluster_id: test-cluster-id\n  gateway_url: https://example.com\n  heartbeat_interval_seconds: 30\n  auth_mode: both\n  auth_token: test-token\n  auth0_domain: test.auth0.com\n  auth0_audience: https://test\n  listen_addr: 0.0.0.0:8080\nstore:\n  path: /root/.mesh/state.db\nplugin:\n  dir: /root/.mesh/plugins\ningress:\n  adapter: caddy\nlimits:\n  max_bodies: 10\n  max_snapshots: 5\n''',
    )
    # Old diagnostic MUST NOT appear
    assert "timeout 2 /usr/local/bin/mesh-daemon serve" not in rendered, \
        "timeout 2 diagnostic must be removed"
    # New validation script MUST appear in runcmd
    assert "99-validate-daemon.sh" in rendered, \
        "99-validate-daemon.sh must be called instead"


def test_bootstrap_scripts_are_bundled_in_cloud_init():
    """
    Test_BootstrapScripts_AreBundled: Verify 99-wait-for-nomad.sh and
    99-validate-daemon.sh are included in write_files for all tiers.
    """
    for tier in ("standard", "solo"):
        rendered = generate_cloud_init(
            cluster_tier=tier,
            tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server",
        )
        import yaml
        config = yaml.safe_load(rendered.replace("#cloud-config\n", ""))
        paths = [w["path"] for w in config.get("write_files", [])]
        assert "opt/ops-platform/scripts/99-wait-for-nomad.sh" in "/".join(paths), \
            f"99-wait-for-nomad.sh must be bundled for tier={tier}"
        assert "opt/ops-platform/scripts/99-validate-daemon.sh" in "/".join(paths), \
            f"99-validate-daemon.sh must be bundled for tier={tier}"


def test_wait_for_nomad_script_uses_nomad_addr_env():
    """
    Test_WaitForNomad_UsesNomadAddrEnv: Verify the wait script honours
    $NOMAD_ADDR, $NOMAD_POLL_INTERVAL, and $NOMAD_WAIT_TIMEOUT overrides.
    """
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "scripts", "99-wait-for-nomad.sh")
    assert os.path.exists(script), f"Script not found: {script}"
    content = open(script).read()
    assert 'NOMAD_ADDR="${NOMAD_ADDR:-http://127.0.0.1:4646}"' in content
    assert 'NOMAD_POLL_INTERVAL' in content or 'POLL_INTERVAL' in content
    assert 'NOMAD_WAIT_TIMEOUT' in content or 'TIMEOUT' in content


def test_validate_daemon_script_gracefully_skips_without_config():
    """
    Test_ValidateDaemon_GracefullySkips: Verify the validate script handles
    a missing config file gracefully (non-leader nodes won't have one).
    """
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "scripts", "99-validate-daemon.sh")
    assert os.path.exists(script), f"Script not found: {script}"
    content = open(script).read()
    assert 'SKIP:' in content or 'exit 0' in content
    # Must not exit with error when config is absent (non-leader path)
    assert "not found (non-leader node" in content
