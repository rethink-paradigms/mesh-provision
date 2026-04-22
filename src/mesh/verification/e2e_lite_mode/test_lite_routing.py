import pytest
from unittest.mock import patch, MagicMock
from mesh.workloads.deploy_lite_ingress.route_manager import RouteManager
from mesh.infrastructure.progressive_activation.tier_config import (
    ClusterTier,
    TierConfig,
)


class TestLiteRouting:
    def test_add_multiple_routes(self):
        manager = RouteManager()
        with patch.object(manager, "_request", return_value=[]):
            assert manager.add_route("app1.example.com", "127.0.0.1", 8081) is True
            assert manager.add_route("app2.example.com", "127.0.0.1", 8082) is True

    def test_update_route(self):
        manager = RouteManager()
        with patch.object(manager, "_request", return_value=[]):
            assert manager.update_route("app.example.com", "127.0.0.1", 9090) is True

    def test_list_routes(self):
        manager = RouteManager()
        with patch.object(manager, "_request", return_value=[]):
            routes = manager.list_routes()
            assert isinstance(routes, list)

    def test_deploy_app_routes_to_lite_for_single_node(self):
        config = TierConfig.from_tier(ClusterTier.LITE)
        assert config.enable_caddy is True
