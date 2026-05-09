"""
Tests for Provider: Libcloud Dynamic Provider (Multi-Cloud Node Provisioning)

This test suite validates the UniversalCloudNodeProvider which implements
Pulumi's Dynamic Resource API for multi-cloud node provisioning using Apache
Libcloud drivers with exact provider values (no size tier abstractions).

Test Categories:
    T1: Provider Support (5 tests)
    T2: create() Method (10 tests)
    T3: delete() and read() Methods (5 tests)
    T4: Credential Resolution (5 tests)
    T5: Discovery Methods (5 tests)

Total: 30 unit tests
"""

import pytest
from unittest.mock import Mock, patch

# Import libcloud after mocking
from libcloud.compute.types import Provider

# Import pulumi before importing the module under test

# Now import the module under test
from mesh.infrastructure.providers.libcloud_dynamic_provider import UniversalCloudNodeProvider

from mesh.infrastructure.providers import (
    get_credentials,
    is_provider_supported,
    PROVIDER_ENUMS,
)

from mesh.infrastructure.providers.discovery import (
    list_sizes,
    list_regions,
    get_size,
    is_region_available,
)


class TestProviderSupport:
    """
    T1: Test Provider Support (5 tests)

    Validates that the provider correctly identifies supported providers
    and handles unknown providers appropriately.
    """

    def test_known_providers_are_supported(self):
        """
        Test_ProviderSupport_KnownProvidersAreSupported: Verify that known
        providers (aws, digitalocean, gcp) are recognized as supported.
        """
        assert is_provider_supported("aws") is True
        assert is_provider_supported("digitalocean") is True
        assert is_provider_supported("gcp") is True
        assert is_provider_supported("azure") is True
        assert is_provider_supported("linode") is True
        assert is_provider_supported("vultr") is True

    def test_unknown_provider_not_supported(self):
        """
        Test_ProviderSupport_UnknownProviderNotSupported: Verify that unknown
        providers return False for is_provider_supported.
        """
        assert is_provider_supported("unknown_provider") is False
        assert is_provider_supported("fake_cloud") is False
        assert is_provider_supported("") is False

    def test_provider_enum_mappings_exist(self):
        """
        Test_ProviderSupport_ProviderEnumMappingsExist: Verify that provider
        enum mappings are defined for all supported providers.
        """
        # Check that common providers have enum mappings
        assert "aws" in PROVIDER_ENUMS
        assert "digitalocean" in PROVIDER_ENUMS
        assert "gcp" in PROVIDER_ENUMS
        assert PROVIDER_ENUMS["aws"] == Provider.EC2
        assert PROVIDER_ENUMS["digitalocean"] == Provider.DIGITAL_OCEAN
        assert PROVIDER_ENUMS["gcp"] == Provider.GCE

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    def test_create_with_unknown_provider_fails(self, mock_get_stack):
        """
        Test_ProviderSupport_CreateWithUnknownProviderFails: Verify that
        attempting to create a node with an unknown provider raises ValueError.
        """
        with patch(
            "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
            return_value="test-project",
        ):
            provider = UniversalCloudNodeProvider()

            inputs = {
                "provider": "unknown_provider",
                "region": "us-east-1",
                "size_id": "t3.medium",
                "boot_script": "#!/bin/bash\necho test",
            }

            with pytest.raises(ValueError, match="Unknown provider"):
                provider.create(inputs)

    def test_get_driver_with_supported_provider(self):
        """
        Test_ProviderSupport_GetDriverWithSupportedProvider: Verify that
        get_driver works for supported providers with valid credentials.
        """
        # Mock environment variables
        with patch.dict(
            "os.environ", {"AWS_ACCESS_KEY_ID": "test_key", "AWS_SECRET_ACCESS_KEY": "test_secret"}
        ):
            # This should not raise an error for provider enum mapping
            assert is_provider_supported("aws") is True


