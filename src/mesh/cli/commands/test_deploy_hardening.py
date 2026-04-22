"""Tests for NOMAD_ADDR / CONSUL_ADDR discovery chain.

Validates the multi-source fallback:
    env var → ~/.mesh/config file → default localhost
"""

import os
import tempfile

import pytest

from mesh.infrastructure.config.env import (
    _parse_config_value,
    get_config_file_path,
    get_consul_addr,
    get_consul_addr_from_config,
    get_nomad_addr,
    get_nomad_addr_from_config,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove NOMAD_ADDR and CONSUL_ADDR from env for every test."""
    monkeypatch.delenv("NOMAD_ADDR", raising=False)
    monkeypatch.delenv("CONSUL_ADDR", raising=False)


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory and patch MESH_CONFIG_FILE."""
    cfg = tmp_path / ".mesh"
    cfg.mkdir()
    config_file = cfg / "config"
    monkeypatch.setattr(
        "mesh.infrastructure.config.env.MESH_CONFIG_DIR", str(cfg)
    )
    monkeypatch.setattr(
        "mesh.infrastructure.config.env.MESH_CONFIG_FILE", str(config_file)
    )
    return config_file


def _write_config(config_file, content: str):
    config_file.write_text(content)


# ---------------------------------------------------------------------------
# get_nomad_addr — env var priority
# ---------------------------------------------------------------------------


class TestNomadAddrEnvVarPriority:
    def test_env_var_takes_precedence_over_config(self, monkeypatch, config_dir):
        _write_config(config_dir, 'NOMAD_ADDR="http://100.64.0.1:4646"')
        monkeypatch.setenv("NOMAD_ADDR", "http://env-var-host:4646")
        assert get_nomad_addr() == "http://env-var-host:4646"

    def test_env_var_takes_precedence_over_default(self, monkeypatch):
        monkeypatch.setenv("NOMAD_ADDR", "http://custom:4646")
        assert get_nomad_addr() == "http://custom:4646"


# ---------------------------------------------------------------------------
# get_nomad_addr — config file
# ---------------------------------------------------------------------------


class TestNomadAddrFromConfig:
    def test_reads_quoted_value(self, config_dir):
        _write_config(config_dir, 'NOMAD_ADDR="http://100.64.0.1:4646"\n')
        assert get_nomad_addr() == "http://100.64.0.1:4646"

    def test_reads_single_quoted_value(self, config_dir):
        _write_config(config_dir, "NOMAD_ADDR='http://100.64.0.1:4646'\n")
        assert get_nomad_addr() == "http://100.64.0.1:4646"

    def test_reads_unquoted_value(self, config_dir):
        _write_config(config_dir, "NOMAD_ADDR=http://100.64.0.1:4646\n")
        assert get_nomad_addr() == "http://100.64.0.1:4646"

    def test_skips_comments(self, config_dir):
        _write_config(
            config_dir,
            "# This is a comment\nNOMAD_ADDR=http://100.64.0.1:4646\n",
        )
        assert get_nomad_addr() == "http://100.64.0.1:4646"

    def test_reads_among_multiple_keys(self, config_dir):
        _write_config(
            config_dir,
            'NOMAD_ADDR="http://100.64.0.1:4646"\n'
            'CONSUL_ADDR="http://100.64.0.1:8500"\n'
            'TAILSCALE_IP="100.64.0.1"\n'
            'ROLE="server"\n',
        )
        assert get_nomad_addr() == "http://100.64.0.1:4646"

    def test_missing_key_returns_none(self, config_dir):
        _write_config(config_dir, 'CONSUL_ADDR="http://1.2.3.4:8500"\n')
        assert get_nomad_addr_from_config() is None


# ---------------------------------------------------------------------------
# get_nomad_addr — default fallback
# ---------------------------------------------------------------------------


class TestNomadAddrDefaultFallback:
    def test_default_when_no_env_and_no_config(self, config_dir):
        assert get_nomad_addr() == "http://127.0.0.1:4646"

    def test_default_when_config_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mesh.infrastructure.config.env.MESH_CONFIG_DIR",
            str(tmp_path / "nonexistent"),
        )
        monkeypatch.setattr(
            "mesh.infrastructure.config.env.MESH_CONFIG_FILE",
            str(tmp_path / "nonexistent" / "config"),
        )
        assert get_nomad_addr() == "http://127.0.0.1:4646"

    def test_default_when_empty_config_file(self, config_dir):
        _write_config(config_dir, "")
        assert get_nomad_addr() == "http://127.0.0.1:4646"

    def test_default_when_config_has_only_comments(self, config_dir):
        _write_config(config_dir, "# no useful data\n# another comment\n")
        assert get_nomad_addr() == "http://127.0.0.1:4646"


# ---------------------------------------------------------------------------
# get_consul_addr — same pattern
# ---------------------------------------------------------------------------


class TestConsulAddrDiscovery:
    def test_env_var_priority(self, monkeypatch, config_dir):
        _write_config(config_dir, 'CONSUL_ADDR="http://100.64.0.1:8500"\n')
        monkeypatch.setenv("CONSUL_ADDR", "http://env-consul:8500")
        assert get_consul_addr() == "http://env-consul:8500"

    def test_reads_from_config(self, config_dir):
        _write_config(config_dir, 'CONSUL_ADDR="http://100.64.0.1:8500"\n')
        assert get_consul_addr() == "http://100.64.0.1:8500"

    def test_default_fallback(self, config_dir):
        assert get_consul_addr() == "http://localhost:8500"

    def test_config_missing_consul_key(self, config_dir):
        _write_config(config_dir, 'NOMAD_ADDR="http://1.2.3.4:4646"\n')
        assert get_consul_addr_from_config() is None
        assert get_consul_addr() == "http://localhost:8500"


# ---------------------------------------------------------------------------
# _parse_config_value — edge cases
# ---------------------------------------------------------------------------


class TestParseConfigValueEdgeCases:
    def test_nonexistent_file_returns_none(self, tmp_path):
        assert _parse_config_value(str(tmp_path / "nope"), "KEY") is None

    def test_unreadable_file_returns_none(self, tmp_path):
        f = tmp_path / "secret"
        f.write_text("KEY=val")
        os.chmod(str(f), 0o000)
        assert _parse_config_value(str(f), "KEY") is None

    def test_line_without_equals_skipped(self, config_dir):
        _write_config(config_dir, "NOTAVALIDLINE\nNOMAD_ADDR=http://x:4646\n")
        assert get_nomad_addr() == "http://x:4646"

    def test_empty_lines_skipped(self, config_dir):
        _write_config(
            config_dir, "\n\nNOMAD_ADDR=http://x:4646\n\n"
        )
        assert get_nomad_addr() == "http://x:4646"


# ---------------------------------------------------------------------------
# Return type contract
# ---------------------------------------------------------------------------


class TestReturnTypeContract:
    def test_get_nomad_addr_returns_str(self, config_dir):
        result = get_nomad_addr()
        assert isinstance(result, str)

    def test_get_consul_addr_returns_str(self, config_dir):
        result = get_consul_addr()
        assert isinstance(result, str)

    def test_get_nomad_addr_from_config_returns_optional(self, config_dir):
        result = get_nomad_addr_from_config()
        assert result is None or isinstance(result, str)
