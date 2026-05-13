"""Tests for daemon_config parameter in boot scripts and cloud-init YAML."""

import yaml
from .generate_boot_scripts import generate_shell_script, generate_cloud_init_yaml


MINIMAL_ARGS = {
    "tailscale_key": "tskey-test",
    "leader_ip": "10.0.0.1",
    "role": "server",
}

# base64 of "server:\n  port: 8080\n"
SAMPLE_DAEMON_CONFIG = "c2VydmVyOgogIHBvcnQ6IDgwODAK"


def test_daemon_config_in_shell_script():
    """Verify generate_shell_script renders DAEMON_CONFIG variable, not POST_BOOT_SCRIPT."""
    rendered = generate_shell_script(
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    assert "DAEMON_CONFIG=" in rendered
    assert "POST_BOOT_SCRIPT=" not in rendered


def test_daemon_config_in_cloud_init_yaml():
    """Verify generate_cloud_init_yaml includes /etc/mesh/config.yaml write_files entry."""
    y = generate_cloud_init_yaml(
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    config_files = [
        f for f in config.get("write_files", []) if f["path"] == "/etc/mesh/config.yaml"
    ]
    assert len(config_files) == 1
    assert config_files[0]["permissions"] == "0600"


def test_empty_daemon_config_skips():
    """Verify empty config produces no config.yaml or daemon install in cloud-init."""
    y = generate_cloud_init_yaml(
        **MINIMAL_ARGS,
        daemon_config="",
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    config_files = [
        f for f in config.get("write_files", []) if f["path"] == "/etc/mesh/config.yaml"
    ]
    assert len(config_files) == 0
    # Should still have the original startup.sh runcmd plus goss install
    assert len(config.get("runcmd", [])) == 2


def test_daemon_config_base64_encoding():
    """Verify the rendered shell script uses base64 -d for decoding."""
    rendered = generate_shell_script(
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    assert "base64 -d > /etc/mesh/config.yaml" in rendered


def test_daemon_config_safe_escaping():
    """Verify printf '%%s' is used (not echo) for safe shell escaping."""
    rendered = generate_shell_script(
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    assert "printf '%s'" in rendered


def test_template_no_POST_BOOT_SCRIPT():
    """Verify POST_BOOT_SCRIPT string absent from rendered shell output."""
    rendered = generate_shell_script(
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    # The variable itself should NOT appear in rendered output
    assert "POST_BOOT_SCRIPT" not in rendered


def test_daemon_config_none_backward_compat():
    """Verify daemon_config=None produces same output as before (empty config)."""
    rendered = generate_shell_script(
        **MINIMAL_ARGS,
        daemon_config=None,
    )
    assert "DAEMON_CONFIG=" in rendered  # template var still rendered (empty)


def test_cloud_init_has_daemon_install_runcmd():
    """Verify cloud-init includes daemon install runcmd when daemon_config provided."""
    y = generate_cloud_init_yaml(
        **MINIMAL_ARGS,
        daemon_config=SAMPLE_DAEMON_CONFIG,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    runcmds = config.get("runcmd", [])
    install_cmds = [c for c in runcmds if "install.sh" in str(c)]
    assert len(install_cmds) >= 1
    assert "MESH_DAEMON_INSTALL_URL" in str(install_cmds[0])


def test_ssh_authorized_keys_in_cloud_init():
    """Verify ssh_authorized_keys parameter adds keys to cloud-init YAML."""
    y = generate_cloud_init_yaml(
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

    y = generate_cloud_init_yaml(
        **MINIMAL_ARGS,
        ssh_authorized_keys=None,
    )
    config = yaml.safe_load(y.replace("#cloud-config\n", ""))
    assert "ssh_authorized_keys" not in config
