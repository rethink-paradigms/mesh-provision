"""Tests for tier configuration."""

import pytest
from mesh.tiers.tier_config import ClusterTier, TierConfig


class TestTierConfig:
    def test_lite_tier_config(self):
        config = TierConfig.from_tier(ClusterTier.LITE)
        assert config.tier == ClusterTier.LITE
        assert config.enable_caddy is True
        assert config.enable_tailscale is False
        assert config.enable_consul is False

    def test_standard_tier_config(self):
        config = TierConfig.from_tier(ClusterTier.STANDARD)
        assert config.tier == ClusterTier.STANDARD
        assert config.enable_tailscale is True
        assert config.enable_consul is True
        assert config.enable_caddy is True

    def test_workers_zero_means_lite(self):
        workers = 0
        tier = ClusterTier.LITE if workers == 0 else ClusterTier.STANDARD
        config = TierConfig.from_tier(tier)
        assert config.tier == ClusterTier.LITE

    def test_workers_nonzero_means_standard(self):
        workers = 2
        tier = ClusterTier.LITE if workers == 0 else ClusterTier.STANDARD
        config = TierConfig.from_tier(tier)
        assert config.tier == ClusterTier.STANDARD
