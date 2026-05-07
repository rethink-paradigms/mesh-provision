"""Tests for post-provision health check polling in run_init_json()."""

from unittest.mock import Mock, patch

from mesh.cli.commands.init_json import _poll_health, run_init_json


# ---------------------------------------------------------------------------
# Test 1: Health check succeeds — returns "ready"
# ---------------------------------------------------------------------------


@patch("mesh.cli.commands.init_json.print_json_success")
@patch("mesh.cli.commands.init_json.print_json_error")
@patch("mesh.cli.commands.init_json.provision_cluster_direct")
@patch("mesh.cli.commands.init_json._poll_health")
def test_health_check_success(mock_poll, mock_provision, mock_error, mock_success):
    mock_provision.return_value = {
        "leader": {
            "public_ip": "1.2.3.4",
            "private_ip": "10.0.0.1",
            "instance_id": "droplet-1",
        },
        "workers": [],
    }
    mock_poll.return_value = "ready"

    run_init_json(
        provider="digitalocean",
        region="nyc3",
        workers=0,
        leader_size="s-2vcpu-4gb",
        worker_size="s-1vcpu-1gb",
        cluster_name="test-cluster",
        api_key="test-key",
        daemon_token="dtok",
        daemon_url="https://daemon.test.com",
    )

    mock_success.assert_called_once()
    args = mock_success.call_args[0][0]
    assert args["status"] == "ready"


# ---------------------------------------------------------------------------
# Test 2: Health check fails — returns "provisioned"
# ---------------------------------------------------------------------------


@patch("mesh.cli.commands.init_json.print_json_success")
@patch("mesh.cli.commands.init_json.print_json_error")
@patch("mesh.cli.commands.init_json.provision_cluster_direct")
@patch("mesh.cli.commands.init_json._poll_health")
def test_health_check_failure(mock_poll, mock_provision, mock_error, mock_success):
    mock_provision.return_value = {
        "leader": {
            "public_ip": "1.2.3.4",
            "private_ip": "10.0.0.1",
            "instance_id": "droplet-1",
        },
        "workers": [],
    }
    mock_poll.return_value = "provisioned"

    run_init_json(
        provider="digitalocean",
        region="nyc3",
        workers=0,
        leader_size="s-2vcpu-4gb",
        worker_size="s-1vcpu-1gb",
        cluster_name="test-cluster",
        api_key="test-key",
        daemon_token="dtok",
        daemon_url="https://daemon.test.com",
    )

    mock_success.assert_called_once()
    args = mock_success.call_args[0][0]
    assert args["status"] == "provisioned"


# ---------------------------------------------------------------------------
# Test 3: No IP available — returns "provisioned" without polling
# ---------------------------------------------------------------------------


@patch("mesh.cli.commands.init_json.print_json_success")
@patch("mesh.cli.commands.init_json.print_json_error")
@patch("mesh.cli.commands.init_json.provision_cluster_direct")
@patch("mesh.cli.commands.init_json._poll_health")
def test_health_check_no_ip(mock_poll, mock_provision, mock_error, mock_success):
    mock_provision.return_value = {
        "leader": {
            "public_ip": "",
            "private_ip": "",
            "instance_id": "droplet-1",
        },
        "workers": [],
    }

    run_init_json(
        provider="digitalocean",
        region="nyc3",
        workers=0,
        leader_size="s-2vcpu-4gb",
        worker_size="s-1vcpu-1gb",
        cluster_name="test-cluster",
        api_key="test-key",
        daemon_token="dtok",
        daemon_url="https://daemon.test.com",
    )

    mock_success.assert_called_once()
    args = mock_success.call_args[0][0]
    assert args["status"] == "provisioned"
    mock_poll.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: Health check retries then succeeds
# ---------------------------------------------------------------------------


def test_health_check_retry_then_success():
    mock_get = Mock()
    mock_get.side_effect = [
        ConnectionError("connection refused"),
        ConnectionError("connection refused"),
        Mock(status_code=200),
    ]

    with patch("requests.get", mock_get), patch("time.sleep", return_value=None):
        result = _poll_health("1.2.3.4", timeout=15, interval=5)
        assert result == "ready"
        assert mock_get.call_count == 3
