"""Tests for mesh init --output json CLI command."""

from unittest.mock import patch
from typer.testing import CliRunner

from mesh.cli.main import app
from mesh.cli.commands.init_json import run_init_json

runner = CliRunner()

INIT_ARGS = [
    "init", "--output", "json", "--demo",
    "--api-key", "test123",
    "--leader-size", "s-2vcpu-4gb",
    "--cluster-name", "test-regr",
    "--region", "nyc3",
]


class TestInitJsonDemo:
    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    def test_demo_produces_brief_shape(self, mock_error, mock_success):
        """Full demo invocation should produce flat brief shape."""
        result = runner.invoke(app, INIT_ARGS)
        mock_success.assert_called_once()
        data = mock_success.call_args[0][0]
        assert "cluster_id" in data
        assert "leader_ip" in data
        assert "status" in data
        assert "nodes" in data

    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    def test_demo_exits_0(self, mock_error, mock_success):
        """Full demo invocation should succeed (mock prevents sys.exit)."""
        result = runner.invoke(app, INIT_ARGS)
        mock_success.assert_called_once()

    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    def test_demo_leader_ip_present(self, mock_error, mock_success):
        """Brief shape must include a non-empty leader_ip."""
        result = runner.invoke(app, INIT_ARGS)
        mock_success.assert_called_once()
        data = mock_success.call_args[0][0]
        assert "leader_ip" in data
        assert isinstance(data["leader_ip"], str)
        assert data["leader_ip"] != ""

    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    def test_demo_nodes_has_leader_role(self, mock_error, mock_success):
        """Nodes array must have at least 1 entry with role=leader."""
        result = runner.invoke(app, INIT_ARGS)
        mock_success.assert_called_once()
        data = mock_success.call_args[0][0]
        assert isinstance(data["nodes"], list)
        assert len(data["nodes"]) >= 1
        assert data["nodes"][0]["role"] == "leader"

    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    def test_demo_no_rich_output(self, mock_error, mock_success):
        """Rich-formatted text should not appear in stdout for JSON mode."""
        result = runner.invoke(app, INIT_ARGS)
        mock_success.assert_called_once()
        assert "Cluster Configuration" not in result.stdout
        assert "Initialize" not in result.stdout


class TestInitJsonErrors:
    @patch("mesh.cli.commands.json_output.print_json_error")
    def test_missing_args_produces_error(self, mock_error):
        """Missing required args in non-demo JSON mode should call print_json_error."""
        result = runner.invoke(app, [
            "init", "--output", "json",
        ])
        mock_error.assert_called_once()
        call_kwargs = mock_error.call_args[1]
        assert call_kwargs.get("code") == "missing_required_args"


class TestInitJsonFullFlow:
    """Integration tests for run_init_json full flow (brief shape output)."""

    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    def test_full_flow_demo(self, mock_error, mock_success):
        """Full demo path should produce flat BRIEF shape with no rich fields."""
        run_init_json(
            provider="digitalocean", region="nyc3", workers=0,
            leader_size="s-2vcpu-4gb", worker_size="s-1vcpu-1gb",
            cluster_name="demo-cluster", api_key="test-key",
            demo=True,
        )
        mock_success.assert_called_once()
        brief = mock_success.call_args[0][0]
        assert brief["cluster_id"] == "demo-cluster"
        assert brief["status"] == "ready"
        assert "leader_ip" in brief
        assert "nodes" in brief
        assert len(brief["nodes"]) >= 1
        assert brief["nodes"][0]["role"] == "leader"
        # CRITICAL: Rich fields must NOT leak
        for field in ("provider", "region", "tier", "nomad_addr",
                       "caddy_admin"):
            assert field not in brief, f"Rich field '{field}' leaked into flat shape"

    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    @patch("mesh.cli.commands.init_json.provision_cluster_direct")
    @patch("mesh.cli.commands.init_json._poll_health")
    def test_full_flow_real_mocked(
        self, mock_poll, mock_provision, mock_error, mock_success
    ):
        """Real path (mocked) should produce flat BRIEF shape with health status."""
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
            provider="digitalocean", region="nyc3", workers=0,
            leader_size="s-2vcpu-4gb", worker_size="s-1vcpu-1gb",
            cluster_name="real-cluster", api_key="real-key",
        )

        mock_success.assert_called_once()
        brief = mock_success.call_args[0][0]
        assert brief["status"] == "ready"
        assert brief["leader_ip"] == "1.2.3.4"
        assert len(brief["nodes"]) == 1
        assert "provider" not in brief  # Rich fields stripped
