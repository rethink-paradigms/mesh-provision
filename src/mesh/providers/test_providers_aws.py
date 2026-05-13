"""Tests for AWS provider — credential handling (key:secret format)."""

import pytest
from unittest.mock import patch, MagicMock

from mesh.providers import get_driver, is_provider_usable


class TestAWSDriverInit:
    @patch("mesh.providers._libcloud_get_driver")
    def test_aws_init_with_colon_format(self, mock_get_driver):
        mock_driver_class = MagicMock()
        mock_get_driver.return_value = mock_driver_class
        get_driver("aws", api_key="AKIATEST:secretkey", region="us-east-1")
        mock_driver_class.assert_called_once_with("AKIATEST", "secretkey", region="us-east-1")

    @patch("mesh.providers._libcloud_get_driver")
    def test_aws_init_with_env_secret(self, mock_get_driver):
        mock_driver_class = MagicMock()
        mock_get_driver.return_value = mock_driver_class
        with patch.dict("os.environ", {"AWS_SECRET_ACCESS_KEY": "mysecret"}):
            get_driver("aws", api_key="AKIATEST", region="us-east-1")
        mock_driver_class.assert_called_once_with("AKIATEST", "mysecret", region="us-east-1")

    def test_aws_missing_secret_raises(self):
        import os
        with patch.dict("os.environ", {}, clear=True):
            os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
            with pytest.raises(ValueError, match="secret"):
                get_driver("aws", api_key="AKIATEST", region="us-east-1")
