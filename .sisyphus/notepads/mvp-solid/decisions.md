# MVP Solid - Decisions

## 2026-04-22 Planning
- 3 MVP features: Cluster Bootstrap (manual install) + Container Deployment + Volume Snapshots
- NOT fixing mesh init CLI — manual install script only
- Tar-based snapshots (no CSI driver), container volumes only
- Strip Traefik, INGRESS/PRODUCTION tiers
- TDD: RED → GREEN → REFACTOR
- Install script runs ON the VM (SSH'd in)
- Tailscale auth via interactive prompt
- Snapshot storage: /var/lib/mesh/snapshots/ (local filesystem)
- Keep demo mode but remove silent fallbacks
