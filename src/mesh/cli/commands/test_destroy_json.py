"""Tests for mesh destroy --output json CLI command."""

from unittest.mock import patch
from typer.testing import CliRunner

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
