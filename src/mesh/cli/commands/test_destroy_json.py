"""Tests for mesh destroy --output json CLI command."""

import io
import json
from unittest.mock import patch

from typer.testing import CliRunner

from mesh.cli.commands.init_json import run_init_json_from_stdin
from mesh.cli.main import app

runner = CliRunner()

DESTROY_ARGS = [
    "destroy", "--output", "json", "--demo",
    "--api-key", "test123",
    "--cluster", "test-brief",
]


class TestDestroyJsonDemo:
    @patch("mesh.cli.commands.json_output.print_json_success")
    @patch("mesh.cli.commands.json_output.print_json_error")
    def test_demo_produces_brief_shape(self, mock_error, mock_success):
        result = runner.invoke(app, DESTROY_ARGS)
        mock_success.assert_called_once()
        data = mock_success.call_args[0][0]
        assert data["status"] == "destroyed"
        assert data["destroyed"] is True
        assert data["cluster_id"] == "test-brief"

    @patch("mesh.cli.commands.json_output.print_json_success")
    @patch("mesh.cli.commands.json_output.print_json_error")
    def test_demo_exits_0(self, mock_error, mock_success):
        result = runner.invoke(app, DESTROY_ARGS)
        mock_success.assert_called_once()


class TestDestroyStdin:
    """Tests for mesh destroy via stdin JSON protocol."""

    @patch("mesh.cli.commands.json_output.print_json_success")
    @patch("mesh.cli.commands.json_output.print_json_error")
    @patch("mesh.infrastructure.provision_node.provision_direct.destroy_resources_direct")
    def test_destroy_stdin_success(self, mock_destroy, mock_error, mock_success):
        """Success path: valid stdin JSON produces correct destroy brief shape."""
        mock_destroy.return_value = {"resources_cleaned": ["droplet-1"]}
        stdin_data = json.dumps({
            "version": "1",
            "command": "destroy",
            "params": {
                "cluster_name": "test-cluster",
                "provider": "digitalocean",
                "api_key": "test123",
            }
        })
        with patch("sys.stdin", io.StringIO(stdin_data)):
            try:
                run_init_json_from_stdin()
            except SystemExit:
                pass
        mock_success.assert_called_once()
        data = mock_success.call_args[0][0]
        assert data["cluster_id"] == "test-cluster"
        assert data["status"] == "destroyed"
        assert data["destroyed"] is True

    @patch("mesh.cli.commands.json_output.print_json_success")
    @patch("mesh.cli.commands.json_output.print_json_error")
    def test_destroy_stdin_unsupported_provider(self, mock_error, mock_success):
        """Error path: unsupported provider (gcp) triggers print_json_error."""
        stdin_data = json.dumps({
            "version": "1",
            "command": "destroy",
            "params": {
                "cluster_name": "test-cluster",
                "provider": "gcp",
                "api_key": "test123",
            }
        })
        with patch("sys.stdin", io.StringIO(stdin_data)):
            try:
                run_init_json_from_stdin()
            except SystemExit:
                pass
        mock_error.assert_called_once()
        call_kwargs = mock_error.call_args[1]
        assert call_kwargs.get("code") == "unknown_provider"

    def test_destroy_stdin_unsupported_version(self):
        """Dispatch guard: unsupported version writes error to stderr."""
        stdin_data = json.dumps({
            "version": "2",
            "command": "destroy",
            "params": {"cluster_name": "test-cluster"}
        })
        mock_stderr = io.StringIO()
        with patch("sys.stdin", io.StringIO(stdin_data)):
            with patch("sys.stderr", mock_stderr):
                try:
                    run_init_json_from_stdin()
                except SystemExit:
                    pass
        output = mock_stderr.getvalue()
        assert "unsupported_version" in output
