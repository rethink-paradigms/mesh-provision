"""Regression tests: JSON mode must not break interactive mode, and vice versa.

Tests 1-3: Interactive mode (no JSON flags) — verify Rich text, no JSON leakage.
Tests 4-6: JSON mode (--output json) — verify Rich text absent, success mock called.

These tests guard against regressions where adding JSON output support could
silently change the behavior of the interactive/plain-text code paths.
"""

from unittest.mock import patch

from typer.testing import CliRunner

from mesh.cli.main import app

runner = CliRunner()


class TestInteractiveNoRegression:
    """Interactive (non-JSON) mode should behave the same as before JSON support."""

    def test_init_no_flags_non_tty_graceful(self):
        """Plain `mesh init` in non-TTY should exit gracefully, not crash.

        CliRunner provides a non-TTY environment.  The init wizard uses
        questionary which returns None without a TTY, causing a clean
        typer.Exit(1).  The regression we guard against: JSON routing
        changes must not alter this graceful non-TTY behaviour.
        """
        result = runner.invoke(app, ["init"])
        assert result.exit_code in (0, 1)
        if result.exit_code == 1:
            assert any(
                word in result.stdout
                for word in ("Aborted", "Cancelled", "non-interactive")
            )

    def test_init_demo_yes_no_json_output(self):
        """`mesh init --demo --yes` uses Rich text, never JSON."""
        result = runner.invoke(app, ["init", "--demo", "--yes"])
        assert result.exit_code == 0
        assert '"cluster_id"' not in result.stdout
        assert "Cluster Configuration" in result.stdout or "Cluster is ready!" in result.stdout

    def test_interactive_demo_yes_no_json_fields(self):
        """Interactive mode must never leak JSON field names into stdout."""
        result = runner.invoke(app, ["init", "--demo", "--yes"])
        assert result.exit_code == 0
        assert '"cluster_id"' not in result.stdout
        assert '"leader_ip"' not in result.stdout
        assert '"nodes"' not in result.stdout


# ---------------------------------------------------------------------------
# JSON mode tests (--output json flag)
# These MUST mock print_json_success / print_json_error because they call
# sys.exit(0) / sys.exit(1) internally.
# ---------------------------------------------------------------------------

class TestJsonModeNoRegression:
    """JSON (--output json) mode must not leak Rich / interactive UI text."""

    @patch("mesh.cli.commands.init_json.print_json_success")
    @patch("mesh.cli.commands.init_json.print_json_error")
    def test_init_json_demo_no_rich_output(self, mock_error, mock_success):
        """`mesh init --output json --demo ...` uses JSON, not Rich text."""
        result = runner.invoke(
            app,
            [
                "init", "--output", "json", "--demo",
                "--api-key", "test123",
                "--leader-size", "s-2vcpu-4gb",
                "--cluster-name", "regr",
                "--region", "nyc3",
            ],
        )
        mock_success.assert_called_once()
        mock_error.assert_not_called()
        assert "Cluster Configuration" not in result.stdout
        assert "Cluster is ready!" not in result.stdout
        assert "Provisioning" not in result.stdout

    def test_destroy_no_flags_non_tty_graceful(self):
        """Plain `mesh destroy` in non-TTY should exit gracefully, not crash.

        The destroy command detects non-TTY and shows an informational
        message.  JSON routing must not change this behaviour.
        """
        result = runner.invoke(app, ["destroy"])
        assert result.exit_code in (0, 1)
        if result.exit_code == 0:
            assert "Cancelled" in result.stdout or "yes" in result.stdout.lower()
        elif result.exit_code == 1:
            assert "Cancelled" in result.stdout or "non-interactive" in result.stdout.lower()

    @patch("mesh.cli.commands.json_output.print_json_success")
    def test_destroy_json_demo_no_rich_output(self, mock_success):
        """`mesh destroy --output json --demo ...` uses JSON, not Rich text."""
        result = runner.invoke(
            app,
            ["destroy", "--output", "json", "--demo", "--api-key", "test123"],
        )
        mock_success.assert_called_once()
        assert "Cluster Configuration" not in result.stdout
        assert "Are you sure" not in result.stdout
        assert "⚠" not in result.stdout
