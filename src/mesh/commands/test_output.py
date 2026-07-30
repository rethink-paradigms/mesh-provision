"""Tests for the output module (JSON serialization helpers)."""

import json
import pytest

from mesh.commands.output import (
    print_json_success,
    print_json_error,
    require_args,
    init_success,
    destroy_success,
    add_worker_success,
    status_success,
    demo_init,
    demo_destroy,
    demo_add_worker,
)


class TestPrintJsonSuccess:
    def test_writes_to_stdout_and_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc:
            print_json_success({"key": "value"})
        assert exc.value.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"key": "value"}


class TestPrintJsonError:
    def test_writes_to_stderr_and_exits_1(self, capsys):
        with pytest.raises(SystemExit) as exc:
            print_json_error(code="test_error", message="something failed")
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "test_error"
        assert err["error"]["message"] == "something failed"

    def test_optional_fields_included_when_provided(self, capsys):
        with pytest.raises(SystemExit):
            print_json_error(
                code="missing_required_args",
                message="Missing: x",
                missing_args=["x", "y"],
                phase="init",
            )
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["missing_args"] == ["x", "y"]
        assert err["error"]["phase"] == "init"

    def test_optional_fields_absent_when_not_provided(self, capsys):
        with pytest.raises(SystemExit):
            print_json_error(code="c", message="m")
        err = json.loads(capsys.readouterr().err)
        assert "phase" not in err["error"]
        assert "missing_args" not in err["error"]


class TestRequireArgs:
    def test_passes_when_all_present(self):
        # Should not raise
        require_args("test", {"a": "1", "b": "2"}, "a", "b")

    def test_exits_when_missing(self, capsys):
        with pytest.raises(SystemExit) as exc:
            require_args("test", {"a": "1"}, "a", "b", "c")
        assert exc.value.code == 1
        err = json.loads(capsys.readouterr().err)
        assert err["error"]["code"] == "missing_required_args"
        assert "b" in err["error"]["missing_args"]
        assert "c" in err["error"]["missing_args"]

    def test_empty_string_counts_as_missing(self, capsys):
        with pytest.raises(SystemExit):
            require_args("test", {"a": ""}, "a")
        err = json.loads(capsys.readouterr().err)
        assert "a" in err["error"]["missing_args"]


class TestResponseBuilders:
    def test_init_success_shape(self):
        result = init_success("my-cluster", "1.2.3.4", "ready",
                              [{"id": "x", "ip": "1.2.3.4", "role": "leader"}])
        assert result["cluster_id"] == "my-cluster"
        assert result["leader_ip"] == "1.2.3.4"
        assert result["status"] == "ready"
        assert result["nodes"][0]["role"] == "leader"

    def test_destroy_success_shape(self):
        result = destroy_success("c", ["id-1"])
        assert result["status"] == "destroyed"
        assert result["destroyed"] is True
        assert "id-1" in result["resources_cleaned"]

    def test_add_worker_success_shape(self):
        result = add_worker_success("9.9.9.9", "drop-99")
        assert result["node"]["ip"] == "9.9.9.9"
        assert result["node"]["role"] == "worker"

    def test_status_success_shape(self):
        result = status_success("c", True, [{"id": "1", "ip": "x", "role": "leader"}])
        assert result["exists"] is True
        assert result["cluster_name"] == "c"

    def test_demo_init_has_demo_flag(self):
        result = demo_init("c", "digitalocean", "nyc3", 0, "s-2vcpu-4gb")
        assert result["demo"] is True
        assert result["cluster_id"] == "c"

    def test_demo_destroy_has_demo_flag(self):
        result = demo_destroy("c")
        assert result["demo"] is True
        assert result["destroyed"] is True

    def test_demo_add_worker_has_demo_flag(self):
        result = demo_add_worker()
        assert result["demo"] is True
        assert result["node"]["role"] == "worker"
