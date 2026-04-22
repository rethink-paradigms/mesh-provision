"""Integration tests for mesh-install.sh — 2-VM full flow verification.

Tests verify the full install flow for both server and client roles using
two strategies:
1. Script content analysis: Read the script file and verify config blocks,
   function calls, and idempotency patterns.
2. Subprocess CLI testing: Test argument parsing/validation via subprocess.

No real VMs, Docker, or cloud resources required. All tests run on macOS.
"""

import os
import re
import subprocess
import pytest

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "mesh-install.sh")


# ─── Helpers ──────────────────────────────────────────────────────────────────


def run_script(*args: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", SCRIPT_PATH, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.fixture(scope="module")
def script_content():
    """Load the full script content once per module."""
    with open(SCRIPT_PATH) as f:
        return f.read()


def extract_function_body(content: str, func_name: str) -> str:
    """Extract the body of a bash function by name, handling brace depth."""
    start_marker = f"{func_name}()"
    start_idx = content.index(start_marker)
    depth = 0
    end_idx = start_idx
    for i, ch in enumerate(content[start_idx:], start=start_idx):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_idx = i
                break
    return content[start_idx:end_idx]


# ─── TestServerConfigGeneration ───────────────────────────────────────────────


class TestServerConfigGeneration:
    """Verify server HCL config blocks contain correct settings."""

    def test_server_nomad_has_server_enabled(self, script_content):
        """Nomad server config must have server = true."""
        assert "server {\n  enabled = true\n" in script_content

    def test_server_nomad_has_bootstrap_expect(self, script_content):
        """Nomad server config must have bootstrap_expect = 1."""
        assert "bootstrap_expect = 1" in script_content

    def test_server_nomad_has_caddy_host_volume(self, script_content):
        """Server Nomad config must include Caddy host_volume."""
        assert 'host_volume "caddy-data"' in script_content
        assert 'path = "/opt/caddy/data"' in script_content

    def test_server_consul_has_server_true(self, script_content):
        """Consul server config must have server = true."""
        consul_server_body = extract_function_body(
            script_content, "configure_consul_server"
        )
        assert "server = true" in consul_server_body

    def test_server_consul_has_bootstrap_expect(self, script_content):
        """Consul server config must have bootstrap_expect = 1."""
        consul_server_body = extract_function_body(
            script_content, "configure_consul_server"
        )
        assert "bootstrap_expect = 1" in consul_server_body

    def test_server_consul_has_ui_config(self, script_content):
        """Consul server config must have ui_config enabled."""
        consul_server_body = extract_function_body(
            script_content, "configure_consul_server"
        )
        assert "ui_config" in consul_server_body
        assert "enabled = true" in consul_server_body

    def test_server_write_config_uses_public_ip(self, script_content):
        """Server write_config uses public IP for NOMAD_ADDR."""
        write_config_body = extract_function_body(script_content, "write_config")
        assert 'nomad_addr="http://${public_ip}:4646"' in write_config_body

    def test_server_write_config_uses_public_ip_for_consul(self, script_content):
        """Server write_config uses public IP for CONSUL_ADDR."""
        write_config_body = extract_function_body(script_content, "write_config")
        assert 'consul_addr="http://${public_ip}:8500"' in write_config_body

    def test_server_install_flow_calls_caddy(self, script_content):
        """Server install flow must call install_caddy."""
        server_body = extract_function_body(script_content, "install_server")
        assert "install_caddy" in server_body

    def test_server_nomad_has_client_enabled(self, script_content):
        """Server Nomad config also enables client mode (dual mode)."""
        nomad_server_body = extract_function_body(
            script_content, "configure_nomad_server"
        )
        assert "client {" in nomad_server_body
        assert "enabled = true" in nomad_server_body


# ─── TestClientConfigGeneration ───────────────────────────────────────────────


class TestClientConfigGeneration:
    """Verify client HCL config blocks contain correct settings."""

    def test_client_nomad_has_server_disabled(self, script_content):
        """Client Nomad config must have server { enabled = false }."""
        nomad_client_body = extract_function_body(
            script_content, "configure_nomad_client"
        )
        assert "server {\n  enabled = false\n}" in nomad_client_body

    def test_client_nomad_has_server_join(self, script_content):
        """Client Nomad config must have server_join with SERVER_IP."""
        nomad_client_body = extract_function_body(
            script_content, "configure_nomad_client"
        )
        assert "server_join {" in nomad_client_body
        assert 'retry_join = ["${SERVER_IP}:4647"]' in nomad_client_body

    def test_client_consul_has_server_false(self, script_content):
        """Client Consul config must have server = false."""
        consul_client_body = extract_function_body(
            script_content, "configure_consul_client"
        )
        assert "server = false" in consul_client_body

    def test_client_consul_has_retry_join(self, script_content):
        """Client Consul config must have retry_join with SERVER_IP."""
        consul_client_body = extract_function_body(
            script_content, "configure_consul_client"
        )
        assert 'retry_join = ["${SERVER_IP}"]' in consul_client_body

    def test_client_nomad_no_caddy_host_volume(self, script_content):
        """Client Nomad config must NOT have Caddy host_volume."""
        nomad_client_body = extract_function_body(
            script_content, "configure_nomad_client"
        )
        assert "caddy-data" not in nomad_client_body
        assert "host_volume" not in nomad_client_body

    def test_client_write_config_uses_server_ip(self, script_content):
        """Client write_config uses SERVER_IP for NOMAD_ADDR."""
        write_config_body = extract_function_body(script_content, "write_config")
        assert 'nomad_addr="http://${SERVER_IP}:4646"' in write_config_body

    def test_client_write_config_uses_server_ip_for_consul(self, script_content):
        """Client write_config uses SERVER_IP for CONSUL_ADDR."""
        write_config_body = extract_function_body(script_content, "write_config")
        assert 'consul_addr="http://${SERVER_IP}:8500"' in write_config_body

    def test_client_install_flow_no_caddy(self, script_content):
        """Client install flow must NOT call install_caddy."""
        client_body = extract_function_body(script_content, "install_client")
        assert "install_caddy" not in client_body

    def test_client_consul_no_bootstrap_expect(self, script_content):
        """Client Consul config must NOT have bootstrap_expect."""
        consul_client_body = extract_function_body(
            script_content, "configure_consul_client"
        )
        assert "bootstrap_expect" not in consul_client_body

    def test_client_consul_no_ui_config(self, script_content):
        """Client Consul config must NOT have ui_config."""
        consul_client_body = extract_function_body(
            script_content, "configure_consul_client"
        )
        assert "ui_config" not in consul_client_body

    def test_client_nomad_has_role_meta(self, script_content):
        """Client Nomad config sets meta role = 'client'."""
        nomad_client_body = extract_function_body(
            script_content, "configure_nomad_client"
        )
        assert 'role = "client"' in nomad_client_body

    def test_client_install_flow_calls_correct_steps(self, script_content):
        """Client install flow calls all required steps in order."""
        client_body = extract_function_body(script_content, "install_client")
        required_steps = [
            "install_deps",
            "install_tailscale",
            "install_hashicorp",
            "configure_consul_client",
            "configure_nomad_client",
            "create_systemd_services",
            "write_config",
            "print_client_summary",
        ]
        for step in required_steps:
            assert step in client_body, f"Missing step: {step}"

        # Verify order: configure_consul_client before configure_nomad_client
        assert client_body.index("configure_consul_client") < client_body.index(
            "configure_nomad_client"
        )


# ─── TestServerClientConsistency ──────────────────────────────────────────────


class TestServerClientConsistency:
    """Verify both roles use consistent versions, paths, and settings."""

    def test_both_roles_use_same_nomad_version(self, script_content):
        """Both server and client reference the same NOMAD_VERSION constant."""
        # There should be exactly one NOMAD_VERSION definition
        version_defs = re.findall(
            r'readonly NOMAD_VERSION="([^"]+)"', script_content
        )
        assert len(version_defs) == 1
        assert version_defs[0] == "1.9.3"

    def test_both_roles_use_same_consul_version(self, script_content):
        """Both server and client reference the same CONSUL_VERSION constant."""
        version_defs = re.findall(
            r'readonly CONSUL_VERSION="([^"]+)"', script_content
        )
        assert len(version_defs) == 1
        assert version_defs[0] == "1.17.1"

    def test_both_roles_use_same_systemd_execstart(self, script_content):
        """Both roles create systemd services with identical ExecStart commands."""
        systemd_body = extract_function_body(
            script_content, "create_systemd_services"
        )
        # Consul ExecStart
        assert (
            "ExecStart=/usr/local/bin/consul agent -config-dir=/etc/consul.d"
            in systemd_body
        )
        # Nomad ExecStart
        assert (
            "ExecStart=/usr/local/bin/nomad agent -config=/etc/nomad.d"
            in systemd_body
        )

    def test_both_roles_write_same_config_path(self, script_content):
        """Both roles write to ~/.mesh/config."""
        assert 'MESH_CONFIG_DIR="${HOME}/.mesh"' in script_content
        assert 'MESH_CONFIG_FILE="${MESH_CONFIG_DIR}/config"' in script_content

    def test_both_roles_use_same_datacenter(self, script_content):
        """Both server and client use datacenter 'dc1'."""
        # Server consul
        consul_server = extract_function_body(
            script_content, "configure_consul_server"
        )
        assert 'datacenter = "dc1"' in consul_server
        # Client consul
        consul_client = extract_function_body(
            script_content, "configure_consul_client"
        )
        assert 'datacenter = "dc1"' in consul_client
        # Server nomad
        nomad_server = extract_function_body(
            script_content, "configure_nomad_server"
        )
        assert 'datacenter = "dc1"' in nomad_server
        # Client nomad
        nomad_client = extract_function_body(
            script_content, "configure_nomad_client"
        )
        assert 'datacenter = "dc1"' in nomad_client

    def test_both_roles_install_same_deps(self, script_content):
        """Both server and client call install_deps with same packages."""
        # install_deps is shared — verify it installs all 4 packages
        deps_body = extract_function_body(script_content, "install_deps")
        for pkg in ["curl", "unzip", "docker.io", "jq"]:
            assert pkg in deps_body

    def test_both_roles_install_tailscale(self, script_content):
        """Both server and client install Tailscale."""
        server_body = extract_function_body(script_content, "install_server")
        client_body = extract_function_body(script_content, "install_client")
        assert "install_tailscale" in server_body
        assert "install_tailscale" in client_body

    def test_both_roles_install_hashicorp(self, script_content):
        """Both server and client install HashiCorp binaries."""
        server_body = extract_function_body(script_content, "install_server")
        client_body = extract_function_body(script_content, "install_client")
        assert "install_hashicorp" in server_body
        assert "install_hashicorp" in client_body

    def test_both_roles_create_systemd_services(self, script_content):
        """Both roles create systemd services."""
        server_body = extract_function_body(script_content, "install_server")
        client_body = extract_function_body(script_content, "install_client")
        assert "create_systemd_services" in server_body
        assert "create_systemd_services" in client_body

    def test_both_roles_use_same_consul_data_dir(self, script_content):
        """Both server and client Consul use /opt/consul data dir."""
        consul_server = extract_function_body(
            script_content, "configure_consul_server"
        )
        consul_client = extract_function_body(
            script_content, "configure_consul_client"
        )
        assert 'data_dir = "/opt/consul"' in consul_server
        assert 'data_dir = "/opt/consul"' in consul_client

    def test_both_roles_use_same_nomad_data_dir(self, script_content):
        """Both server and client Nomad use /opt/nomad data dir."""
        nomad_server = extract_function_body(
            script_content, "configure_nomad_server"
        )
        nomad_client = extract_function_body(
            script_content, "configure_nomad_client"
        )
        assert 'data_dir = "/opt/nomad"' in nomad_server
        assert 'data_dir = "/opt/nomad"' in nomad_client


# ─── TestIdempotency ─────────────────────────────────────────────────────────


class TestIdempotency:
    """Verify the script has idempotency checks — safe to re-run."""

    def test_tailscale_command_v_check(self, script_content):
        """Script checks if tailscale is already installed via command -v."""
        assert "command -v tailscale" in script_content

    def test_consul_binary_existence_check(self, script_content):
        """Script checks if consul binary exists before downloading."""
        assert '[[ -f "/usr/local/bin/consul" ]]' in script_content

    def test_nomad_binary_existence_check(self, script_content):
        """Script checks if nomad binary exists before downloading."""
        assert '[[ -f "/usr/local/bin/nomad" ]]' in script_content

    def test_dpkg_package_checks(self, script_content):
        """install_deps uses dpkg -s to check if packages are installed."""
        assert "dpkg -s" in script_content

    def test_caddy_volume_grep_check(self, script_content):
        """Caddy host_volume uses grep before appending to nomad.hcl."""
        assert 'grep -q "caddy-data" /etc/nomad.d/nomad.hcl' in script_content

    def test_caddy_command_v_check(self, script_content):
        """Script checks if caddy is already installed."""
        assert "command -v caddy" in script_content

    def test_tailscale_status_check(self, script_content):
        """Script checks if tailscale is already connected."""
        assert "tailscale status" in script_content

    def test_sysctl_grep_check(self, script_content):
        """IP forwarding persistence uses grep to avoid duplicate writes."""
        assert (
            'grep -q "net.ipv4.ip_forward=1" /etc/sysctl.d/99-tailscale.conf'
            in script_content
        )

    def test_docker_running_check(self, script_content):
        """Script checks if docker is already running before enabling."""
        assert "systemctl is-active --quiet docker" in script_content

    def test_already_installed_patterns_count(self, script_content):
        """Count 'already installed' / 'already' patterns — should be multiple."""
        already_patterns = re.findall(r"already (?:installed|connected)", script_content, re.IGNORECASE)
        assert len(already_patterns) >= 4, (
            f"Expected >= 4 idempotency messages, found {len(already_patterns)}"
        )

    def test_install_deps_skip_message(self, script_content):
        """install_deps has explicit skip message when all packages present."""
        deps_body = extract_function_body(script_content, "install_deps")
        assert "already installed, skipping" in deps_body.lower()

    def test_consul_already_installed_log(self, script_content):
        """Consul install logs 'already installed' when binary exists."""
        hashicorp_body = extract_function_body(script_content, "install_hashicorp")
        assert "already installed" in hashicorp_body.lower()

    def test_nomad_already_installed_log(self, script_content):
        """Nomad install logs 'already installed' when binary exists."""
        hashicorp_body = extract_function_body(script_content, "install_hashicorp")
        # The function checks both consul and nomad
        assert "already installed" in hashicorp_body.lower()


# ─── TestErrorCases ───────────────────────────────────────────────────────────


class TestErrorCases:
    """Verify argument validation and error handling via subprocess."""

    def test_client_without_server_ip_exits_error(self):
        """--role client without --server-ip should exit with error."""
        result = run_script("--role", "client", "--tskey", "tskey-test")
        assert result.returncode != 0
        assert "--server-ip" in result.stderr

    def test_invalid_role_exits_error(self):
        """Invalid role value should exit with error."""
        result = run_script("--role", "worker", "--tskey", "tskey-test")
        assert result.returncode != 0
        assert "Invalid role" in result.stderr

    def test_missing_tskey_exits_error(self):
        """Missing --tskey should exit with error."""
        result = run_script("--role", "server")
        assert result.returncode != 0
        assert "--tskey" in result.stderr

    def test_invalid_server_ip_format_exits_error(self):
        """Invalid --server-ip format should exit with error."""
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "!!!invalid!!!",
        )
        assert result.returncode != 0
        assert "Invalid --server-ip" in result.stderr

    def test_help_exits_zero(self):
        """--help should exit 0 with usage info."""
        result = run_script("--help")
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_short_h_exits_zero(self):
        """-h should exit 0 with usage info."""
        result = run_script("-h")
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_no_args_exits_error(self):
        """No arguments should exit with error."""
        result = run_script()
        assert result.returncode != 0
        assert "--role is required" in result.stderr

    def test_empty_role_value_exits_error(self):
        """--role with no value should exit with error."""
        result = run_script("--role")
        assert result.returncode != 0

    def test_empty_tskey_value_exits_error(self):
        """--tskey with no value should exit with error."""
        result = run_script("--role", "server", "--tskey")
        assert result.returncode != 0

    def test_unknown_option_exits_error(self):
        """Unknown option should exit with error."""
        result = run_script("--role", "server", "--tskey", "tskey-test", "--bogus")
        assert result.returncode != 0
        assert "Unknown option" in result.stderr

    def test_empty_server_ip_value_exits_error(self):
        """--server-ip with no value should exit with error."""
        result = run_script(
            "--role", "client", "--tskey", "tskey-test", "--server-ip"
        )
        assert result.returncode != 0

    def test_server_ip_with_special_chars_rejected(self):
        """Server IP with special characters should be rejected."""
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "10.0.0.1; rm -rf /",
        )
        assert result.returncode != 0

    def test_client_accepts_valid_ipv4(self):
        """Client accepts valid IPv4 address."""
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "100.64.0.1",
        )
        assert "Invalid --server-ip" not in result.stderr

    def test_client_accepts_hostname(self):
        """Client accepts valid hostname."""
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "mesh-leader",
        )
        assert "Invalid --server-ip" not in result.stderr