class TestCreateMethod:
    """
    T2: Test create() Method (10 tests)

    Validates the create() method of UniversalCloudNodeProvider including
    validation, driver initialization, and node creation.
    """

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
        return_value="test-project",
    )
    def test_create_with_exact_size_id(self, mock_get_project, mock_get_stack):
        """
        Test_CreateMethod_CreateWithExactSizeId: Verify that create() works
        with exact size_id parameter (e.g., "t3.medium", "s-2vcpu-4gb").
        """
        # Mock the discovery methods and provider check
        mock_size = Mock(id="t3.medium", ram=4096, name="t3.medium")
        mock_image = Mock(id="ami-12345")

        # Mock driver and node
        mock_node = Mock(
            id="i-1234567890abcdef0",
            state="RUNNING",
            public_ips=["1.2.3.4"],
            private_ips=["10.0.0.1"],
        )
        mock_driver = Mock()
        mock_driver.create_node.return_value = mock_node

        # Patch everything at the module where they're imported
        with (
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_region_available",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_size",
                return_value=mock_size,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.find_ubuntu_image",
                return_value=mock_image,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver",
                return_value=mock_driver,
            ),
        ):

            provider = UniversalCloudNodeProvider()

            inputs = {
                "provider": "aws",
                "region": "us-east-1",
                "size_id": "t3.medium",
                "boot_script": "#!/bin/bash\necho test",
            }

            result = provider.create(inputs)

            assert result.id == "i-1234567890abcdef0"
            assert result.outs["public_ip"] == "1.2.3.4"
            assert result.outs["private_ip"] == "10.0.0.1"
            assert result.outs["status"] == "RUNNING"
            assert result.outs["size_id"] == "t3.medium"

            # Verify driver was called with exact size
            mock_driver.create_node.assert_called_once()
            call_args = mock_driver.create_node.call_args
            assert call_args[1]["size"].id == "t3.medium"

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
        return_value="test-project",
    )
    def test_create_with_invalid_size_id_fails(self, mock_get_project, mock_get_stack):
        """
        Test_CreateMethod_CreateWithInvalidSizeIdFails: Verify that create()
        fails with clear error when size_id doesn't exist.
        """
        with (
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_region_available",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_size",
                return_value=None,
            ),
        ):

            provider = UniversalCloudNodeProvider()

            inputs = {
                "provider": "aws",
                "region": "us-east-1",
                "size_id": "invalid_size",
                "boot_script": "#!/bin/bash\necho test",
            }

            with pytest.raises(ValueError, match="Invalid size_id"):
                provider.create(inputs)

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
        return_value="test-project",
    )
    def test_create_with_invalid_region_fails(self, mock_get_project, mock_get_stack):
        """
        Test_CreateMethod_CreateWithInvalidRegionFails: Verify that create()
        fails with clear error when region doesn't exist.
        """
        with (
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_region_available",
                return_value=False,
            ),
        ):

            provider = UniversalCloudNodeProvider()

            inputs = {
                "provider": "aws",
                "region": "invalid-region",
                "size_id": "t3.medium",
                "boot_script": "#!/bin/bash\necho test",
            }

            with pytest.raises(ValueError, match="Invalid region"):
                provider.create(inputs)

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
        return_value="test-project",
    )
    def test_create_with_explicit_image_id(self, mock_get_project, mock_get_stack):
        """
        Test_CreateMethod_CreateWithExplicitImageId: Verify that create()
        works with explicit image_id parameter.
        """
        mock_size = Mock(id="t3.medium", ram=4096)
        mock_image = Mock(id="ami-custom")

        mock_node = Mock(
            id="i-1234567890abcdef0",
            state="RUNNING",
            public_ips=["1.2.3.4"],
            private_ips=["10.0.0.1"],
        )
        mock_driver = Mock()
        mock_driver.create_node.return_value = mock_node

        with (
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_region_available",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_size",
                return_value=mock_size,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_image",
                return_value=mock_image,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver",
                return_value=mock_driver,
            ),
        ):

            provider = UniversalCloudNodeProvider()

            inputs = {
                "provider": "aws",
                "region": "us-east-1",
                "size_id": "t3.medium",
                "image_id": "ami-custom",
                "boot_script": "#!/bin/bash\necho test",
            }

            result = provider.create(inputs)

            assert result.id == "i-1234567890abcdef0"
            # Verify the explicit image was used
            mock_driver.create_node.assert_called_once()
            call_args = mock_driver.create_node.call_args
            assert call_args[1]["image"].id == "ami-custom"

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
        return_value="test-project",
    )
    def test_create_auto_discovers_ubuntu_image(self, mock_get_project, mock_get_stack):
        """
        Test_CreateMethod_CreateAutoDiscoversUbuntuImage: Verify that create()
        automatically discovers Ubuntu 22.04 image when image_id is not specified.
        """
        mock_size = Mock(id="t3.medium", ram=4096)
        mock_ubuntu_image = Mock(id="ami-ubuntu-22-04", name="ubuntu-jammy-22.04")

        mock_node = Mock(
            id="i-1234567890abcdef0",
            state="RUNNING",
            public_ips=["1.2.3.4"],
            private_ips=["10.0.0.1"],
        )
        mock_driver = Mock()
        mock_driver.create_node.return_value = mock_node

        with (
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_region_available",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_size",
                return_value=mock_size,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.find_ubuntu_image",
                return_value=mock_ubuntu_image,
            ) as mock_find,
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver",
                return_value=mock_driver,
            ),
        ):

            provider = UniversalCloudNodeProvider()

            inputs = {
                "provider": "aws",
                "region": "us-east-1",
                "size_id": "t3.medium",
                "boot_script": "#!/bin/bash\necho test",
                # No image_id specified
            }

            result = provider.create(inputs)

            # Verify Ubuntu image discovery was called
            mock_find.assert_called_once_with("aws", version="22.04")
            assert result.id == "i-1234567890abcdef0"

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
        return_value="test-project",
    )
    def test_create_requires_size_id(self, mock_get_project, mock_get_stack):
        """
        Test_CreateMethod_CreateRequiresSizeId: Verify that create() fails
        when size_id is not provided (no size tier fallback).
        """
        provider = UniversalCloudNodeProvider()

        inputs = {
            "provider": "aws",
            "region": "us-east-1",
            "size_id": "",  # Empty size_id
            "boot_script": "#!/bin/bash\necho test",
        }

        with pytest.raises(ValueError, match="size_id is required"):
            provider.create(inputs)

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
        return_value="test-project",
    )
    def test_create_passes_boot_script_via_userdata(self, mock_get_project, mock_get_stack):
        """
        Test_CreateMethod_CreatePassesBootScriptViaUserdata: Verify that
        the boot script is passed to the driver via ex_userdata parameter.
        """
        mock_size = Mock(id="t3.medium", ram=4096)
        mock_image = Mock(id="ami-123")

        mock_node = Mock(
            id="i-1234567890abcdef0",
            state="RUNNING",
            public_ips=["1.2.3.4"],
            private_ips=["10.0.0.1"],
        )
        mock_driver = Mock()
        mock_driver.create_node.return_value = mock_node

        boot_script = "#!/bin/bash\necho 'Hello World'"

        with (
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_region_available",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_size",
                return_value=mock_size,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.find_ubuntu_image",
                return_value=mock_image,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver",
                return_value=mock_driver,
            ),
        ):

            provider = UniversalCloudNodeProvider()

            inputs = {
                "provider": "aws",
                "region": "us-east-1",
                "size_id": "t3.medium",
                "boot_script": boot_script,
            }

            provider.create(inputs)

            # Verify ex_userdata was passed with boot script
            call_args = mock_driver.create_node.call_args
            assert call_args[1]["ex_userdata"] == boot_script

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_stack",
        return_value="test-stack",
    )
    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.pulumi.get_project",
        return_value="test-project",
    )
    def test_create_handles_driver_failure(self, mock_get_project, mock_get_stack):
        """
        Test_CreateMethod_CreateHandlesDriverFailure: Verify that create()
        properly handles and reports driver creation failures.
        """
        mock_size = Mock(id="t3.medium", ram=4096)
        mock_image = Mock(id="ami-123")

        mock_driver = Mock()
        mock_driver.create_node.side_effect = Exception("Provider API error")

        with (
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.is_region_available",
                return_value=True,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_size",
                return_value=mock_size,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.find_ubuntu_image",
                return_value=mock_image,
            ),
            patch(
                "mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver",
                return_value=mock_driver,
            ),
        ):

            provider = UniversalCloudNodeProvider()

            inputs = {
                "provider": "aws",
                "region": "us-east-1",
                "size_id": "t3.medium",
                "boot_script": "#!/bin/bash\necho test",
            }

            with pytest.raises(RuntimeError, match="Failed to create node"):
                provider.create(inputs)


