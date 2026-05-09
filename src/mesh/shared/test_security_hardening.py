import pathlib
import re

import pytest

_MESH_PROVISION = pathlib.Path(__file__).parents[3]

_SCRIPTS = [
    _MESH_PROVISION / "src/mesh/infrastructure/boot_consul_nomad/boot.sh",
    _MESH_PROVISION / "src/mesh/infrastructure/boot_consul_nomad/scripts/02-install-tailscale.sh",
    _MESH_PROVISION / "src/mesh/infrastructure/boot_consul_nomad/scripts/10-install-caddy.sh",
    _MESH_PROVISION / "scripts/mesh-install.sh",
]

_CURL_PIPE_EXEC = re.compile(r"curl\b.*\|\s*(?:bash|sh)\b")


def _find_curl_pipe_exec(path: pathlib.Path) -> list[str]:
    return [
        line.rstrip()
        for line in path.read_text().splitlines()
        if _CURL_PIPE_EXEC.search(line) and not line.lstrip().startswith("#")
    ]


class TestNoCurlBashPatterns:

    @pytest.mark.parametrize("script", _SCRIPTS, ids=[p.name for p in _SCRIPTS])
    def test_no_curl_pipe_bash_or_sh(self, script):
        matches = _find_curl_pipe_exec(script)
        assert matches == [], (
            f"curl|bash/sh pattern found in {script.relative_to(_MESH_PROVISION)}:\n"
            + "\n".join(f"  {m}" for m in matches)
        )
