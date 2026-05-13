"""Tests for the destroy command — stdin JSON protocol."""

import json
from unittest.mock import patch

import pytest

from mesh.commands.destroy import handle_destroy


class TestDestroyDemo:
    def test_demo_shape(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_destroy({"demo": True, "cluster_name": "my-cluster"})
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["cluster_id"] == "my-cluster"
        assert out["status"] == "destroyed"
        assert out["destroyed"] is True


class TestDestroyValidation:
    def test_missing_cluster_name_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_destroy({"provider": "digitalocean", "api_key": "k"})
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "missing_required_args"
        assert "cluster_name" in err["error"]["missing_args"]

    def test_unknown_provider_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_destroy({"cluster_name": "c", "provider": "gcp", "api_key": "k"})
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "unknown_provider"


class TestDestroyRealPath:
    @patch("mesh.commands.destroy.destroy_cluster")
    def test_successful_destroy(self, mock_destroy, capsys):
        mock_destroy.return_value = {"cluster_name": "c", "destroyed": True, "resources_cleaned": ["id-1"]}
        with pytest.raises(SystemExit) as exc:
            handle_destroy({
                "cluster_name": "c", "provider": "digitalocean", "api_key": "dop_v1_test",
            })
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["cluster_id"] == "c"
        assert out["destroyed"] is True
        assert "id-1" in out["resources_cleaned"]

    @patch("mesh.commands.destroy.destroy_cluster", side_effect=RuntimeError("not found"))
    def test_destroy_failure_returns_error(self, mock_destroy, capsys):
        with pytest.raises(SystemExit) as exc:
            handle_destroy({
                "cluster_name": "c", "provider": "digitalocean", "api_key": "k",
            })
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "provision_failed"