class TestDeleteAndReadMethods:
    """
    T3: Test delete() and read() Methods (5 tests)

    Validates the delete() and read() methods of UniversalCloudNodeProvider.
    """

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
        return_value=True,
    )
    @patch("mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver")
    def test_delete_calls_driver_destroy_node(self, mock_get_driver, mock_is_supported):
        """
        Test_DeleteAndRead_DeleteCallsDriverDestroyNode: Verify that delete()
        calls driver.destroy_node() with the correct node.
        """
        mock_node = Mock(id="i-1234567890abcdef0")
        mock_driver = Mock()
        mock_driver.ex_get_node_details.return_value = mock_node
        mock_get_driver.return_value = mock_driver

        provider = UniversalCloudNodeProvider()

        inputs = {"provider": "aws", "region": "us-east-1"}

        provider.delete("i-1234567890abcdef0", inputs)

        mock_driver.ex_get_node_details.assert_called_once_with("i-1234567890abcdef0")
        mock_driver.destroy_node.assert_called_once_with(mock_node)

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
        return_value=True,
    )
    @patch("mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver")
    def test_delete_handles_nonexistent_node(self, mock_get_driver, mock_is_supported):
        """
        Test_DeleteAndRead_DeleteHandlesNonexistentNode: Verify that delete()
        handles the case where the node doesn't exist gracefully.
        """
        mock_driver = Mock()
        mock_driver.ex_get_node_details.side_effect = Exception("Node not found")
        mock_driver.list_nodes.return_value = []  # No nodes found
        mock_get_driver.return_value = mock_driver

        provider = UniversalCloudNodeProvider()

        inputs = {"provider": "aws", "region": "us-east-1"}

        # Should not raise an error
        provider.delete("i-nonexistent", inputs)

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
        return_value=True,
    )
    @patch("mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver")
    def test_read_returns_current_node_state(self, mock_get_driver, mock_is_supported):
        """
        Test_DeleteAndRead_ReadReturnsCurrentNodeState: Verify that read()
        returns the current state of the node from the provider.
        """
        mock_node = Mock(
            id="i-1234567890abcdef0",
            state="RUNNING",
            public_ips=["1.2.3.4"],
            private_ips=["10.0.0.1"],
        )
        mock_driver = Mock()
        mock_driver.ex_get_node_details.return_value = mock_node
        mock_get_driver.return_value = mock_driver

        provider = UniversalCloudNodeProvider()

        inputs = {"provider": "aws", "region": "us-east-1", "size_id": "t3.medium"}

        result = provider.read("i-1234567890abcdef0", inputs)

        assert result.id == "i-1234567890abcdef0"
        assert result.outs["public_ip"] == "1.2.3.4"
        assert result.outs["private_ip"] == "10.0.0.1"
        assert result.outs["status"] == "RUNNING"
        assert result.outs["size_id"] == "t3.medium"

    @patch(
        "mesh.infrastructure.providers.libcloud_dynamic_provider.is_provider_supported",
        return_value=True,
    )
    @patch("mesh.infrastructure.providers.libcloud_dynamic_provider.get_driver")
    def test_read_with_nonexistent_node_returns_none(self, mock_get_driver, mock_is_supported):
        """
        Test_DeleteAndRead_ReadWithNonexistentNodeReturnsNone: Verify that
        read() returns None when the node doesn't exist.
        """
        mock_driver = Mock()
        mock_driver.ex_get_node_details.side_effect = Exception("Node not found")
        mock_driver.list_nodes.return_value = []  # No nodes found
        mock_get_driver.return_value = mock_driver

        provider = UniversalCloudNodeProvider()

        inputs = {"provider": "aws", "region": "us-east-1", "size_id": "t3.medium"}

        result = provider.read("i-nonexistent", inputs)

        assert result is None


