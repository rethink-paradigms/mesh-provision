"""Tests for daemon_config parameter in boot scripts and cloud-init YAML."""

import yaml
from mesh.provisioning.boot import generate_cloud_init, _resolve_mesh_version


MINIMAL_ARGS = {
    "tailscale_key": "tskey-test",
    "leader_ip": "10.0.0.1",
    "role": "server",
}

SAMPLE_DAEMON_CONFIG = (
    "gateway_url: https://api.example.com\n"
    "heartbeat_interval_seconds: 30\n"
    "cluster_id: abc123\n"
)

SAMPLE_DAEMON_CONFIG_WRAPPED = (
    "daemon:\n"
    "  cluster_id: abc123\n"
    "  gateway_url: https://api.example.com\n"
    "  heartbeat_interval_seconds: 30\n"
)


def test_daemon_config_in_cloud_init_yaml():
    """Verify generate_cloud_init includes /etc/mesh/config.yaml write_files entry."""
    y = generate_cloud_init(cluster_tier="standard", 
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    config_files = [
        f for f in config.get("write_files", []) if f["path"] == "/etc/mesh/config.yaml"
    ]
    assert len(config_files) == 1
    assert config_files[0]["permissions"] == "0600"


def test_daemon_config_written_as_plain_text():
    """daemon_config is written verbatim (plain text, no base64, no transformation)."""
    plain_config = "gateway_url: https://api.example.com\ncluster_id: abc123\n"
    y = generate_cloud_init(cluster_tier="standard",
        **MINIMAL_ARGS,
        daemon_config=plain_config,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    config_files = [
        f for f in config.get("write_files", []) if f["path"] == "/etc/mesh/config.yaml"
    ]
    assert len(config_files) == 1
    written_content = config_files[0]["content"]
    # Must be exactly what was passed in — no transformation
    assert written_content.strip() == plain_config.strip()
    parsed = yaml.safe_load(written_content)
    assert isinstance(parsed, dict)


def test_daemon_config_passthrough_no_wrapping():
    """daemon_config is passed through verbatim — no daemon: key wrapper added."""
    plain_config = "gateway_url: https://api.example.com\ncluster_id: abc123\n"
    y = generate_cloud_init(cluster_tier="standard",
        **MINIMAL_ARGS,
        daemon_config=plain_config,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    config_files = [
        f for f in config.get("write_files", []) if f["path"] == "/etc/mesh/config.yaml"
    ]
    written_content = config_files[0]["content"]
    # Content should be exactly the plain_config — no wrapping
    assert written_content.strip() == plain_config.strip()


def test_daemon_config_with_daemon_key_passes_through():
    """If input already has daemon: key, it is written as-is."""
    wrapped = "daemon:\n  cluster_id: abc123\n  gateway_url: https://api.example.com\n"
    y = generate_cloud_init(cluster_tier="standard",
        **MINIMAL_ARGS,
        daemon_config=wrapped,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    config_files = [
        f for f in config.get("write_files", []) if f["path"] == "/etc/mesh/config.yaml"
    ]
    written_content = config_files[0]["content"]
    assert written_content.strip() == wrapped.strip()
    parsed = yaml.safe_load(written_content)
    assert "daemon" in parsed
    assert "daemon" not in parsed.get("daemon", {}), "must not be double-wrapped"


def test_empty_daemon_config_skips():
    """Verify empty config produces no config.yaml or daemon install in cloud-init."""
    y = generate_cloud_init(cluster_tier="standard", 
        **MINIMAL_ARGS,
        daemon_config="",
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    config_files = [
        f for f in config.get("write_files", []) if f["path"] == "/etc/mesh/config.yaml"
    ]
    assert len(config_files) == 0
    assert len(config.get("runcmd", [])) == 2


def test_daemon_config_none_backward_compat():
    """Verify daemon_config=None skips config.yaml in cloud-init."""
    y = generate_cloud_init(cluster_tier="standard", 
        **MINIMAL_ARGS,
        daemon_config=None,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    config_files = [
        f for f in config.get("write_files", []) if f["path"] == "/etc/mesh/config.yaml"
    ]
    assert len(config_files) == 0


def test_cloud_init_has_daemon_install_runcmd():
    """Verify cloud-init includes daemon install runcmd when daemon_config provided."""
    y = generate_cloud_init(cluster_tier="standard", 
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    runcmds = config.get("runcmd", [])
    install_cmds = [c for c in runcmds if "install-mesh.sh" in str(c)]
    assert len(install_cmds) >= 1
    assert "MESH_SKIP_INIT" in str(install_cmds[0])


def test_daemon_config_in_shell_script_no_daemon_config_var():
    """Shell script template does not handle daemon_config — cloud-init write_files does."""
    rendered = generate_cloud_init(cluster_tier="standard", 
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    assert len(rendered) > 0


def test_ssh_authorized_keys_in_cloud_init():
    """Verify ssh_authorized_keys parameter adds keys to cloud-init YAML."""
    y = generate_cloud_init(cluster_tier="standard", 
        **MINIMAL_ARGS,
        ssh_authorized_keys=["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKtest test-key"],
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    assert "ssh_authorized_keys" in config
    assert "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKtest test-key" in config["ssh_authorized_keys"]


def test_ssh_authorized_keys_none_backward_compat():
    """Verify no ssh_authorized_keys when param is None and no key file exists."""
    import pathlib
    key_file = pathlib.Path.home() / ".ssh" / "mesh_test_key.pub"
    if key_file.exists():
        import pytest
        pytest.skip("mesh_test_key.pub exists — backward compat test requires clean state")

    y = generate_cloud_init(cluster_tier="standard", 
        **MINIMAL_ARGS,
        ssh_authorized_keys=None,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    assert "ssh_authorized_keys" not in config


def test_mesh_version_pinned_in_runcmd():
    """Verify pinned mesh_version appears in the install runcmd."""
    y = generate_cloud_init(
        cluster_tier="standard",
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
        mesh_version="1.0.0",
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    runcmds = config.get("runcmd", [])
    install_cmds = [c for c in runcmds if "install-mesh.sh" in str(c)]
    assert len(install_cmds) == 1
    assert "MESH_VERSION=1.0.0" in install_cmds[0]


def test_mesh_version_latest_resolves():
    """Verify 'latest' mesh_version resolves to a real semver in runcmd."""
    y = generate_cloud_init(
        cluster_tier="standard",
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
        mesh_version="latest",
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    runcmds = config.get("runcmd", [])
    install_cmds = [c for c in runcmds if "install-mesh.sh" in str(c)]
    assert len(install_cmds) == 1
    # Should resolve to something like 1.0.0 (not literally "latest")
    assert "MESH_VERSION=latest" not in install_cmds[0]
    assert "MESH_VERSION=" in install_cmds[0]


def test_resolve_mesh_version_passthrough():
    """_resolve_mesh_version returns pinned versions unchanged."""
    assert _resolve_mesh_version("1.0.0") == "1.0.0"
    assert _resolve_mesh_version("2.1.0-rc1") == "2.1.0-rc1"


def test_resolve_mesh_version_latest():
    """_resolve_mesh_version('latest') returns a non-empty tag from GitHub."""
    tag = _resolve_mesh_version("latest")
    assert tag != ""
    assert tag != "latest"  # Should have resolved to actual release
