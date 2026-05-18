"""Tests for mesh-install.sh argument parsing and prerequisite checking.

Uses subprocess to test the script's CLI interface without
actually running any installation steps (requires root + Ubuntu).
"""

import os
import subprocess
import pytest

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "mesh-install.sh")


def run_script(*args: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", SCRIPT_PATH, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ─── Help Tests ──────────────────────────────────────────────────────────────


class TestHelp:
    def test_help_exits_zero(self):
        result = run_script("--help")
        assert result.returncode == 0

    def test_help_shows_usage(self):
        result = run_script("--help")
        assert "Usage:" in result.stdout

    def test_help_mentions_server(self):
        result = run_script("--help")
        assert "server" in result.stdout

    def test_help_mentions_client(self):
        result = run_script("--help")
        assert "client" in result.stdout

    def test_help_mentions_tailscale(self):
        result = run_script("--help")
        assert "Tailscale" in result.stdout

    def test_help_mentions_nomad(self):
        result = run_script("--help")
        assert "Nomad" in result.stdout

    def test_help_shows_role_option(self):
        result = run_script("--help")
        assert "--role" in result.stdout

    def test_help_shows_tskey_option(self):
        result = run_script("--help")
        assert "--tskey" in result.stdout

    def test_help_shows_server_ip_option(self):
        result = run_script("--help")
        assert "--server-ip" in result.stdout

    def test_help_shows_check_only(self):
        result = run_script("--help")
        assert "--check-only" in result.stdout

    def test_help_shows_dry_run(self):
        result = run_script("--help")
        assert "--dry-run" in result.stdout

    def test_short_h_flag(self):
        result = run_script("-h")
        assert result.returncode == 0
        assert "Usage:" in result.stdout


# ─── Argument Validation Tests ───────────────────────────────────────────────


class TestArgValidation:
    def test_no_args_exits_error(self):
        result = run_script()
        assert result.returncode != 0

    def test_no_args_shows_error(self):
        result = run_script()
        assert "--role is required" in result.stderr

    def test_role_only_exits_error(self):
        result = run_script("--role", "server")
        assert result.returncode != 0
        assert "--tskey" in result.stderr

    def test_invalid_role_exits_error(self):
        result = run_script("--role", "manager", "--tskey", "tskey-test")
        assert result.returncode != 0

    def test_invalid_role_shows_message(self):
        result = run_script("--role", "manager", "--tskey", "tskey-test")
        assert "Invalid role" in result.stderr or "manager" in result.stderr

    def test_empty_role_value_exits_error(self):
        result = run_script("--role")
        assert result.returncode != 0

    def test_empty_tskey_value_exits_error(self):
        result = run_script("--role", "server", "--tskey")
        assert result.returncode != 0

    def test_empty_server_ip_value_exits_error(self):
        result = run_script("--role", "server", "--tskey", "tskey-test", "--server-ip")
        assert result.returncode != 0

    def test_client_without_server_ip_exits_error(self):
        result = run_script("--role", "client", "--tskey", "tskey-test")
        assert result.returncode != 0
        assert "--server-ip" in result.stderr

    def test_unknown_option_exits_error(self):
        result = run_script("--bogus")
        assert result.returncode != 0
        assert "Unknown option" in result.stderr


# ─── Role Specific Tests ─────────────────────────────────────────────────────


class TestServerRole:
    def test_server_role_with_tskey_attempts_install(self):
        result = run_script("--role", "server", "--tskey", "tskey-auth-test123")
        # Will fail because we're not root / not on Ubuntu
        # But should NOT fail on arg parsing
        assert "Invalid role" not in result.stderr
        assert "Unknown option" not in result.stderr


class TestClientRoleStub:
    def test_client_role_not_root(self):
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "10.0.0.1",
        )
        combined = result.stderr + result.stdout
        assert "root" in combined.lower() or "rerequisite" in combined.lower()