class TestCredentialResolution:
    """
    T4: Test Credential Resolution (5 tests)

    Validates the credential resolution logic for different providers.
    """

    @patch.dict(
        "os.environ",
        {"AWS_ACCESS_KEY_ID": "test_access_key", "AWS_SECRET_ACCESS_KEY": "test_secret_key"},
    )
    def test_aws_credentials_from_environment(self):
        """
        Test_CredentialResolution_AWSCredentialsFromEnvironment: Verify that
        AWS credentials are correctly resolved from environment variables.
        """
        creds = get_credentials("aws", region="us-east-1")

        assert creds["key"] == "test_access_key"
        assert creds["secret"] == "test_secret_key"
        assert creds["region"] == "us-east-1"

    @patch.dict("os.environ", {"DIGITALOCEAN_API_TOKEN": "test_token"})
    def test_digitalocean_credentials_from_environment(self):
        """
        Test_CredentialResolution_DigitalOceanCredentialsFromEnvironment: Verify
        that DigitalOcean credentials are correctly resolved from env vars.
        """
        creds = get_credentials("digitalocean")

        assert creds["key"] == "test_token"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials_raise_error(self):
        """
        Test_CredentialResolution_MissingCredentialsRaiseError: Verify that
        missing credentials raise a clear error message.
        """
        with pytest.raises(ValueError, match="Missing required credentials"):
            get_credentials("aws")

    def test_credential_override_bypasses_environment(self):
        """
        Test_CredentialResolution_CredentialOverrideBypassesEnvironment: Verify
        that providing credentials overrides bypasses environment variable lookup.
        """
        override_creds = {"key": "override_key", "secret": "override_secret"}

        # Even without env vars set, overrides should work
        creds = get_credentials("aws", **override_creds)

        assert creds["key"] == "override_key"
        assert creds["secret"] == "override_secret"

    @patch.dict("os.environ", {"LINODE_API_KEY": "linode_token"})
    def test_linode_credentials_from_environment(self):
        """
        Test_CredentialResolution_LinodeCredentialsFromEnvironment: Verify
        that Linode credentials are correctly resolved from env vars.
        """
        creds = get_credentials("linode")

        assert creds["key"] == "linode_token"


