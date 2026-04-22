import json
from unittest.mock import MagicMock, patch

import pytest

from mesh.infrastructure.progressive_activation.tier_config import ClusterTier
from mesh.workloads.deploy_app.deploy import _detect_tier_from_nomad, deploy_app


@patch(
    "mesh.workloads.deploy_app.deploy._detect_tier_from_nomad",
    return_value=ClusterTier.LITE,
)
@patch(
    "mesh.workloads.deploy_lite_web_service.deploy.deploy_lite_web_service",
    return_value=True,
)
def test_deploy_app_lite_tier_uses_lite_service(mock_lite, mock_detect):
    result = deploy_app(
        app_name="test-app",
        image="test-image",
        image_tag="v1",
        port=8080,
        domain="test.example.com",
    )
    assert result is True
    mock_lite.assert_called_once_with(
        app_name="test-app",
        image="test-image",
        image_tag="v1",
        port=8080,
        domain="test.example.com",
        cpu=100,
        memory=128,
        datacenter="dc1",
        nomad_addr=None,
    )


@patch(
    "mesh.workloads.deploy_app.deploy._detect_tier_from_nomad",
    return_value=ClusterTier.STANDARD,
)
@patch(
    "mesh.workloads.deploy_lite_web_service.deploy.deploy_lite_web_service",
    return_value=True,
)
def test_deploy_app_standard_tier_uses_lite_service(mock_lite, mock_detect):
    result = deploy_app(
        app_name="test-app",
        image="test-image",
    )
    assert result is True
    mock_lite.assert_called_once()


@patch(
    "mesh.workloads.deploy_lite_web_service.deploy.deploy_lite_web_service",
    return_value=True,
)
def test_deploy_app_explicit_tier_overrides_detection(mock_lite):
    result = deploy_app(
        app_name="test-app",
        image="test-image",
        cluster_tier="lite",
    )
    assert result is True
    mock_lite.assert_called_once()


@patch("mesh.workloads.deploy_app.deploy.subprocess.run")
def test_detect_tier_from_nomad_single_node(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([{"Name": "node1", "Datacenter": "dc1", "Role": "client"}]),
    )
    tier = _detect_tier_from_nomad()
    assert tier == ClusterTier.LITE


@patch("mesh.workloads.deploy_app.deploy.subprocess.run")
def test_detect_tier_from_nomad_multiple_nodes(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(
            [
                {"Name": "node1", "Datacenter": "dc1", "Role": "client"},
                {"Name": "node2", "Datacenter": "dc1", "Role": "client"},
            ]
        ),
    )
    tier = _detect_tier_from_nomad()
    assert tier == ClusterTier.STANDARD


@patch("mesh.workloads.deploy_app.deploy.subprocess.run")
def test_detect_tier_from_nomad_failure_defaults_standard(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    tier = _detect_tier_from_nomad()
    assert tier == ClusterTier.STANDARD
