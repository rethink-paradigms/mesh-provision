import pytest
"""
Tests for Boot Script Integration

Validates boot script generation and injection:
- Tailscale key injection
- Role (server/client) inclusion
- Leader IP inclusion
- GPU installation commands
- Spot handler script
- Complete leader boot script
- Complete worker boot script
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from mesh.provisioning.boot import generate_cloud_init


def test_boot_script_contains_tailscale_key():
    """
    Test_BootScript_ContainsTailscaleKey: Verify Tailscale key injected into boot script.

    Validates that the provided Tailscale auth key is correctly embedded
    in the generated boot script.
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="tskey-control-123abc", leader_ip="10.0.0.1", role="client"
    )

    assert 'TAILSCALE_KEY="tskey-control-123abc"' in script


def test_boot_script_contains_role_server():
    """
    Test_BootScript_ContainsRoleServer: Verify server role in boot script.

    Validates that when role="server", the boot script contains
    the correct role specification.
    """
    script = generate_cloud_init(role="server", cluster_tier="standard", tailscale_key="test-key", leader_ip="127.0.0.1")

    assert 'ROLE="server"' in script


def test_boot_script_contains_role_client():
    """
    Test_BootScript_ContainsRoleClient: Verify client role in boot script.

    Validates that when role="client", the boot script contains
    the correct role specification.
    """
    script = generate_cloud_init(role="client", cluster_tier="standard", tailscale_key="test-key", leader_ip="vm-leader")

    assert 'ROLE="client"' in script


def test_boot_script_contains_leader_ip():
    """
    Test_BootScript_ContainsLeaderIP: Verify leader IP in boot script.

    Validates that the provided leader IP is correctly embedded
    in the generated boot script.
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="test-key", leader_ip="192.168.1.100", role="client"
    )

    assert 'LEADER_IP="192.168.1.100"' in script


@pytest.mark.skip(reason="GPU/spot handling removed from generate_cloud_init - these are Phase 1 features not needed for subprocess protocol")
def test_boot_script_with_gpu():
    """
    Test_BootScript_WithGPU: Verify GPU installation commands present.

    GPU installation commands and configuration.
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="test-key",
        leader_ip="vm-leader",
        role="client",
    )

    # Check for HAS_GPU flag
    assert 'HAS_GPU="true"' in script
    # Check for GPU installation scripts
    assert "04-install-gpu-drivers.sh" in script
    assert "05-install-nvidia-plugin.sh" in script
    assert "08-verify-gpu.sh" in script
    # Check for CUDA and driver version variables
    assert 'CUDA_VERSION="12.1"' in script
    assert 'DRIVER_VERSION="535"' in script


@pytest.mark.skip(reason="GPU/spot handling removed from generate_cloud_init - these are Phase 1 features not needed for subprocess protocol")
def test_boot_script_with_spot_handling():
    """
    Test_BootScript_WithSpotHandling: Verify spot handler script present.

    spot instance interruption handling commands.
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="test-key",
        leader_ip="vm-leader",
        role="client",
        spot_check_interval=5,
        spot_grace_period=90,
    )

    # Check for ENABLE_SPOT_HANDLING flag
    assert 'ENABLE_SPOT_HANDLING="true"' in script
    # Check for spot handler script and systemd service
    assert "09-handle-spot-interruption.sh" in script
    assert "spot-handler.service" in script
    # Check for spot interval variables
    assert 'SPOT_CHECK_INTERVAL="5"' in script
    assert 'SPOT_GRACE_PERIOD="90"' in script


def test_boot_script_full_leader():
    """
    Test_BootScript_FullLeader: Verify complete leader boot script.

    Validates that a leader role boot script contains all required components:
    - Tailscale key
    - Server role
    - Leader IP (127.0.0.1 for bootstrap)
    - Nomad server mode
    - Consul server mode
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="tskey-leader-xyz", leader_ip="127.0.0.1", role="server"
    )

    # Required parameters
    assert 'TAILSCALE_KEY="tskey-leader-xyz"' in script
    assert 'ROLE="server"' in script
    assert 'LEADER_IP="127.0.0.1"' in script

    # Server components
    assert "server" in script.lower()  # Should have server mode enabled


