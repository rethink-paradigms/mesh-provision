# Contributing to Mesh

Thanks for your interest! This repo is the open-source core of the Mesh
platform. Enterprise features (GPU, monitoring, backups, AI agent
orchestration) live in a separate `mesh-enterprise` package that registers
plugins via entry points — see `src/mesh/cli/plugins.py` for the integration
surface.

## Development setup

Requires Python 3.11+.

> **Workspace:** This repo is part of the Mesh workspace.
> From workspace root:
> ```bash
> infisical run -- pip install -e code/mesh-provision/[dev]
> infisical run -- bash code/mesh-provision/run_tests.sh
> ```
> See [`SERVICES.md`](../../SERVICES.md).

For standalone development:

```bash
git clone https://github.com/rethink-paradigms/mesh.git
cd mesh
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

For local cluster testing, install [Multipass](https://multipass.run/).

## Running tests

```bash
# Unit + collection tests (fast)
pytest src/mesh -m "not e2e and not integration and not cloud_only"

# Everything except live-cluster E2E
./run_tests.sh

# Run the E2E suite (requires a running local cluster)
RUN_E2E=1 ./run_tests.sh
```

## Project layout

Vertical slice by domain — each feature owns its tests and a `CONTEXT.md`
file describing its interface, inputs, outputs, and dependencies.

```
src/mesh/
├── cli/              # `mesh` CLI commands and plugin discovery
├── infrastructure/   # provision_node, boot_consul_nomad, providers, …
├── workloads/        # deploy_app, deploy_lite_*, deploy_traefik, …
└── verification/     # E2E suites: lite mode, multi-node, app deployment
```

Before modifying a feature, read its `CONTEXT.md`. When adding a feature,
write the `CONTEXT.md` first — it is the design contract.

## Pull requests

- Keep each PR focused on one logical change. Split refactors from
  behavior changes.
- Include tests for new behavior. Co-locate them with the feature
  (`test_<thing>.py` next to `<thing>.py`).
- Follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(scope):`, `fix(scope):`, `refactor(scope):`, `docs:`, `test:`,
  `chore:`.
- Run `pytest src/mesh -m "not e2e"` locally before pushing; CI will run
  the same suite.

## Memory budget

The control plane targets ~530MB RAM total. New components should justify
their RAM cost; the platform is deliberately lightweight.

## Reporting bugs & security issues

- Bugs: open an issue at
  [github.com/rethink-paradigms/mesh/issues](https://github.com/rethink-paradigms/mesh/issues).
- Security: please do not open public issues. Use GitHub's private
  vulnerability reporting — see [SECURITY.md](SECURITY.md).

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). In short: be kind, assume good
faith, and critique the code, not the author.
