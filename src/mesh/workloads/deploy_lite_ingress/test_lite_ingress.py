import json
import os
import subprocess
import urllib.error
from unittest.mock import patch, MagicMock, call
from mesh.workloads.deploy_lite_ingress.deploy import (
    deploy_lite_ingress,
    LiteIngressConfig,
)
from mesh.workloads.deploy_lite_ingress.route_manager import RouteManager


class TestLiteIngressConfig:
    def test_lite_ingress_config_defaults(self):
        config = LiteIngressConfig(acme_email="admin@example.com")
        assert config.acme_email == "admin@example.com"
        assert config.caddy_image == "caddy:2"
        assert config.memory == 25
        assert config.cpu == 100
        assert config.datacenter == "dc1"
        assert config.log_level == "INFO"
        assert config.nomad_addr is None

    def test_lite_ingress_config_custom(self):
        config = LiteIngressConfig(
            acme_email="ops@example.com",
            caddy_image="caddy:2-alpine",
            memory=50,
            cpu=200,
            datacenter="dc-prod",
            log_level="DEBUG",
            nomad_addr="http://10.0.0.1:4646",
        )
        assert config.acme_email == "ops@example.com"
        assert config.caddy_image == "caddy:2-alpine"
        assert config.memory == 50
        assert config.cpu == 200
        assert config.datacenter == "dc-prod"
        assert config.log_level == "DEBUG"
        assert config.nomad_addr == "http://10.0.0.1:4646"


class TestDeployLiteIngress:
    @patch("mesh.workloads.deploy_lite_ingress.deploy.os.path.exists")
    def test_deploy_lite_ingress_missing_job_file(self, mock_exists):
        mock_exists.return_value = False
        config = LiteIngressConfig(acme_email="admin@example.com")
        result = deploy_lite_ingress(config)
        assert result is False

    @patch("mesh.workloads.deploy_lite_ingress.deploy.subprocess.run")
    @patch("mesh.workloads.deploy_lite_ingress.deploy.os.path.exists")
    def test_deploy_lite_ingress_success(self, mock_exists, mock_run):
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(stdout="Deployment successful", returncode=0)
        config = LiteIngressConfig(acme_email="admin@example.com")
        result = deploy_lite_ingress(config)
        assert result is True

    @patch("mesh.workloads.deploy_lite_ingress.deploy.subprocess.run")
    @patch("mesh.workloads.deploy_lite_ingress.deploy.os.path.exists")
    def test_deploy_lite_ingress_nomad_addr(self, mock_exists, mock_run):
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(stdout="OK", returncode=0)
        config = LiteIngressConfig(
            acme_email="admin@example.com", nomad_addr="http://10.0.0.1:4646"
        )
        deploy_lite_ingress(config)
        call_args = mock_run.call_args[0][0]
        assert "-address" in call_args
        assert "http://10.0.0.1:4646" in call_args


