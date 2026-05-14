"""Tests for the init command — stdin JSON protocol."""

import json
import io
import sys
from unittest.mock import patch, MagicMock

import pytest

from mesh.commands.init import handle_init
from mesh.commands.output import demo_init


class TestInitDemo:
    """Demo mode — no cloud calls, fast, validates output shape."""

    def test_demo_produces_correct_shape(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_init({"demo": True, "cluster_name": "test", "provider": "digitalocean",
                         "region": "nyc3", "workers": 0, "leader_size": "s-2vcpu-4gb"})
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["cluster_id"] == "test"
        assert "leader_ip" in out
        assert "status" in out
        assert isinstance(out["nodes"], list)
        assert out["nodes"][0]["role"] == "leader"

    def test_demo_lite_has_no_workers(self, capsys):
        with pytest.raises(SystemExit):
            handle_init({"demo": True, "cluster_name": "c", "workers": 0})
        out = json.loads(capsys.readouterr().out)
        assert all(n["role"] == "leader" for n in out["nodes"])

    def test_demo_standard_has_workers(self, capsys):
        with pytest.raises(SystemExit):
            handle_init({"demo": True, "cluster_name": "c", "workers": 2})
        out = json.loads(capsys.readouterr().out)
        roles = [n["role"] for n in out["nodes"]]
        assert roles.count("leader") == 1
        assert roles.count("worker") == 2


class TestInitValidation:
    """Missing required params → error response."""

    def test_missing_provider_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_init({"region": "nyc3", "cluster_name": "c",
                         "leader_size": "s-2vcpu-4gb", "api_key": "k"})
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "missing_required_args"
        assert "provider" in err["error"]["missing_args"]

    def test_unknown_provider_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_init({"provider": "gcp", "region": "us-east1",
                         "cluster_name": "c", "leader_size": "e2-medium", "api_key": "k"})
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "unknown_provider"


class TestInitRealPath:
    """Real provisioning path with mocked cloud calls."""

    @patch("mesh.commands.init.provision_cluster")
    @patch("mesh.commands.init.poll_daemon_health", return_value=True)
    @patch("mesh.commands.init.generate_cloud_init", return_value="#cloud-config\n{}")
    def test_successful_provision(self, mock_boot, mock_poll, mock_cluster, capsys):
        mock_cluster.return_value = {
            "leader": {"public_ip": "1.2.3.4", "private_ip": "10.0.0.1", "instance_id": "drop-1"},
            "workers": [],
        }
        with pytest.raises(SystemExit) as exc:
            handle_init({
                "provider": "digitalocean", "region": "nyc3",
                "cluster_name": "my-cluster", "leader_size": "s-2vcpu-4gb",
                "api_key": "dop_v1_test",
            })
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["cluster_id"] == "my-cluster"
        assert out["leader_ip"] == "1.2.3.4"
        assert out["status"] == "ready"
        assert out["nodes"][0] == {"id": "drop-1", "ip": "1.2.3.4", "role": "leader"}

    @patch("mesh.commands.init.provision_cluster", side_effect=RuntimeError("quota exceeded"))
    @patch("mesh.commands.init.generate_cloud_init", return_value="#cloud-config\n{}")
    def test_provision_failure_returns_error(self, mock_boot, mock_cluster, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_init({
                "provider": "digitalocean", "region": "nyc3",
                "cluster_name": "c", "leader_size": "s-2vcpu-4gb", "api_key": "k",
            })
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "provision_failed"
        assert "quota exceeded" in err["error"]["message"]

    @patch("mesh.commands.init.provision_cluster")
    @patch("mesh.commands.init.poll_daemon_health", return_value=False)
    @patch("mesh.commands.init.generate_cloud_init", return_value="#cloud-config\n{}")
    def test_health_timeout_returns_provisioned(self, mock_boot, mock_poll, mock_cluster, capsys):
        mock_cluster.return_value = {
            "leader": {"public_ip": "5.5.5.5", "private_ip": None, "instance_id": "x"},
            "workers": [],
        }
        with pytest.raises(SystemExit) as exc:
            handle_init({
                "provider": "digitalocean", "region": "nyc3",
                "cluster_name": "c", "leader_size": "s-2vcpu-4gb", "api_key": "k",
            })
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "provisioned"