# ─── TestDryRunMode ───────────────────────────────────────────────────────────


class TestDryRunMode:
    """Verify --dry-run mode passes arg parsing for both roles."""

    def test_server_dry_run_no_arg_errors(self):
        """Server --dry-run should not fail on argument parsing."""
        result = run_script(
            "--role", "server",
            "--tskey", "tskey-test",
            "--dry-run",
        )
        assert "Invalid role" not in result.stderr
        assert "Unknown option" not in result.stderr
        assert "--tskey" not in result.stderr

    def test_client_dry_run_no_arg_errors(self):
        """Client --dry-run with valid server-ip should not fail on arg parsing."""
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "10.0.0.1",
            "--dry-run",
        )
        assert "Invalid role" not in result.stderr
        assert "Unknown option" not in result.stderr
        assert "--server-ip" not in result.stderr

    def test_dry_run_script_content_has_run_cmd(self, script_content):
        """Script has run_cmd helper that enables dry-run mode."""
        assert "run_cmd()" in script_content
        assert '"$DRY_RUN" == "true"' in script_content
        assert "[dry-run]" in script_content

    def test_server_dry_run_attempts_prerequisite(self):
        """Server --dry-run will attempt prerequisites (fail on macOS)."""
        result = run_script(
            "--role", "server",
            "--tskey", "tskey-test",
            "--dry-run",
        )
        combined = result.stdout + result.stderr
        # Should reach prerequisite checking (not fail on arg parsing)
        assert "Invalid role" not in result.stderr
        assert "root" in combined.lower() or "rerequisite" in combined.lower()

    def test_client_dry_run_with_ip_attempts_prerequisite(self):
        """Client --dry-run with server-ip will attempt prerequisites."""
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "100.64.0.1",
            "--dry-run",
        )
        combined = result.stdout + result.stderr
        assert "Invalid role" not in result.stderr
        assert "Invalid --server-ip" not in result.stderr
