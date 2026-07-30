"""Tests for the add-worker command — stdin JSON protocol."""

import json
from unittest.mock import patch

import pytest

from mesh.commands.add_worker import handle_add_worker


class TestAddWorkerDemo:
    def test_demo_shape(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_add_worker({"demo": True})
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert "node" in out
        assert out["node"]["role"] == "worker"
        assert "ip" in out["node"]
        assert "id" in out["node"]


class TestAddWorkerValidation:
    def test_missing_required_params_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_add_worker({"cluster_name": "c"})  # missing most params
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "missing_required_args"

    def test_unknown_provider_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_add_worker({
                "provider": "azure", "region": "eastus", "cluster_name": "c",
                "worker_size": "Standard_B1s", "leader_ip": "1.2.3.4", "api_key": "k",
            })
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "unknown_provider"


class TestAddWorkerRealPath:
    @patch("mesh.commands.add_worker.provision_node")
    @patch("mesh.commands.add_worker.generate_cloud_init", return_value="#cloud-config\n{}")
    def test_successful_add_worker(self, mock_boot, mock_provision, capsys):
        mock_provision.return_value = {
            "public_ip": "9.9.9.9", "private_ip": "10.0.0.5",
            "instance_id": "worker-drop-99", "name": "c-worker-1234",
        }
        with pytest.raises(SystemExit) as exc:
            handle_add_worker({
                "provider": "digitalocean", "region": "nyc3",
                "cluster_name": "c", "worker_size": "s-1vcpu-1gb",
                "leader_ip": "1.2.3.4", "api_key": "dop_v1_test",
            })
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["node"]["ip"] == "9.9.9.9"
        assert out["node"]["id"] == "worker-drop-99"
        assert out["node"]["role"] == "worker"

    @patch("mesh.commands.add_worker.provision_node", side_effect=RuntimeError("limit reached"))
    @patch("mesh.commands.add_worker.generate_cloud_init", return_value="#cloud-config\n{}")
    def test_provision_failure_returns_error(self, mock_boot, mock_provision, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_add_worker({
                "provider": "digitalocean", "region": "nyc3",
                "cluster_name": "c", "worker_size": "s-1vcpu-1gb",
                "leader_ip": "1.2.3.4", "api_key": "k",
            })
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "provision_failed"
