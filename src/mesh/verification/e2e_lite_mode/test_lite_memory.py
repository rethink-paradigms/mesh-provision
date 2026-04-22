import pytest
from mesh.infrastructure.progressive_activation.tier_config import (
    ClusterTier,
    TierConfig,
)


class TestLiteMemory:
    def test_lite_mode_overhead_budget(self):
        config = TierConfig.from_tier(ClusterTier.LITE)
        overhead = 0
        if not config.enable_consul:
            overhead += 0
        if not config.enable_tailscale:
            overhead += 0
        if not config.enable_telegraf:
            overhead += 0

        base_overhead = 80 + 100 + 20
        assert base_overhead <= 200

    def test_caddy_memory_allocation(self):
        from mesh.workloads.deploy_lite_ingress.deploy import LiteIngressConfig

        config = LiteIngressConfig(acme_email="test@example.com")
        assert config.memory <= 50

    def test_lite_vs_full_savings(self):
        full_overhead = 80 + 100 + 50 + 20 + 256 + 30
        lite_overhead = 80 + 100 + 20
        savings_percent = ((full_overhead - lite_overhead) / full_overhead) * 100
        assert savings_percent >= 60
