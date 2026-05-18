from dataclasses import dataclass
from enum import Enum


class ClusterTier(Enum):
    SOLO = "solo"
    CLUSTER = "cluster"


@dataclass
class TierConfig:
    tier: ClusterTier = ClusterTier.CLUSTER
    enable_tailscale: bool = True
    enable_telegraf: bool = False
    enable_caddy: bool = False
    enable_spot_handler: bool = False

    @classmethod
    def from_tier(cls, tier: ClusterTier) -> "TierConfig":
        configs = {
            ClusterTier.SOLO: cls(
                tier=tier,
                enable_tailscale=True,
                enable_telegraf=False,
                enable_caddy=True,
            ),
            ClusterTier.CLUSTER: cls(
                tier=tier,
                enable_tailscale=True,
                enable_telegraf=False,
                enable_caddy=True,
            ),
        }
        return configs[tier]
