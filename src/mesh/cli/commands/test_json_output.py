"""Tests for BRIEF-compliant JSON output transformation."""

import pytest

from mesh.cli.commands.json_output import to_brief_destroy_shape, to_brief_shape


class TestToBriefShape:
    """Pure-function tests for to_brief_shape()."""

    def test_to_brief_shape_happy_path(self):
        """Rich dict with leader + 1 worker → flat shape with 2 nodes."""
        result = {
            "cluster_id": "my-cluster",
            "provider": "digitalocean",
            "region": "nyc3",
            "tier": "standard",
            "leader": {
                "ip": "10.0.0.1",
                "id": "leader-01",
                "size": "s-2vcpu-4gb",
            },
            "workers": [
                {
                    "ip": "10.0.0.2",
                    "id": "worker-01",
                    "size": "s-1vcpu-1gb",
                },
            ],
        }
        brief = to_brief_shape(result)
        assert brief["cluster_id"] == "my-cluster"
        assert brief["leader_ip"] == "10.0.0.1"
        assert brief["status"] == "ready"
        assert len(brief["nodes"]) == 2
        assert brief["nodes"][0] == {"id": "leader-01", "ip": "10.0.0.1", "role": "leader"}
        assert brief["nodes"][1] == {"id": "worker-01", "ip": "10.0.0.2", "role": "worker"}

    def test_to_brief_shape_empty_ips(self):
        """Leader with empty ip → leader_ip='', nodes still has leader entry."""
        result = {
            "cluster_id": "empty-cluster",
            "leader": {
                "ip": "",
                "id": "leader-empty",
                "size": "s-2vcpu-4gb",
            },
            "workers": [],
        }
        brief = to_brief_shape(result)
        assert brief["leader_ip"] == ""
        assert len(brief["nodes"]) == 1
        assert brief["nodes"][0]["ip"] == ""

    def test_to_brief_shape_zero_workers(self):
        """workers=[] → nodes array has exactly 1 entry (leader only)."""
        result = {
            "cluster_id": "solo-cluster",
            "leader": {
                "ip": "10.0.0.1",
                "id": "leader-solo",
                "size": "s-2vcpu-4gb",
            },
            "workers": [],
        }
        brief = to_brief_shape(result)
        assert len(brief["nodes"]) == 1
        assert brief["nodes"][0]["role"] == "leader"

    def test_to_brief_shape_three_workers(self):
        """3 workers → nodes array has 4 entries (1 leader + 3 workers)."""
        result = {
            "cluster_id": "big-cluster",
            "leader": {
                "ip": "10.0.0.1",
                "id": "leader-big",
                "size": "s-2vcpu-4gb",
            },
            "workers": [
                {"ip": "10.0.0.2", "id": "worker-1", "size": "s-1vcpu-1gb"},
                {"ip": "10.0.0.3", "id": "worker-2", "size": "s-1vcpu-1gb"},
                {"ip": "10.0.0.4", "id": "worker-3", "size": "s-1vcpu-1gb"},
            ],
        }
        brief = to_brief_shape(result)
        assert len(brief["nodes"]) == 4
        assert brief["nodes"][0]["role"] == "leader"
        assert brief["nodes"][1]["role"] == "worker"
        assert brief["nodes"][2]["role"] == "worker"
        assert brief["nodes"][3]["role"] == "worker"

    def test_to_brief_shape_cluster_id_preserved(self):
        """cluster_id is passed through unchanged."""
        result = {
            "cluster_id": "exact-match-cluster",
            "leader": {
                "ip": "10.0.0.1",
                "id": "leader-exact",
                "size": "s-2vcpu-4gb",
            },
            "workers": [],
        }
        brief = to_brief_shape(result)
        assert brief["cluster_id"] == "exact-match-cluster"


class TestToBriefDestroyShape:
    """Pure-function tests for to_brief_destroy_shape()."""

    def test_with_resources(self):
        """Realistic result with 3 resources_cleaned → flat shape."""
        result = {
            "cluster_name": "prod-cluster",
            "destroyed": True,
            "resources_cleaned": ["droplet-abc123", "droplet-def456", "droplet-ghi789"],
        }
        brief = to_brief_destroy_shape(result, "prod-cluster")
        assert brief["cluster_id"] == "prod-cluster"
        assert brief["status"] == "destroyed"
        assert brief["destroyed"] is True
        assert len(brief["resources_cleaned"]) == 3
        assert "droplet-abc123" in brief["resources_cleaned"]

    def test_empty_resources(self):
        """Empty resources_cleaned → resources_cleaned=[], still destroyed=True."""
        result = {
            "cluster_name": "empty-cluster",
            "destroyed": True,
            "resources_cleaned": [],
        }
        brief = to_brief_destroy_shape(result, "empty-cluster")
        assert brief["cluster_id"] == "empty-cluster"
        assert brief["status"] == "destroyed"
        assert brief["destroyed"] is True
        assert brief["resources_cleaned"] == []

    def test_destroyed_always_true(self):
        """destroyed field is always True regardless of input."""
        result = {
            "cluster_name": "whatever",
            "destroyed": False,
            "resources_cleaned": [],
        }
        brief = to_brief_destroy_shape(result, "whatever")
        assert brief["destroyed"] is True