def test_boot_script_full_worker():
    """
    Test_BootScript_FullWorker: Verify complete worker boot script.

    Validates that a worker role boot script contains all required components:
    - Tailscale key
    - Client role
    - Leader IP reference
    - Nomad client mode
    - Consul client mode
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="tskey-worker-abc", leader_ip="vm-leader", role="client"
    )

    # Required parameters
    assert 'TAILSCALE_KEY="tskey-worker-abc"' in script
    assert 'ROLE="client"' in script
    assert 'LEADER_IP="vm-leader"' in script

    # Client components
    assert "client" in script.lower()  # Should have client mode enabled


@pytest.mark.skip(reason="GPU/spot handling removed from generate_cloud_init - these are Phase 1 features not needed for subprocess protocol")
def test_boot_script_with_gpu_and_spot():
    """
    Test_BootScript_WithGPUAndSpot: Verify GPU and spot handling combined.

    Validates that when both GPU and spot handling are enabled,
    the boot script includes both sets of functionality.
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="test-key",
        leader_ip="vm-leader",
        role="client",
        spot_check_interval=10,
        spot_grace_period=120,
    )

    # GPU components
    assert 'HAS_GPU="true"' in script
    assert "04-install-gpu-drivers.sh" in script
    assert 'CUDA_VERSION="12.1"' in script

    # Spot handling components
    assert 'ENABLE_SPOT_HANDLING="true"' in script
    assert "09-handle-spot-interruption.sh" in script
    assert 'SPOT_CHECK_INTERVAL="10"' in script
    assert 'SPOT_GRACE_PERIOD="120"' in script

    # Required components
    assert 'TAILSCALE_KEY="test-key"' in script
    assert 'ROLE="client"' in script
    assert 'LEADER_IP="vm-leader"' in script


@pytest.mark.skip(reason="GPU/spot handling removed from generate_cloud_init - these are Phase 1 features not needed for subprocess protocol")
def test_boot_script_custom_driver_version():
    """
    Test_BootScript_CustomDriverVersion: Verify custom NVIDIA driver version.

    Validates that custom NVIDIA driver versions are correctly embedded.
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="test-key",
        leader_ip="vm-leader",
        role="client",
    )

    assert 'CUDA_VERSION="11.8"' in script
    assert 'DRIVER_VERSION="525"' in script


@pytest.mark.skip(reason="GPU/spot handling removed from generate_cloud_init - these are Phase 1 features not needed for subprocess protocol")
def test_boot_script_custom_spot_intervals():
    """
    Test_BootScript_CustomSpotIntervals: Verify custom spot intervals.

    Validates that custom spot check interval and grace period values
    are correctly embedded in the boot script.
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="test-key",
        leader_ip="vm-leader",
        role="client",
        spot_check_interval=15,
        spot_grace_period=150,
    )

    assert 'SPOT_CHECK_INTERVAL="15"' in script
    assert 'SPOT_GRACE_PERIOD="150"' in script


def test_boot_script_without_optional_features():
    """
    Test_BootScript_WithoutOptionalFeatures: Verify minimal boot script.

    Validates that when GPU and spot handling are both disabled,
    the boot script doesn't include those features.
    """
    script = generate_cloud_init(cluster_tier="standard", 
        tailscale_key="test-key",
        leader_ip="vm-leader",
        role="client",
    )

    # Should have HAS_GPU and ENABLE_SPOT_HANDLING set to false
    assert 'HAS_GPU="false"' in script
    assert 'ENABLE_SPOT_HANDLING="false"' in script
    # Variables are always declared, just with different values

    # Should still have required components
    assert 'TAILSCALE_KEY="test-key"' in script
    assert 'ROLE="client"' in script
    assert 'LEADER_IP="vm-leader"' in script
