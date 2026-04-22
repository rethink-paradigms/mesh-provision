import pytest
from unittest.mock import patch, MagicMock
from mesh.infrastructure.progressive_activation.tier_config import (
    ClusterTier,
    TierConfig,
)
from mesh.infrastructure.progressive_activation.tier_manager import (
    detect_cluster_tier,
    NodeInfo,
)
from mesh.infrastructure.boot_consul_nomad.generate_boot_scripts import (
    generate_shell_script,
)


class TestLiteBoot:
    def test_lite_tier_config_no_consul_no_tailscale(self):
        config = TierConfig.from_tier(ClusterTier.LITE)
        assert config.enable_consul is False
        assert config.enable_tailscale is False
        assert config.enable_caddy is True

    def test_lite_boot_script_no_tailscale(self):
        script = generate_shell_script(
            tailscale_key="tskey-test",
            leader_ip="127.0.0.1",
            role="server",
            cluster_tier="lite",
        )
        assert 'CLUSTER_TIER="lite"' in script
        assert 'ENABLE_CADDY="true"' in script

    def test_lite_boot_script_no_consul_service(self):
        script = generate_shell_script(
            tailscale_key="tskey-test",
            leader_ip="127.0.0.1",
            role="server",
            cluster_tier="lite",
        )
        assert 'if [ "$CLUSTER_TIER" != "lite" ]' in script

    def test_lite_boot_installs_caddy(self):
        script = generate_shell_script(
            tailscale_key="tskey-test",
            leader_ip="127.0.0.1",
            role="server",
            cluster_tier="lite",
        )
        assert "scripts/10-install-caddy.sh" in script
        assert "/opt/caddy/data" in script

    def test_single_node_detected_as_lite(self):
        nodes = [NodeInfo(name="node-1", provider="aws", region="us-east-1", role="server")]
        config = detect_cluster_tier(nodes)
        assert config.tier == ClusterTier.LITE
        assert config.enable_caddy is True