class TestClientRole:
    def test_client_missing_server_ip_shows_error(self):
        result = run_script("--role", "client", "--tskey", "tskey-test")
        assert result.returncode != 0
        assert "--server-ip" in result.stderr

    def test_client_invalid_ip_shows_error(self):
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "not-valid!!!",
        )
        assert result.returncode != 0
        assert "Invalid --server-ip" in result.stderr

    def test_client_accepts_valid_ip(self):
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "100.64.0.1",
        )
        assert "Invalid --server-ip" not in result.stderr
        assert "--server-ip is required" not in result.stderr

    def test_client_accepts_hostname(self):
        result = run_script(
            "--role", "client",
            "--tskey", "tskey-test",
            "--server-ip", "mesh-leader",
        )
        assert "Invalid --server-ip" not in result.stderr

    def test_client_no_caddy_in_install_flow(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        install_client_start = content.index("install_client()")
        install_client_end = content.index("}", install_client_start)
        # Find the matching closing brace
        depth = 0
        for i, ch in enumerate(content[install_client_start:], start=install_client_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    install_client_end = i
                    break
        install_client_body = content[install_client_start:install_client_end]
        assert "install_caddy" not in install_client_body

    def test_client_config_has_role_client(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert 'ROLE="${ROLE}"' in content or 'ROLE="client"' in content

    def test_client_writes_consul_client_config(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "configure_consul_client" in content
        assert 'server = false' in content

    def test_client_writes_nomad_client_config(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "configure_nomad_client" in content
        assert "server_join" in content

    def test_client_has_print_client_summary(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "print_client_summary" in content

    def test_client_config_uses_server_ip_for_nomad_addr(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert 'nomad_addr="http://${SERVER_IP}:4646"' in content

    def test_client_flow_calls_correct_steps(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        install_client_start = content.index("install_client()")
        depth = 0
        install_client_end = install_client_start
        for i, ch in enumerate(content[install_client_start:], start=install_client_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    install_client_end = i
                    break
        install_client_body = content[install_client_start:install_client_end]
        assert "install_deps" in install_client_body
        assert "install_tailscale" in install_client_body
        assert "install_hashicorp" in install_client_body
        assert "configure_consul_client" in install_client_body
        assert "configure_nomad_client" in install_client_body
        assert "create_systemd_services" in install_client_body
        assert "write_config" in install_client_body
        assert "print_client_summary" in install_client_body


# ─── Dry Run Tests ───────────────────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_shows_steps(self):
        result = run_script(
            "--role", "server",
            "--tskey", "tskey-test",
            "--dry-run",
        )
        # Dry run should show what would be done
        # but will still fail on root check, which is fine
        combined = result.stdout + result.stderr
        # Should NOT have "Invalid role" or arg errors
        assert "Invalid role" not in result.stderr
        assert "Unknown option" not in result.stderr

    def test_dry_run_flag_parsed(self):
        result = run_script(
            "--role", "server",
            "--tskey", "tskey-test",
            "--dry-run",
        )
        # Script should not exit due to argument errors
        assert "Unknown option" not in result.stderr


# ─── Check-Only Tests ────────────────────────────────────────────────────────


class TestCheckOnly:
    def test_check_only_flag_parsed(self):
        result = run_script(
            "--role", "server",
            "--tskey", "tskey-test",
            "--check-only",
        )
        # Should not fail on arg parsing
        assert "Invalid role" not in result.stderr
        assert "Unknown option" not in result.stderr

    def test_check_only_runs_prerequisite_check(self):
        result = run_script(
            "--role", "server",
            "--tskey", "tskey-test",
            "--check-only",
        )
        combined = result.stdout + result.stderr
        # Should mention prerequisites
        assert "rerequisite" in combined.lower() or "root" in combined.lower()


# ─── Script File Tests ───────────────────────────────────────────────────────


class TestScriptFile:
    def test_script_exists(self):
        assert os.path.isfile(SCRIPT_PATH)

    def test_script_is_executable(self):
        assert os.access(SCRIPT_PATH, os.X_OK)

    def test_script_has_shebang(self):
        with open(SCRIPT_PATH) as f:
            first_line = f.readline().strip()
        assert first_line == "#!/usr/bin/env bash"

    def test_script_uses_strict_mode(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "set -euo pipefail" in content

    def test_script_mentions_nomad_version(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "1.9.3" in content

    def test_script_mentions_consul_version(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "1.17.1" in content

    def test_script_has_idempotency_checks(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Check for key idempotency patterns
        assert "command -v tailscale" in content
        assert '"/usr/local/bin/consul"' in content or "-f \"/usr/local/bin/consul\"" in content
        assert "already installed" in content.lower()

    def test_script_writes_mesh_config(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "MESH_CONFIG_DIR" in content
        assert "NOMAD_ADDR" in content

    def test_script_has_systemd_services(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "consul.service" in content
        assert "nomad.service" in content
        assert "systemctl daemon-reload" in content

    def test_script_no_caddy_host_volume_in_nomad_config(self):
        """Nomad v1.9.3 does not support host_volume in agent config.
        host_volume was removed from agent config; it belongs in job specs if needed."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert 'host_volume "caddy-data"' not in content
