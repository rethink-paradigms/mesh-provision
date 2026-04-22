from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .tier_config import TierConfig


@dataclass
class NodeInfo:
    name: str
    provider: str
    region: str
    role: str
    is_spot: bool = False


def detect_cluster_tier(nodes: List[NodeInfo], override_tier: Optional[str] = None) -> TierConfig:
    """Detect cluster tier from node topology.

    Logic:
    - If override_tier is provided, use it directly
    - 1 node -> LITE
    - 2+ nodes -> STANDARD
    """
    from .tier_config import ClusterTier, TierConfig

    if override_tier:
        tier = ClusterTier(override_tier)
        return TierConfig.from_tier(tier)

    if len(nodes) <= 1:
        return TierConfig.from_tier(ClusterTier.LITE)

    return TierConfig.from_tier(ClusterTier.STANDARD)


class TierUpgradeError(Exception):
    """Raised when attempting to use a feature not available in the current tier."""

    pass
