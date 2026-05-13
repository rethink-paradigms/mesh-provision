"""Tests for the status command — stdin JSON protocol."""

import json
from unittest.mock import patch

import pytest

from mesh.commands.status import handle_status


class TestStatusValidation:
    def test_missing_provider_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_status({"cluster_name": "c", "api_key": "k"})
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "missing_required_args"
        assert "provider" in err["error"]["missing_args"]

    def test_missing_cluster_name_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_status({"provider": "digitalocean", "api_key": "k"})
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert "cluster_name" in err["error"]["missing_args"]

    def test_unknown_provider_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_status({"provider": "gcp", "cluster_name": "c", "api_key": "k"})
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "unknown_provider"


class TestStatusRealPath:
    @patch("mesh.commands.status.query_cluster")
    def test_cluster_exists(self, mock_query, capsys):
        mock_query.return_value = {
            "cluster_name": "my-cluster",
            "exists": True,
            "nodes": [{"id": "123", "ip": "1.2.3.4", "role": "leader"}],
        }
        with pytest.raises(SystemExit) as exc:
            handle_status({"provider": "digitalocean", "cluster_name": "my-cluster", "api_key": "k"})
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["cluster_name"] == "my-cluster"
        assert out["exists"] is True
        assert len(out["nodes"]) == 1

    @patch("mesh.commands.status.query_cluster")
    def test_cluster_not_found(self, mock_query, capsys):
        mock_query.return_value = {"cluster_name": "c", "exists": False, "nodes": []}
        with pytest.raises(SystemExit) as exc:
            handle_status({"provider": "digitalocean", "cluster_name": "c", "api_key": "k"})
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["exists"] is False
        assert out["nodes"] == []

    @patch("mesh.commands.status.query_cluster", side_effect=RuntimeError("auth failed"))
    def test_query_failure_returns_error(self, mock_query, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_status({"provider": "digitalocean", "cluster_name": "c", "api_key": "k"})
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "status_failed"