class TestNomadJobTemplate:
    def test_nomad_job_template_valid_hcl_syntax(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        hcl_file = os.path.join(script_dir, "lite_ingress.nomad.hcl")
        assert os.path.exists(hcl_file)
        with open(hcl_file, "r") as f:
            content = f.read()
        assert 'job "caddy"' in content
        assert 'type = "system"' in content
        assert "variable" in content

    def test_caddy_template_has_correct_ports(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        hcl_file = os.path.join(script_dir, "lite_ingress.nomad.hcl")
        with open(hcl_file, "r") as f:
            content = f.read()
        assert "static = 80" in content
        assert "static = 443" in content
        assert "static = 2019" in content

    def test_caddy_template_has_http_redirect(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        hcl_file = os.path.join(script_dir, "lite_ingress.nomad.hcl")
        with open(hcl_file, "r") as f:
            content = f.read()
        assert "redir https://{host}{uri} permanent" in content

    def test_caddy_template_has_server_constraint(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        hcl_file = os.path.join(script_dir, "lite_ingress.nomad.hcl")
        with open(hcl_file, "r") as f:
            content = f.read()
        assert "${meta.role}" in content
        assert '"server"' in content

    def test_caddy_template_has_host_volume(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        hcl_file = os.path.join(script_dir, "lite_ingress.nomad.hcl")
        with open(hcl_file, "r") as f:
            content = f.read()
        assert "caddy-data" in content

    def test_caddy_template_default_resources(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        hcl_file = os.path.join(script_dir, "lite_ingress.nomad.hcl")
        with open(hcl_file, "r") as f:
            content = f.read()
        assert "default = 25" in content
        assert "default = 100" in content

    def test_caddy_template_has_mesh_infra_namespace(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        hcl_file = os.path.join(script_dir, "lite_ingress.nomad.hcl")
        with open(hcl_file, "r") as f:
            content = f.read()
        assert 'namespace = "mesh-infra"' in content
        # Verify it's in the job stanza, not a variable or task config
        job_stanza_line = [l for l in content.splitlines() if 'job "caddy"' in l]
        assert len(job_stanza_line) == 1
        # Find the line index of the job stanza
        lines = content.splitlines()
        job_idx = next(i for i, l in enumerate(lines) if 'job "caddy"' in l)
        # namespace should be within the first 3 lines after job opening
        nearby = lines[job_idx : job_idx + 4]
        assert any('namespace = "mesh-infra"' in l for l in nearby)


class TestRouteManager:
    def _mock_urlopen(self, response_data=None):
        if response_data is None:
            response_data = {}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("mesh.workloads.deploy_lite_ingress.route_manager.urllib.request.urlopen")
    def test_route_manager_add_route(self, mock_urlopen):
        existing_routes = []
        mock_urlopen.return_value = self._mock_urlopen(existing_routes)
        rm = RouteManager()
        result = rm.add_route("app.example.com", "10.0.0.5", 8080)
        assert result is True

    @patch("mesh.workloads.deploy_lite_ingress.route_manager.urllib.request.urlopen")
    def test_route_manager_remove_route(self, mock_urlopen):
        existing_routes = [
            {
                "match": [{"host": ["app.example.com"]}],
                "handle": [{"handler": "reverse_proxy"}],
            }
        ]
        mock_urlopen.return_value = self._mock_urlopen(existing_routes)
        rm = RouteManager()
        result = rm.remove_route("app.example.com")
        assert result is True

    @patch("mesh.workloads.deploy_lite_ingress.route_manager.urllib.request.urlopen")
    def test_route_manager_list_routes(self, mock_urlopen):
        routes = [
            {
                "match": [{"host": ["app.example.com"]}],
                "handle": [{"handler": "reverse_proxy"}],
            }
        ]
        mock_urlopen.return_value = self._mock_urlopen(routes)
        rm = RouteManager()
        result = rm.list_routes()
        assert len(result) == 1

    @patch("mesh.workloads.deploy_lite_ingress.route_manager.urllib.request.urlopen")
    def test_route_manager_retry_on_failure(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([]).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            urllib.error.URLError("connection refused"),
            urllib.error.URLError("connection refused"),
            mock_resp,
        ]
        rm = RouteManager()
        result = rm.list_routes()
        assert result == []
        assert mock_urlopen.call_count == 3

    @patch("mesh.workloads.deploy_lite_ingress.route_manager.urllib.request.urlopen")
    def test_route_manager_add_route_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        rm = RouteManager()
        result = rm.add_route("app.example.com", "10.0.0.5", 8080)
        assert result is False

    @patch("mesh.workloads.deploy_lite_ingress.route_manager.urllib.request.urlopen")
    def test_route_manager_remove_route_empty(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen([])
        rm = RouteManager()
        result = rm.remove_route("nonexistent.example.com")
        assert result is True

    @patch("mesh.workloads.deploy_lite_ingress.route_manager.urllib.request.urlopen")
    def test_route_manager_update_route(self, mock_urlopen):
        existing_routes = [
            {
                "match": [{"host": ["app.example.com"]}],
                "handle": [{"handler": "reverse_proxy"}],
            }
        ]
        mock_urlopen.return_value = self._mock_urlopen(existing_routes)
        rm = RouteManager()
        result = rm.update_route("app.example.com", "10.0.0.10", 9090)
        assert result is True

    @patch("mesh.workloads.deploy_lite_ingress.route_manager.urllib.request.urlopen")
    def test_route_manager_list_routes_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        rm = RouteManager()
        result = rm.list_routes()
        assert result == []