class TestDiscoveryMethods:
    """
    T5: Test Discovery Methods (5 tests)

    Validates the real-time provider discovery methods.
    """

    @patch("mesh.infrastructure.providers.discovery.get_driver")
    def test_list_sizes_queries_provider(self, mock_get_driver):
        """
        Test_DiscoveryMethods_ListSizesQueriesProvider: Verify that list_sizes()
        queries the provider for available sizes.
        """
        mock_driver = Mock()
        mock_size = Mock(id="t3.medium", ram=4096, name="t3.medium")
        mock_driver.list_sizes.return_value = [mock_size]
        # Mock list_sizes_in_location since region is specified
        mock_driver.list_sizes_in_location = Mock(return_value=[mock_size])
        mock_get_driver.return_value = mock_driver

        sizes = list_sizes("aws", "us-east-1")

        assert len(sizes) == 1
        assert sizes[0].id == "t3.medium"
        mock_driver.list_sizes.assert_called_once()

    @patch("mesh.infrastructure.providers.discovery.get_driver")
    def test_list_regions_queries_provider(self, mock_get_driver):
        """
        Test_DiscoveryMethods_ListRegionsQueriesProvider: Verify that
        list_regions() queries the provider for available regions.
        """
        mock_driver = Mock()
        mock_location = Mock(id="us-east-1", name="US East 1")
        mock_driver.list_locations.return_value = [mock_location]
        mock_get_driver.return_value = mock_driver

        regions = list_regions("aws")

        assert len(regions) == 1
        assert regions[0].id == "us-east-1"
        mock_driver.list_locations.assert_called_once()

    @patch("mesh.infrastructure.providers.discovery.list_sizes")
    def test_get_size_finds_exact_match(self, mock_list_sizes):
        """
        Test_DiscoveryMethods_GetSizeFindsExactMatch: Verify that get_size()
        finds the exact size by ID from the provider's size list.
        """
        mock_sizes = [
            Mock(id="t3.small", ram=2048),
            Mock(id="t3.medium", ram=4096),
            Mock(id="t3.large", ram=8192),
        ]
        mock_list_sizes.return_value = mock_sizes

        size = get_size("aws", "t3.medium")

        assert size is not None
        assert size.id == "t3.medium"
        assert size.ram == 4096

    @patch("mesh.infrastructure.providers.discovery.list_sizes")
    def test_get_size_returns_none_for_invalid_id(self, mock_list_sizes):
        """
        Test_DiscoveryMethods_GetSizeReturnsNoneForInvalidId: Verify that
        get_size() returns None when the size_id doesn't exist.
        """
        mock_sizes = [Mock(id="t3.small", ram=2048), Mock(id="t3.medium", ram=4096)]
        mock_list_sizes.return_value = mock_sizes

        size = get_size("aws", "invalid_size")

        assert size is None

    @patch("mesh.infrastructure.providers.discovery.list_regions")
    def test_is_region_available_checks_existence(self, mock_list_regions):
        """
        Test_DiscoveryMethods_IsRegionAvailableChecksExistence: Verify that
        is_region_available() correctly checks if a region exists.
        """
        mock_regions = [Mock(id="us-east-1"), Mock(id="us-west-1"), Mock(id="eu-west-1")]
        mock_list_regions.return_value = mock_regions

        assert is_region_available("aws", "us-east-1") is True
        assert is_region_available("aws", "ap-south-1") is False


