"""
Tests for Feature: Progressive Activation - Tier Data Model

Test Categories:
    - Tier Configuration: from_tier factory method for each tier
    - Tier Detection: detect_cluster_tier from node topology
    - Edge Cases: override, default, error handling

Total: 8 tests
"""

import pytest

from mesh.infrastructure.progressive_activation.tier_config import (
    TierConfig,
    ClusterTier,
)
from mesh.infrastructure.progressive_activation.tier_manager import (
    detect_cluster_tier,
    NodeInfo,
    TierUpgradeError,
)


class TestTierConfig:
    def test_lite_tier_enables_caddy_disables_others(self):
        config = TierConfig.from_tier(ClusterTier.LITE)
        assert config.enable_caddy is True
        assert config.enable_tailscale is False
        assert config.enable_consul is False
        assert config.enable_telegraf is False

    def test_standard_tier_enables_caddy_and_consul(self):
        config = TierConfig.from_tier(ClusterTier.STANDARD)
        assert config.enable_caddy is True
        assert config.enable_consul is True
        assert config.enable_tailscale is True
        assert config.enable_telegraf is False

    def test_default_tier_is_standard(self):
        config = TierConfig()
        assert config.tier == ClusterTier.STANDARD

    def test_tier_config_from_tier_returns_correct_config(self):
        for tier in ClusterTier:
            config = TierConfig.from_tier(tier)
            assert config.tier == tier


class TestDetectClusterTier:
    def test_detect_single_node_is_lite(self):
        nodes = [NodeInfo(name="node-1", provider="aws", region="us-east-1", role="server")]
        config = detect_cluster_tier(nodes)
        assert config.tier == ClusterTier.LITE

    def test_detect_multi_node_same_region_is_standard(self):
        nodes = [
            NodeInfo(name="node-1", provider="aws", region="us-east-1", role="server"),
            NodeInfo(name="node-2", provider="aws", region="us-east-1", role="client"),
        ]
        config = detect_cluster_tier(nodes)
        assert config.tier == ClusterTier.STANDARD

    def test_detect_multi_region_is_standard(self):
        nodes = [
            NodeInfo(name="node-1", provider="aws", region="us-east-1", role="server"),
            NodeInfo(name="node-2", provider="aws", region="eu-west-1", role="client"),
        ]
        config = detect_cluster_tier(nodes)
        assert config.tier == ClusterTier.STANDARD

    def test_override_tier_takes_precedence(self):
        nodes = [
            NodeInfo(name="node-1", provider="aws", region="us-east-1", role="server"),
            NodeInfo(
                name="node-2",
                provider="aws",
                region="eu-west-1",
                role="client",
                is_spot=True,
            ),
        ]
        config = detect_cluster_tier(nodes, override_tier="lite")
        assert config.tier == ClusterTier.LITE

    def test_tier_upgrade_error_is_exception(self):
        assert issubclass(TierUpgradeError, Exception)
        with pytest.raises(TierUpgradeError):
            raise TierUpgradeError("feature not available")
