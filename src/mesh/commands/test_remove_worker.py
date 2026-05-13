"""Tests for the remove-worker command."""

from unittest.mock import MagicMock, patch
import pytest
from mesh.commands.remove_worker import handle_remove_worker


def make_node(node_id, name):
    n = MagicMock()
    n.id = node_id
    n.name = name
    n.public_ips = ["10.0.0.5"]
    n.private_ips = []
    return n


def run(params, capsys):
    with pytest.raises(SystemExit) as exc:
        handle_remove_worker(params)
    assert exc.value.code == 0
    import json
    return json.loads(capsys.readouterr().out)


def run_err(params, capsys):
    with pytest.raises(SystemExit) as exc:
        handle_remove_worker(params)
    assert exc.value.code == 1
    import json
    return json.loads(capsys.readouterr().err)


def test_remove_worker_by_node_id(capsys):
    worker = make_node("w-123", "my-cluster-worker-1747000000")

    with patch("mesh.provisioning.direct._get_driver") as mock_driver_factory:
        drv = MagicMock()
        drv.list_nodes.return_value = [worker]
        mock_driver_factory.return_value = drv

        result = run({
            "provider": "digitalocean",
            "cluster_name": "my-cluster",
            "api_key": "dop_v1_key",
            "node_id": "w-123",
        }, capsys)

    assert result["removed"] is True
    assert result["node_id"] == "w-123"
    assert result["node_name"] == "my-cluster-worker-1747000000"
    drv.destroy_node.assert_called_once_with(worker)


def test_remove_worker_by_node_name(capsys):
    worker = make_node("w-456", "my-cluster-worker-1747000001")

    with patch("mesh.provisioning.direct._get_driver") as mock_driver_factory:
        drv = MagicMock()
        drv.list_nodes.return_value = [worker]
        mock_driver_factory.return_value = drv

        result = run({
            "provider": "digitalocean",
            "cluster_name": "my-cluster",
            "api_key": "dop_v1_key",
            "node_name": "my-cluster-worker-1747000001",
        }, capsys)

    assert result["removed"] is True
    assert result["node_name"] == "my-cluster-worker-1747000001"


def test_remove_worker_refuses_leader(capsys):
    leader = make_node("l-001", "my-cluster-leader")

    with patch("mesh.provisioning.direct._get_driver") as mock_driver_factory:
        drv = MagicMock()
        drv.list_nodes.return_value = [leader]
        mock_driver_factory.return_value = drv

        err = run_err({
            "provider": "digitalocean",
            "cluster_name": "my-cluster",
            "api_key": "dop_v1_key",
            "node_id": "l-001",
        }, capsys)

    assert err["error"]["code"] == "provision_failed"
    assert "not a worker" in err["error"]["message"]
    drv.destroy_node.assert_not_called()


def test_remove_worker_refuses_other_cluster(capsys):
    other = make_node("x-001", "other-cluster-worker-111")

    with patch("mesh.provisioning.direct._get_driver") as mock_driver_factory:
        drv = MagicMock()
        drv.list_nodes.return_value = [other]
        mock_driver_factory.return_value = drv

        err = run_err({
            "provider": "digitalocean",
            "cluster_name": "my-cluster",
            "api_key": "dop_v1_key",
            "node_id": "x-001",
        }, capsys)

    assert err["error"]["code"] == "provision_failed"
    assert "not a worker" in err["error"]["message"]
    drv.destroy_node.assert_not_called()


def test_remove_worker_node_not_found(capsys):
    with patch("mesh.provisioning.direct._get_driver") as mock_driver_factory:
        drv = MagicMock()
        drv.list_nodes.return_value = []
        mock_driver_factory.return_value = drv

        err = run_err({
            "provider": "digitalocean",
            "cluster_name": "my-cluster",
            "api_key": "dop_v1_key",
            "node_id": "does-not-exist",
        }, capsys)

    assert err["error"]["code"] == "provision_failed"
    assert "not found" in err["error"]["message"]


def test_remove_worker_missing_node_identifier(capsys):
    err = run_err({
        "provider": "digitalocean",
        "cluster_name": "my-cluster",
        "api_key": "dop_v1_key",
        # no node_id, no node_name
    }, capsys)
    assert err["error"]["code"] == "missing_required_args"


def test_remove_worker_demo(capsys):
    result = run({"demo": True}, capsys)
    assert result["removed"] is True
    assert "node_id" in result
    assert "node_name" in result
