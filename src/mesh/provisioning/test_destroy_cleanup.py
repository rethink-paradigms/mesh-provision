"""Tests for cleanup_all destroy functionality (G9).

Verifies the cleanup_all parameter of destroy_cluster().
Tests cover: no cleanup, with cleanup, empty cluster, unsupported
provider, and resilience to partial failures.
"""

from unittest.mock import Mock, patch, MagicMock

import pytest

from mesh.provisioning.direct import destroy_cluster


@pytest.fixture
def mock_do_driver():
    """Create a mock DigitalOcean driver with all auxiliary methods."""
    driver = Mock()
    # Default: no nodes
    driver.list_nodes.return_value = []
    # Default: no extra resources
    driver.ex_list_volumes.return_value = []
    driver.ex_list_firewalls.return_value = []
    driver.ex_list_floating_ips.return_value = []
    driver.ex_list_ssh_keys.return_value = []
    # Destroy methods
    driver.destroy_node = Mock()
    driver.ex_destroy_volume = Mock()
    driver.ex_delete_firewall = Mock()
    driver.ex_release_floating_ip = Mock()
    driver.ex_delete_ssh_key = Mock()
    return driver


def make_node(node_id: str, name: str, ip: str = "10.0.0.1"):
    """Create a minimal mock Libcloud node."""
    n = MagicMock()
    n.id = node_id
    n.name = name
    n.public_ips = [ip]
    n.private_ips = []
    return n


def test_destroy_no_cleanup(mock_do_driver):
    """Verify cleanup_all=False destroys nodes but not auxiliary resources."""
    mock_do_driver.list_nodes.return_value = [
        make_node("node-1", "test-cluster-leader"),
    ]

    with patch(
        "mesh.provisioning.direct._get_driver",
        return_value=mock_do_driver,
    ):
        result = destroy_cluster(
            "digitalocean", "dop_v1_key", "nyc3", "test-cluster",
            cleanup_all=False,
        )

    # Node should be destroyed
    mock_do_driver.destroy_node.assert_called_once()
    assert result["destroyed"] is True
    assert "node-1" in result["resources_cleaned"]

    # Auxiliary methods should NOT be called
    mock_do_driver.ex_destroy_volume.assert_not_called()
    mock_do_driver.ex_delete_firewall.assert_not_called()
    mock_do_driver.ex_release_floating_ip.assert_not_called()
    mock_do_driver.ex_delete_ssh_key.assert_not_called()


def test_destroy_with_cleanup(mock_do_driver):
    """Verify cleanup_all=True cleans auxiliary resources then nodes."""
    vol = MagicMock()
    vol.id = "vol-abc123"
    mock_do_driver.ex_list_volumes.return_value = [vol]
    mock_do_driver.list_nodes.return_value = [
        make_node("node-1", "test-cluster-leader"),
    ]

    manager = Mock()
    manager.attach_mock(mock_do_driver.ex_destroy_volume, "destroy_vol")
    manager.attach_mock(mock_do_driver.destroy_node, "destroy_node")

    with patch(
        "mesh.provisioning.direct._get_driver",
        return_value=mock_do_driver,
    ):
        result = destroy_cluster(
            "digitalocean", "dop_v1_key", "nyc3", "test-cluster",
            cleanup_all=True,
        )

    # Both volume and node should be destroyed
    mock_do_driver.ex_destroy_volume.assert_called_once()
    mock_do_driver.destroy_node.assert_called_once()

    # Volume destroyed BEFORE node
    calls = manager.mock_calls
    vol_idx = next(i for i, c in enumerate(calls) if "destroy_vol" in str(c))
    node_idx = next(i for i, c in enumerate(calls) if "destroy_node" in str(c))
    assert vol_idx < node_idx, "Auxiliary resources should be cleaned before nodes"

    assert "volume:vol-abc123" in result["resources_cleaned"]
    assert "node-1" in result["resources_cleaned"]
    assert result["destroyed"] is True


def test_destroy_cleanup_empty_cluster(mock_do_driver):
    """Verify cleanup_all=True succeeds gracefully on an empty cluster."""
    # No nodes, no resources (both already default to [])
    with patch(
        "mesh.provisioning.direct._get_driver",
        return_value=mock_do_driver,
    ):
        result = destroy_cluster(
            "digitalocean", "dop_v1_key", "nyc3", "test-cluster",
            cleanup_all=True,
        )

    assert result["destroyed"] is True
    assert result["resources_cleaned"] == []


def test_destroy_cleanup_unsupported_provider():
    """Verify cleanup_all=True on non-DO provider raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="cleanup_all"):
        destroy_cluster(
            "aws", "key", "us-east-1", "test-cluster",
            cleanup_all=True,
        )


def test_destroy_cleanup_resilience_volume_failure(mock_do_driver):
    """Verify partial failure in volume cleanup doesn't prevent node cleanup."""
    vol = MagicMock()
    vol.id = "vol-fail"
    mock_do_driver.ex_list_volumes.return_value = [vol]
    mock_do_driver.ex_destroy_volume.side_effect = RuntimeError("API error")
    mock_do_driver.list_nodes.return_value = [
        make_node("node-1", "test-cluster-leader"),
    ]

    with patch(
        "mesh.provisioning.direct._get_driver",
        return_value=mock_do_driver,
    ):
        result = destroy_cluster(
            "digitalocean", "dop_v1_key", "nyc3", "test-cluster",
            cleanup_all=True,
        )

    # Volume cleanup failed but node should still be destroyed
    mock_do_driver.destroy_node.assert_called_once()
    assert result["destroyed"] is True
    assert "node-1" in result["resources_cleaned"]


def test_destroy_cleanup_all_resources(mock_do_driver):
    """Verify cleanup_all=True cleans all four auxiliary resource types."""
    vol = MagicMock()
    vol.id = "vol-1"
    fw = MagicMock()
    fw.id = "fw-1"
    fip = MagicMock()
    fip.id = "fip-1"
    key = MagicMock()
    key.id = "key-1"

    mock_do_driver.ex_list_volumes.return_value = [vol]
    mock_do_driver.ex_list_firewalls.return_value = [fw]
    mock_do_driver.ex_list_floating_ips.return_value = [fip]
    mock_do_driver.ex_list_ssh_keys.return_value = [key]
    mock_do_driver.list_nodes.return_value = [
        make_node("node-1", "test-cluster-leader"),
    ]

    with patch(
        "mesh.provisioning.direct._get_driver",
        return_value=mock_do_driver,
    ):
        result = destroy_cluster(
            "digitalocean", "dop_v1_key", "nyc3", "test-cluster",
            cleanup_all=True,
        )

    mock_do_driver.ex_destroy_volume.assert_called_once()
    mock_do_driver.ex_delete_firewall.assert_called_once()
    # Floating IPs not explicitly released — no names, cannot be cluster-filtered safely
    mock_do_driver.ex_release_floating_ip.assert_not_called()
    mock_do_driver.ex_delete_ssh_key.assert_called_once()
    mock_do_driver.destroy_node.assert_called_once()
    assert "volume:vol-1" in result["resources_cleaned"]
    assert "firewall:fw-1" in result["resources_cleaned"]
    # floating_ip not in resources_cleaned — not explicitly released (droplet lifecycle)
    assert "floating_ip:fip-1" not in result["resources_cleaned"]
    assert "ssh_key:key-1" in result["resources_cleaned"]
    assert "node-1" in result["resources_cleaned"]
    assert result["destroyed"] is True