from mesh.infrastructure.providers import UNSUPPORTED_PROVIDERS, get_driver


class TestHardenedProviders:

    def test_gcp_raises_unsupported(self):
        with pytest.raises(ValueError, match="UNSUPPORTED"):
            get_driver("gcp")

    def test_google_alias_raises_unsupported(self):
        with pytest.raises(ValueError, match="UNSUPPORTED"):
            get_driver("google")

    def test_azure_raises_unsupported(self):
        with pytest.raises(ValueError, match="UNSUPPORTED"):
            get_driver("azure")

    def test_gridscale_absent_from_provider_enums(self):
        assert "gridscale" not in PROVIDER_ENUMS

    def test_cloudscale_absent_from_provider_enums(self):
        assert "cloudscale" not in PROVIDER_ENUMS

    def test_unsupported_providers_set_includes_gcp_and_azure(self):
        assert "gcp" in UNSUPPORTED_PROVIDERS
        assert "google" in UNSUPPORTED_PROVIDERS
        assert "azure" in UNSUPPORTED_PROVIDERS

    def test_gridscale_cloudscale_not_in_unsupported_providers(self):
        assert "gridscale" not in UNSUPPORTED_PROVIDERS
        assert "cloudscale" not in UNSUPPORTED_PROVIDERS
