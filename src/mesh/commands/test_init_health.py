"""Tests for post-provision health polling in handle_init()."""

from unittest.mock import Mock, patch

import pytest

from mesh.commands.init import _poll_health, handle_init


class TestPollHealth:
    def test_returns_ready_on_200(self):
        mock_resp = Mock(status_code=200)
        with patch("requests.get", return_value=mock_resp), \
             patch("time.sleep"):
            result = _poll_health("1.2.3.4", timeout=10, interval=5)
        assert result == "ready"

    def test_returns_provisioned_on_timeout(self):
        with patch("requests.get", side_effect=ConnectionError("refused")), \
             patch("time.sleep"):
            result = _poll_health("1.2.3.4", timeout=5, interval=5)
        assert result == "provisioned"

    def test_retries_then_succeeds(self):
        responses = [ConnectionError(), ConnectionError(), Mock(status_code=200)]
        with patch("requests.get", side_effect=responses), \
             patch("time.sleep"):
            result = _poll_health("1.2.3.4", timeout=15, interval=5)
        assert result == "ready"


class TestInitHealthIntegration:
    """handle_init propagates health poll result into output."""

    @patch("mesh.commands.init.provision_cluster")
    @patch("mesh.commands.init._poll_health", return_value="ready")
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
        import json
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "ready"

    @patch("mesh.commands.init.provision_cluster")
    @patch("mesh.commands.init._poll_health", return_value="provisioned")
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
        import json
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "provisioned"

    @patch("mesh.commands.init.provision_cluster")
    @patch("mesh.commands.init._poll_health")
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
