"""Tests for tier selection in boot script generation.

Solo tier:     Tailscale, Nomad, Caddy scripts bundled (single VM)
Cluster tier:  Tailscale, Nomad, Caddy scripts bundled (multi VM, same scripts)
Consul:        removed entirely — no daemon references exist
"""

import yaml
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


class TestSoloTier:
    """Solo tier: single VM, Tailscale always on, no workers."""

    def test_solo_bundles_tailscale(self):
        output = generate_cloud_init(role="server", cluster_tier="solo",
                                     tailscale_key="tskey-test")
        assert "02-install-tailscale.sh" in _bundled_scripts(output)

    def test_solo_bundles_nomad_script(self):
        output = generate_cloud_init(role="server", cluster_tier="solo")
        assert "07-configure-nomad.sh" in _bundled_scripts(output)

    def test_solo_bundles_caddy_script(self):
        output = generate_cloud_init(role="server", cluster_tier="solo")
        assert "10-install-caddy.sh" in _bundled_scripts(output)

    def test_solo_does_not_bundle_consul(self):
        """Consul is removed — neither tier bundles it."""
        output = generate_cloud_init(role="server", cluster_tier="solo")
        assert "06-configure-consul.sh" not in _bundled_scripts(output)

    def test_solo_sets_cluster_tier_in_startup_script(self):
        output = generate_cloud_init(role="server", cluster_tier="solo")
        startup = _startup_script(output)
        assert 'CLUSTER_TIER="solo"' in startup

    def test_solo_server_role_in_startup_script(self):
        output = generate_cloud_init(role="server", cluster_tier="solo")
        startup = _startup_script(output)
        assert 'ROLE="server"' in startup


class TestClusterTier:
    """Cluster tier: multi VM, Tailscale always on, same scripts as solo."""

    def test_cluster_bundles_tailscale(self):
        output = generate_cloud_init(role="server", cluster_tier="cluster",
                                     tailscale_key="tskey-test")
        assert "02-install-tailscale.sh" in _bundled_scripts(output)

    def test_cluster_bundles_nomad(self):
        output = generate_cloud_init(role="server", cluster_tier="cluster",
                                     tailscale_key="tskey-test")
        assert "07-configure-nomad.sh" in _bundled_scripts(output)

    def test_cluster_bundles_caddy(self):
        output = generate_cloud_init(role="server", cluster_tier="cluster",
                                     tailscale_key="tskey-test")
        assert "10-install-caddy.sh" in _bundled_scripts(output)

    def test_cluster_does_not_bundle_consul(self):
        """Consul is removed — neither tier bundles it."""
        output = generate_cloud_init(role="server", cluster_tier="cluster",
                                     tailscale_key="tskey-test")
        assert "06-configure-consul.sh" not in _bundled_scripts(output)

    def test_cluster_client_role_in_startup(self):
        output = generate_cloud_init(role="client", cluster_tier="cluster",
                                     tailscale_key="tskey-test", leader_ip="10.0.0.1")
        startup = _startup_script(output)
        assert 'ROLE="client"' in startup
        assert 'LEADER_IP="10.0.0.1"' in startup

    def test_cluster_tailscale_key_injected_in_startup(self):
        output = generate_cloud_init(role="server", cluster_tier="cluster",
                                     tailscale_key="tskey-mykey")
        startup = _startup_script(output)
        assert 'TAILSCALE_KEY="tskey-mykey"' in startup


class TestTiersShareSameScripts:
    """Solo and cluster use identical scripts — only bootstrap_expect differs."""

    def test_solo_and_cluster_bundle_same_scripts(self):
        solo = set(_bundled_scripts(generate_cloud_init(
            role="server", cluster_tier="solo", tailscale_key="tskey-test")))
        cluster = set(_bundled_scripts(generate_cloud_init(
            role="server", cluster_tier="cluster", tailscale_key="tskey-test")))
        assert solo == cluster

    def test_tier_still_passed_to_template(self):
        """CLUSTER_TIER is still the provisioner's intent — boot.sh may ignore it now."""
        solo_startup = _startup_script(generate_cloud_init(role="server", cluster_tier="solo"))
        cluster_startup = _startup_script(generate_cloud_init(role="server", cluster_tier="cluster"))
        assert 'CLUSTER_TIER="solo"' in solo_startup
        assert 'CLUSTER_TIER="cluster"' in cluster_startup


class TestCloudInitStructure:
    def test_starts_with_cloud_config(self):
        output = generate_cloud_init(role="server", cluster_tier="solo")
        assert output.startswith("#cloud-config\n")

    def test_has_startup_script(self):
        output = generate_cloud_init(role="server", cluster_tier="solo")
        assert "/opt/ops-platform/startup.sh" in output

    def test_has_runcmd(self):
        config = yaml.safe_load(generate_cloud_init(role="server", cluster_tier="solo"))
        assert "runcmd" in config
        assert len(config["runcmd"]) >= 1
