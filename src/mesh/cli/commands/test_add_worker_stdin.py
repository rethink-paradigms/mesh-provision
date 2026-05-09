"""Tests for add-worker stdin JSON dispatch."""

import io
import json
from unittest.mock import patch

from mesh.cli.commands.init_json import run_init_json_from_stdin


class TestAddWorkerStdinDemo:
    """Stdin dispatch correctness — verifies routing reaches _run_add_worker_json."""

    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    @patch("mesh.cli.commands.init_json._run_add_worker_json")
    def test_add_worker_stdin_demo(
        self, mock_run, mock_error, mock_success
    ):
        """Stdin dispatch routes add-worker command to _run_add_worker_json."""
        stdin_json = json.dumps({
            "version": "1",
            "command": "add-worker",
            "params": {
                "provider": "digitalocean",
                "region": "nyc3",
                "cluster_name": "test-cluster",
                "worker_size": "s-1vcpu-1gb",
                "leader_ip": "10.0.0.1",
                "api_key": "dummy",
            },
        })
        with patch("sys.stdin", io.StringIO(stdin_json)):
            try:
                run_init_json_from_stdin()
            except SystemExit:
                pass
        mock_run.assert_called_once()


class TestAddWorkerStdinFullFlow:
    """Full add-worker stdin flow with mocked provisioning internals."""

    @patch("mesh.cli.commands.add_worker.print_json_success")
    @patch("mesh.cli.commands.add_worker.print_json_error")
    @patch("mesh.infrastructure.provision_node.provision_direct.provision_node_direct")
    @patch(
        "mesh.infrastructure.boot_consul_nomad.generate_boot_scripts.generate_shell_script",
        return_value="# mock boot script",
    )
    def test_add_worker_stdin_full_flow(
        self, mock_script, mock_provision, mock_error, mock_success
    ):
        """Full add-worker via stdin produces correct node output."""
        mock_provision.return_value = {
            "public_ip": "203.0.113.99",
            "instance_id": "new-worker-1",
        }
        stdin_json = json.dumps({
            "version": "1",
            "command": "add-worker",
            "params": {
                "provider": "digitalocean",
                "region": "nyc3",
                "cluster_name": "test-cluster",
                "worker_size": "s-1vcpu-1gb",
                "leader_ip": "10.0.0.1",
                "api_key": "dummy",
            },
        })
        with patch("sys.stdin", io.StringIO(stdin_json)):
            try:
                run_init_json_from_stdin()
            except SystemExit:
                pass
        mock_success.assert_called_once()
        data = mock_success.call_args[0][0]
        assert "node" in data
        assert data["node"]["role"] == "worker"
        assert data["node"]["ip"] == "203.0.113.99"
        assert data["node"]["id"] == "new-worker-1"


class TestAddWorkerStdinErrors:
    """Error paths for add-worker stdin: missing required args."""

    @patch("mesh.cli.commands.json_output.print_json_error")
    def test_add_worker_stdin_missing_leader_ip(self, mock_error):
        """Stdin without leader_ip should error with missing_required_args."""
        stdin_json = json.dumps({
            "version": "1",
            "command": "add-worker",
            "params": {
                "provider": "digitalocean",
                "region": "nyc3",
                "cluster_name": "test-cluster",
                "worker_size": "s-1vcpu-1gb",
            },
        })
        with patch("sys.stdin", io.StringIO(stdin_json)):
            try:
                run_init_json_from_stdin()
            except SystemExit:
                pass
        mock_error.assert_called_once()
        assert mock_error.call_args[1]["code"] == "missing_required_args"

    @patch("mesh.cli.commands.json_output.print_json_error")
    def test_add_worker_stdin_missing_provider(self, mock_error):
        """Stdin without provider should error with missing_required_args."""
        stdin_json = json.dumps({
            "version": "1",
            "command": "add-worker",
            "params": {
                "region": "nyc3",
                "cluster_name": "test-cluster",
                "worker_size": "s-1vcpu-1gb",
                "leader_ip": "10.0.0.1",
            },
        })
        with patch("sys.stdin", io.StringIO(stdin_json)):
            try:
                run_init_json_from_stdin()
            except SystemExit:
                pass
        mock_error.assert_called_once()
        assert mock_error.call_args[1]["code"] == "missing_required_args"
