"""Tests for post-provision health polling in handle_init()."""

import json
from unittest.mock import patch

import pytest

from mesh.commands.init import handle_init


class TestInitHealthIntegration:
    """handle_init propagates health poll result into output."""

    @patch("mesh.commands.init.provision_cluster")
    @patch("mesh.commands.init.poll_daemon_health", return_value=True)
    @patch("mesh.commands.init.generate_cloud_init", return_value="#cloud-config\n{}")
    def test_ready_status_in_output(self, mock_boot, mock_poll, mock_cluster, capsys):
        mock_cluster.return_value = {
            "leader": {"public_ip": "1.2.3.4", "private_ip": None, "instance_id": "x"},
            "workers": [],
        }
        with pytest.raises(SystemExit) as exc:
            handle_init({
                "provider": "digitalocean", "region": "nyc3",
                "cluster_name": "c", "leader_size": "s-2vcpu-4gb", "api_key": "k",
            })
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "ready"

    @patch("mesh.commands.init.provision_cluster")
    @patch("mesh.commands.init.poll_daemon_health", return_value=False)
    @patch("mesh.commands.init.generate_cloud_init", return_value="#cloud-config\n{}")
    def test_provisioned_status_in_output(self, mock_boot, mock_poll, mock_cluster, capsys):
        mock_cluster.return_value = {
            "leader": {"public_ip": "1.2.3.4", "private_ip": None, "instance_id": "x"},
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

    @patch("mesh.commands.init.provision_cluster")
    @patch("mesh.commands.init.poll_daemon_health")
    @patch("mesh.commands.init.generate_cloud_init", return_value="#cloud-config\n{}")
    def test_no_ip_skips_poll(self, mock_boot, mock_poll, mock_cluster, capsys):
        mock_cluster.return_value = {
            "leader": {"public_ip": "", "private_ip": "", "instance_id": "x"},
            "workers": [],
        }
        with pytest.raises(SystemExit):
            handle_init({
                "provider": "digitalocean", "region": "nyc3",
                "cluster_name": "c", "leader_size": "s-2vcpu-4gb", "api_key": "k",
            })
        mock_poll.assert_not_called()
