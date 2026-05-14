"""Tests for poll_daemon_health() in mesh.provisioning.direct."""

import urllib.error
from unittest.mock import MagicMock, patch, call

import pytest

from mesh.provisioning.direct import poll_daemon_health


class TestPollDaemonHealth:
    """Unit tests for poll_daemon_health() — all urllib.request calls are mocked."""

    def test_poll_returns_true_on_200(self):
        """Returns True immediately when the first call returns HTTP 200."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("time.sleep"):
            result = poll_daemon_health("1.2.3.4", timeout=10, interval=5)

        assert result is True

    def test_poll_returns_false_on_timeout(self):
        """Returns False after timeout when urlopen always raises URLError."""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")), \
             patch("time.sleep"):
            result = poll_daemon_health("1.2.3.4", timeout=10, interval=5)

        assert result is False

    def test_poll_retries_until_success(self):
        """Returns True after initial failures when a 200 eventually comes."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        side_effects = [
            urllib.error.URLError("refused"),
            urllib.error.URLError("refused"),
            mock_resp,
        ]
        with patch("urllib.request.urlopen", side_effect=side_effects), \
             patch("time.sleep"):
            result = poll_daemon_health("1.2.3.4", timeout=15, interval=5)

        assert result is True

    def test_poll_handles_non_200(self):
        """Non-200 responses are treated as not-ready; returns False on timeout."""
        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("time.sleep"):
            result = poll_daemon_health("1.2.3.4", timeout=10, interval=5)

        assert result is False
