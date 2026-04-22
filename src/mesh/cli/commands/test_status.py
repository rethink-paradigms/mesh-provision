"""
Tests for mesh status command.
"""

from unittest.mock import patch
from typer.testing import CliRunner

from mesh.cli.main import app

runner = CliRunner()


class TestStatusNoCluster:
    @patch("mesh.cli.commands.status._get_live_status", return_value=(None, None))
    def test_no_cluster_shows_error(self, mock_get):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "No Mesh cluster found" in result.output
        assert "NOMAD_ADDR" in result.output

    @patch("mesh.cli.commands.status._get_live_status", return_value=(None, None))
    def test_no_cluster_with_comparison(self, mock_get):
        result = runner.invoke(app, ["status", "--compare"])
        assert result.exit_code == 0
        assert "No Mesh cluster found" in result.output

    @patch("mesh.cli.commands.status._get_live_status", return_value=(None, None))
    def test_no_cluster_with_roadmap(self, mock_get):
        result = runner.invoke(app, ["status", "--roadmap"])
        assert result.exit_code == 0
        assert "No Mesh cluster found" in result.output


class TestStatusDemoMode:
    @patch("mesh.cli.commands.status._get_live_status", return_value=(None, None))
    def test_demo_mode_shows_mock_data(self, mock_get):
        result = runner.invoke(app, ["status", "--demo"])
        assert result.exit_code == 0
        assert "No Mesh cluster found" not in result.output
        assert "mesh-leader" in result.output
        assert "mesh-worker-1" in result.output
        assert "web-api" in result.output


class TestStatusWithCluster:
    @patch(
        "mesh.cli.commands.status._get_live_status",
        return_value=(
            [
                {
                    "name": "live-node-1",
                    "role": "server",
                    "status": "running",
                    "ip": "10.0.0.1",
                    "memory": "2048 MB",
                    "cpu": "2000 MHz",
                }
            ],
            [
                {
                    "name": "live-app",
                    "image": "nginx:latest",
                    "node": "live-node-1",
                    "status": "running",
                    "memory": "256 MB",
                    "uptime": "1h",
                }
            ],
        ),
    )
    def test_shows_live_cluster_data(self, mock_get):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "live-node-1" in result.output
        assert "live-app" in result.output
        assert "No Mesh cluster found" not in result.output
