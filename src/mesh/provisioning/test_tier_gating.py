"""Tests for tier-gated boot script generation.

Lite tier:     no Tailscale script bundled, no Consul script bundled,
               Caddy + Nomad scripts bundled
Standard tier: Tailscale, Consul, Caddy, Nomad scripts all bundled
"""

import yaml
import pytest
from mesh.provisioning.boot import generate_cloud_init


def _bundled_scripts(cloud_init_yaml: str) -> list[str]:
    """Parse cloud-init YAML and return paths of all bundled script files."""
    config = yaml.safe_load(cloud_init_yaml)
    paths = []
    for entry in config.get("write_files", []):
        path = entry.get("path", "")
        if path.startswith("/opt/ops-platform/scripts/"):
            paths.append(path.split("/")[-1])  # just filename
    return paths


def _startup_script(cloud_init_yaml: str) -> str:
    """Extract the rendered startup.sh content from cloud-init YAML."""
    config = yaml.safe_load(cloud_init_yaml)
    for entry in config.get("write_files", []):
        if entry.get("path") == "/opt/ops-platform/startup.sh":
            return entry.get("content", "")
    return ""


class TestLiteTier:
    def test_lite_bundles_nomad_script(self):
        output = generate_cloud_init(role="server", cluster_tier="lite")
        assert "07-configure-nomad.sh" in _bundled_scripts(output)

    def test_lite_bundles_caddy_script(self):
        output = generate_cloud_init(role="server", cluster_tier="lite")
        assert "10-install-caddy.sh" in _bundled_scripts(output)

    def test_lite_does_not_bundle_tailscale(self):
        output = generate_cloud_init(role="server", cluster_tier="lite")
        assert "02-install-tailscale.sh" not in _bundled_scripts(output)

    def test_lite_does_not_bundle_consul(self):
        output = generate_cloud_init(role="server", cluster_tier="lite")
        assert "06-configure-consul.sh" not in _bundled_scripts(output)

    def test_lite_sets_cluster_tier_in_startup_script(self):
        output = generate_cloud_init(role="server", cluster_tier="lite")
        startup = _startup_script(output)
        assert 'CLUSTER_TIER="lite"' in startup

    def test_lite_server_role_in_startup_script(self):
        output = generate_cloud_init(role="server", cluster_tier="lite")
        startup = _startup_script(output)
        assert 'ROLE="server"' in startup


class TestStandardTier:
    def test_standard_bundles_tailscale(self):
        output = generate_cloud_init(role="server", cluster_tier="standard",
                                     tailscale_key="tskey-test")
        assert "02-install-tailscale.sh" in _bundled_scripts(output)

    def test_standard_bundles_consul(self):
        output = generate_cloud_init(role="server", cluster_tier="standard",
                                     tailscale_key="tskey-test")
        assert "06-configure-consul.sh" in _bundled_scripts(output)

    def test_standard_bundles_nomad(self):
        output = generate_cloud_init(role="server", cluster_tier="standard",
                                     tailscale_key="tskey-test")
        assert "07-configure-nomad.sh" in _bundled_scripts(output)

    def test_standard_bundles_caddy(self):
        output = generate_cloud_init(role="server", cluster_tier="standard",
                                     tailscale_key="tskey-test")
        assert "10-install-caddy.sh" in _bundled_scripts(output)

    def test_standard_client_role_in_startup(self):
        output = generate_cloud_init(role="client", cluster_tier="standard",
                                     tailscale_key="tskey-test", leader_ip="10.0.0.1")
        startup = _startup_script(output)
        assert 'ROLE="client"' in startup
        assert 'LEADER_IP="10.0.0.1"' in startup

    def test_standard_tailscale_key_injected_in_startup(self):
        output = generate_cloud_init(role="server", cluster_tier="standard",
                                     tailscale_key="tskey-mykey")
        startup = _startup_script(output)
        assert 'TAILSCALE_KEY="tskey-mykey"' in startup


class TestCloudInitStructure:
    def test_starts_with_cloud_config(self):
        output = generate_cloud_init(role="server", cluster_tier="lite")
        assert output.startswith("#cloud-config\n")

    def test_has_startup_script(self):
        output = generate_cloud_init(role="server", cluster_tier="lite")
        assert "/opt/ops-platform/startup.sh" in output

    def test_has_runcmd(self):
        config = yaml.safe_load(generate_cloud_init(role="server", cluster_tier="lite"))
        assert "runcmd" in config
        assert len(config["runcmd"]) >= 1
