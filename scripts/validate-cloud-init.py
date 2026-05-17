#!/usr/bin/env python3
"""
Standalone cloud-init validator for mesh-provision.

Validates generated cloud-init YAML without deploying a VM:
  1. Checks all embedded scripts for YAML-unsafe characters (em-dashes, etc.)
  2. YAML round-trip (dump → parse → verify)
  3. Shell syntax validation with bash -n
  4. Optional: daemon config schema validation

Usage:
    python scripts/validate-cloud-init.py

Exit codes:
    0 = all validations passed
    1 = validation failed (see stderr)
"""

import sys
import os

# Add mesh-provision src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mesh.provisioning.boot import generate_cloud_init


def main():
    print("=" * 60)
    print("mesh-provision cloud-init pre-flight validator")
    print("=" * 60)

    # Test 1: Standard cluster (leader) with daemon config
    print("\n[1/3] Validating standard cluster (leader) cloud-init...")
    try:
        yaml_out = generate_cloud_init(
            role="server",
            cluster_tier="cluster",
            tailscale_key="tskey-test-k2CNTRL-xxxxxxxxxxxxxxxxxxxxxxxxxx",
            leader_ip="",
            daemon_config="""daemon:
  cluster_id: test-cluster-id
  gateway_url: https://example.com
  heartbeat_interval_seconds: 30
  auth_mode: both
  auth_token: test-token
  auth0_domain: test.auth0.com
  auth0_audience: https://test
  listen_addr: 0.0.0.0:8080
store:
  path: /root/.mesh/state.db
plugin:
  dir: /root/.mesh/plugins
ingress:
  adapter: caddy
limits:
  max_bodies: 10
  max_snapshots: 5
""",
            validate=True,
        )
        print("   PASS: Standard cluster cloud-init is valid")
    except ValueError as e:
        print(f"   FAIL: {e}")
        return 1

    # Test 2: Worker node (no daemon config)
    print("\n[2/3] Validating worker node cloud-init...")
    try:
        generate_cloud_init(
            role="client",
            cluster_tier="cluster",
            tailscale_key="tskey-test-k2CNTRL-xxxxxxxxxxxxxxxxxxxxxxxxxx",
            leader_ip="10.0.0.1",
            daemon_config=None,
            validate=True,
        )
        print("   PASS: Worker node cloud-init is valid")
    except ValueError as e:
        print(f"   FAIL: {e}")
        return 1

    # Test 3: Solo tier
    print("\n[3/3] Validating solo tier cloud-init...")
    try:
        generate_cloud_init(
            role="server",
            cluster_tier="solo",
            tailscale_key="tskey-test-k2CNTRL-xxxxxxxxxxxxxxxxxxxxxxxxxx",
            leader_ip="",
            daemon_config="""daemon:
  cluster_id: test-solo-id
  gateway_url: https://example.com
  heartbeat_interval_seconds: 30
  auth_mode: both
  auth_token: test-token
  auth0_domain: test.auth0.com
  auth0_audience: https://test
  listen_addr: 0.0.0.0:8080
store:
  path: /root/.mesh/state.db
plugin:
  dir: /root/.mesh/plugins
""",
            validate=True,
        )
        print("   PASS: Solo tier cloud-init is valid")
    except ValueError as e:
        print(f"   FAIL: {e}")
        return 1

    print("\n" + "=" * 60)
    print("ALL VALIDATIONS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
