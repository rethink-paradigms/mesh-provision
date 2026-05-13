"""Tests for DigitalOcean provider — driver init, credential resolution."""

import pytest
from unittest.mock import patch, MagicMock

from mesh.providers import get_driver, is_provider_usable, USABLE_PROVIDERS


class TestProviderRegistry:
    def test_digitalocean_is_usable(self):
        assert is_provider_usable("digitalocean")
        assert is_provider_usable("do")

    def test_gcp_is_not_usable(self):
        assert not is_provider_usable("gcp")

    def test_azure_is_not_usable(self):
        assert not is_provider_usable("azure")

    def test_unknown_is_not_usable(self):
        assert not is_provider_usable("madeupcloud")

    def test_usable_providers_list(self):
        assert "digitalocean" in USABLE_PROVIDERS
        assert "aws" in USABLE_PROVIDERS
        assert "gcp" not in USABLE_PROVIDERS


class TestDigitalOceanDriverInit:
    @patch("mesh.providers._libcloud_get_driver")
    def test_do_driver_init_with_token(self, mock_get_driver):
        mock_driver_class = MagicMock()
        mock_get_driver.return_value = mock_driver_class
        get_driver("digitalocean", api_key="dop_v1_test")
        mock_driver_class.assert_called_once_with("dop_v1_test")

    def test_do_no_key_no_env_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            import os
            for var in ["DIGITALOCEAN_API_TOKEN", "DO_PAT", "DO_API_TOKEN"]:
                os.environ.pop(var, None)
            with pytest.raises(ValueError, match="No API key"):
                get_driver("digitalocean", api_key="")

    @patch("mesh.providers._libcloud_get_driver")
    def test_do_falls_back_to_env_var(self, mock_get_driver):
        mock_driver_class = MagicMock()
        mock_get_driver.return_value = mock_driver_class
        with patch.dict("os.environ", {"DIGITALOCEAN_API_TOKEN": "env-token"}):
            get_driver("digitalocean", api_key="")
        mock_driver_class.assert_called_once_with("env-token")

    def test_unsupported_provider_raises(self):
        with pytest.raises(ValueError, match="not supported"):
            get_driver("gcp", api_key="somekey")

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_driver("nonexistent", api_key="k")
