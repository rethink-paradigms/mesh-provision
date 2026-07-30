# Commit Restructure + Towncrier Changelog Setup

## TL;DR

> **Quick Summary**: Split the mega-commit (7347f7c, 41 files) into 14 atomic conventional commits in dependency order, set up Towncrier for fragment-based changelog management, and generate the v0.4.0 changelog.
>
> **Deliverables**:
> - 14 atomic git commits replacing the single mega-commit
> - Towncrier installed and configured in pyproject.toml
> - Fragment files created for each logical change
> - CHANGELOG.md updated with v0.4.0 entries
> - Version bumped from 0.3.0 → 0.4.0
>
> **Estimated Effort**: Medium
> **Parallel Execution**: NO — strictly sequential (git history ordering)
> **Critical Path**: Backup → Reset → Towncrier setup → 11 feature commits → Changelog build → Version bump

---

## Context

### Original Request
User wants to: (1) review and make proper atomic commits from the current mega-commit, (2) add a changelog system so agents can track what changed as the product evolves.

### Interview Summary
**Key Discussions**:
- **Version bump**: 0.4.0 (minor) — snapshots and install script are significant new features
- **Changelog system**: Towncrier fragments — user chose structured approach over simple append
- **Commit order**: Must follow dependency DAG — each commit must leave tests passing
- **Scope**: Only git operations + changelog setup. No new features, no refactoring.

**Research Findings**:
- Towncrier config goes in `[tool.towncrier]` in pyproject.toml
- Fragment types map to Keep a Changelog: Added, Changed, Fixed, Removed, Deprecated, Security
- Fragment format: `+<slug>.<type>.md` (orphan) or `<issue>.<type>.md`
- Need magic comment in CHANGELOG.md: `<!-- towncrier release notes start -->`
- `towncrier build` compiles fragments, inserts into CHANGELOG.md, deletes fragments

### Metis Review
**Identified Gaps** (addressed):
- **Dependency ordering**: CLI commands MUST be committed after snapshot engine (import dependency)
- **e2e_lite_mode tests**: Traefik-related test fixes MUST be in the Traefik-stripping commit (not separate)
- **deploy_app tests**: tier_config changes MUST include test_deploy_app.py in same commit
- **main.py coupling**: snapshot.py + main.py registration MUST be in same commit
- **Backup branch**: Create `backup-7347f7c` before reset as safety net
- **Test verification**: Run pytest after key commits (2, 3, 7, 8, 11, 14) to verify no breakage
- **Towncrier first**: Setup must be first commit so fragments can reference it
- **Content preservation**: `git diff 7347f7c HEAD` must be empty at end

---

## Work Objectives

### Core Objective
Replace the single mega-commit with 14 atomic conventional commits in correct dependency order, set up Towncrier for ongoing changelog management, and generate the v0.4.0 changelog.

### Concrete Deliverables
- 14 atomic commits with conventional commit messages
- Towncrier config in pyproject.toml
- `changelog.d/` directory with fragment files
- Updated CHANGELOG.md with v0.4.0 section
- Version bumped to 0.4.0 in pyproject.toml

### Definition of Done
- [x] `git log --oneline HEAD~14..HEAD` shows 14 clean conventional commits
- [x] `git diff 7347f7c HEAD` is empty (content preserved)
- [x] `pytest --tb=short -q` passes after the final commit
- [x] `towncrier build --draft --version 0.4.0` produces expected output
- [x] CHANGELOG.md contains v0.4.0 section with all MVP changes
- [x] `pyproject.toml` version is "0.4.0"
- [x] No fragment files remain in `changelog.d/` after build

### Must Have
- Backup branch before reset
- Each intermediate commit passes pytest (at dependency checkpoints)
- Towncrier fragment types match Keep a Changelog categories
- Magic comment in CHANGELOG.md for towncrier insertion point
- Conventional commit messages matching project style

### Must NOT Have (Guardrails)
- **NO `git push`** until ALL commits verified
- **NO new code** — only reorganizing existing changes
- **NO test refactoring** beyond what the mega-commit already changed
- **NO CI towncrier checks** — out of scope for this plan
- **NO fragments for v0.3.0** entries — only for the new v0.4.0 changes
- **NO modification of `.sisyphus/` file contents** — commit as-is
- **NO version bump before changelog build** — order matters

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Automated tests**: NO new tests — existing test suite validates correctness
- **Verification**: Run `pytest` at dependency checkpoints + final verification

### QA Policy
Every task includes shell-command verification.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Sequential Execution (NO parallelism — git history must be linear)

```
Step 0 (Preparation):
├── Task 0: Verify mega-commit tests pass + create backup branch [quick]

Step 1 (Foundation — towncrier + types):
├── Task 1: Towncrier setup (install, config, magic comment, fragments) [quick]
├── Task 2: Shared types commit [quick]

Step 2 (Core changes — stripping + scaffolding):
├── Task 3: Strip Traefik/INGRESS/PRODUCTION commit [unspecified-high]
├── Task 4: Snapshot scaffold CONTEXT.md commit [quick]
├── Task 5: Install script commit [quick]
├── Task 6: Deploy hardening commit [quick]

Step 3 (Feature modules — snapshots + CLI):
├── Task 7: Snapshot engine + storage commit [unspecified-high]
├── Task 8: CLI snapshot commands commit (includes main.py) [quick]

Step 4 (Tests + cleanup):
├── Task 9: Install integration test commit [quick]
├── Task 10: E2E MVP test commit [quick]
├── Task 11: Demo mode cleanup commit [quick]
├── Task 12: Sisyphus planning files commit [quick]

Step 5 (Release):
├── Task 13: Towncrier build + changelog generation [quick]
├── Task 14: Version bump to 0.4.0 [quick]

Step FINAL:
├── Task F1: Content preservation check (diff against mega-commit)
├── Task F2: Test suite full run
├── Task F3: Commit history review
```

### Dependency Matrix

| Task | Depends On | Blocks | Test Checkpoint |
|------|-----------|--------|----------------|
| 0 | — | 1-14 | YES (baseline) |
| 1 | 0 | 13 | NO (config only) |
| 2 | 0 | 7 | YES |
| 3 | 0 | 6, 11 | YES |
| 4 | 0 | 7 | NO (docs only) |
| 5 | 0 | 9 | NO (standalone scripts) |
| 6 | 3 | — | YES |
| 7 | 2, 4 | 8 | YES |
| 8 | 7 | — | YES |
| 9 | 5 | — | NO (standalone tests) |
| 10 | 7, 8 | — | NO (standalone tests) |
| 11 | 3 | — | YES |
| 12 | — | — | NO (planning files) |
| 13 | 1-12 | 14 | YES |
| 14 | 13 | — | YES |

### Agent Dispatch Summary

- **Step 0**: 1 task — T0 → `quick`
- **Step 1**: 2 tasks — T1 → `quick`, T2 → `quick`
- **Step 2**: 4 tasks — T3 → `unspecified-high`, T4 → `quick`, T5 → `quick`, T6 → `quick`
- **Step 3**: 2 tasks — T7 → `unspecified-high`, T8 → `quick`
- **Step 4**: 4 tasks — T9-T12 → `quick`
- **Step 5**: 2 tasks — T13 → `quick`, T14 → `quick`
- **FINAL**: 3 tasks — F1-F3 → `quick`

---

## TODOs

- [x] 0. **Verify Baseline + Create Backup Branch**

  **What to do**:
  - Run `pytest --tb=short -q` on current HEAD (mega-commit 7347f7c) to verify tests pass
  - Create backup branch: `git branch backup-7347f7c 7347f7c`
  - Record baseline test numbers (should be ~507 pass, 76 fail pre-existing, 9 skip)
  - Soft reset: `git reset --soft HEAD~1` — stages all 41 files for re-commit
  - Verify staging: `git diff --cached --stat` should show same 41 files

  **Must NOT do**:
  - Do NOT push anything
  - Do NOT modify any files
  - Do NOT use `--hard` reset

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: ALL subsequent tasks
  - **Blocked By**: None

  **References**:
  - Git history: `7347f7c` is the mega-commit to split
  - Branch: `feat/v0.3.0-release-readiness`, ahead 1 commit

  **Acceptance Criteria**:
  - [ ] `git branch backup-7347f7c` exists and points to 7347f7c
  - [ ] `git diff --cached --stat` shows 41 files staged
  - [ ] `git status` shows HEAD is now `9fd3732` (parent of mega-commit)

  **QA Scenarios:**
  ```
  Scenario: Backup branch exists
    Tool: Bash
    Steps:
      1. Run: `git branch --list backup-7347f7c`
      2. Assert: output contains "backup-7347f7c"
    Expected Result: Backup branch exists as safety net
    Evidence: .sisyphus/evidence/task-0-backup.txt

  Scenario: All files staged after soft reset
    Tool: Bash
    Steps:
      1. Run: `git diff --cached --stat | tail -1`
      2. Assert: output contains "41 files changed"
    Expected Result: All 41 files from mega-commit are staged
    Evidence: .sisyphus/evidence/task-0-staged.txt
  ```

  **Commit**: NO (preparation step)

- [x] 1. **Towncrier Setup**

  **What to do**:
  - Install towncrier: `pip install towncrier` (add to dev deps in pyproject.toml)
  - Add `[tool.towncrier]` config to pyproject.toml with:
    - `directory = "changelog.d"` — fragment directory
    - `filename = "CHANGELOG.md"` — output file
    - `start_string = "<!-- towncrier release notes start -->\n"` — insertion marker
    - `underlines = ["", "", ""]` — disable RST underlines for Markdown
    - `title_format` matching existing style
    - `issue_format` linking to GitHub issues
    - `name = "rethink-mesh"` — project name
    - Fragment types: Added, Changed, Deprecated, Removed, Fixed, Security (Keep a Changelog order)
  - Add magic comment `<!-- towncrier release notes start -->` to CHANGELOG.md after `[Unreleased]` header
  - Create `changelog.d/` directory
  - Create fragment files for each logical change in the mega-commit:
    - `+shared-types.added.md`: "Add shared type definitions module with SnapshotMetadata, NodeRole, SnapshotStatus enums, and snapshot/Nomad constants."
    - `+strip-traefik.refactor.md`: "Strip broken Traefik automation and INGRESS/PRODUCTION tiers. Remove deploy_traefik/ and deploy_web_service/ modules. Simplify tier system to LITE/STANDARD only."
    - `+snapshot-engine.added.md`: "Add container volume snapshot engine with tar-based create/restore/list/delete operations and local filesystem storage backend."
    - `+install-script.added.md`: "Add interactive mesh-install.sh for 2-VM cluster bootstrap (server + client) via Tailscale mesh networking."
    - `+deploy-hardening.fixed.md`: "Fix NOMAD_ADDR discovery with config file fallback chain (env → ~/.mesh/config → default). Remove silent demo fallbacks from MVP commands."
    - `+cli-snapshots.added.md`: "Add mesh snapshot CLI commands (create/restore/list/delete) with Rich-formatted output."
    - `+e2e-tests.added.md`: "Add MVP golden path E2E test and install script integration tests (125+ new test cases)."
  - Unstage all mega-commit files, then stage ONLY the towncrier setup files
  - Commit: `chore(tooling): set up towncrier for changelog management`

  **Must NOT do**:
  - Do NOT create fragments for v0.3.0 entries
  - Do NOT add CI towncrier checks
  - Do NOT modify existing CHANGELOG.md v0.3.0 content

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 13 (towncrier build)
  - **Blocked By**: Task 0

  **References**:
  - `pyproject.toml` — add [tool.towncrier] after existing [tool.*] sections (~line 140)
  - `CHANGELOG.md` — add magic comment after `## [Unreleased]` (line 8)
  - Towncrier docs: https://towncrier.readthedocs.io/en/latest/tutorial.html
  - Towncrier config: https://towncrier.readthedocs.io/en/latest/configuration.html

  **Acceptance Criteria**:
  - [ ] `changelog.d/` directory exists with 7 fragment files
  - [ ] `pyproject.toml` has `[tool.towncrier]` section with 6 type definitions
  - [ ] `CHANGELOG.md` has `<!-- towncrier release notes start -->` comment
  - [ ] `towncrier build --draft --version 0.4.0` shows all fragments compiled
  - [ ] `grep -c 'towncrier release notes start' CHANGELOG.md` equals 1

  **QA Scenarios:**
  ```
  Scenario: Towncrier config is valid
    Tool: Bash
    Steps:
      1. Run: `towncrier build --draft --version 0.4.0 2>&1 | head -20`
      2. Assert: output shows fragment content (not config error)
    Expected Result: Towncrier reads config and compiles fragments successfully
    Failure Indicators: ConfigError, missing directory, unknown type
    Evidence: .sisyphus/evidence/task-1-towncrier-draft.txt

  Scenario: Fragment files have correct extensions
    Tool: Bash
    Steps:
      1. Run: `ls changelog.d/*.md`
      2. Assert: files match pattern +<slug>.(added|changed|fixed|removed|deprecated|security).md
    Expected Result: All fragment files use Keep a Changelog type extensions
    Evidence: .sisyphus/evidence/task-1-fragments.txt
  ```

  **Commit**: YES
  - Message: `chore(tooling): set up towncrier for changelog management`
  - Files: `pyproject.toml`, `CHANGELOG.md`, `changelog.d/` (7 fragments)
  - Pre-commit: `towncrier build --draft --version 0.4.0`

- [x] 2. **Shared Types Commit**

  **What to do**:
  - Stage and commit: `src/mesh/shared/__init__.py`, `src/mesh/shared/test_types.py`
  - Commit: `feat(types): add shared type definitions module`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (sequential after T1)
  - **Blocks**: Task 7 (snapshot engine imports shared types)
  - **Blocked By**: Task 1

  **References**:
  - `src/mesh/shared/__init__.py` — SnapshotStatus, NodeRole, SnapshotMetadata, constants
  - `src/mesh/shared/test_types.py` — 14 tests

  **Acceptance Criteria**:
  - [ ] `git log --oneline -1` shows `feat(types): add shared type definitions module`
  - [ ] `pytest src/mesh/shared/test_types.py -q` passes

  **QA Scenarios:**
  ```
  Scenario: Types commit is clean
    Tool: Bash
    Steps:
      1. Run: `git diff --stat HEAD~1`
      2. Assert: exactly 2 files changed (shared/__init__.py, shared/test_types.py)
    Expected Result: Only shared type files in this commit
    Evidence: .sisyphus/evidence/task-2-diff.txt
  ```

  **Commit**: YES
  - Message: `feat(types): add shared type definitions module`
  - Files: `src/mesh/shared/__init__.py`, `src/mesh/shared/test_types.py`
  - Pre-commit: `pytest src/mesh/shared/test_types.py`

  **TEST CHECKPOINT**: Run `pytest --tb=short -q` — must pass

- [x] 3. **Strip Traefik/INGRESS/PRODUCTION Commit**

  **What to do**:
  - Stage and commit ALL files related to Traefik stripping as ONE atomic commit:
    - Deleted: `src/mesh/workloads/deploy_traefik/` (5 files: CONTEXT.md, __init__.py, deploy.py, test_deploy.py, traefik.nomad.hcl)
    - Deleted: `src/mesh/workloads/deploy_web_service/` (3 files: CONTEXT.md, test_deploy.py, web_service.nomad.hcl)
    - Modified: `src/mesh/infrastructure/progressive_activation/tier_config.py`
    - Modified: `src/mesh/infrastructure/progressive_activation/tier_manager.py`
    - Modified: `src/mesh/infrastructure/progressive_activation/test_tier_config.py`
    - Modified: `src/mesh/workloads/deploy_app/deploy.py`
    - Modified: `src/mesh/workloads/deploy_app/test_deploy_app.py`
    - Modified: `src/mesh/verification/e2e_lite_mode/test_lite_boot.py`
    - Modified: `src/mesh/verification/e2e_lite_mode/test_lite_memory.py`
    - Modified: `src/mesh/verification/e2e_lite_mode/test_lite_routing.py`
  - Commit: `refactor(tier): strip Traefik and INGRESS/PRODUCTION tiers for MVP`

  **Must NOT do**:
  - Do NOT refactor remaining code beyond what mega-commit changed
  - Do NOT modify deploy_lite_web_service/ (it still exists and works)
  - Do NOT split this into multiple commits — all Traefik-related changes are one logical unit

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 13 files (10 modified + 3 deleted directories), must be staged precisely together
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Tasks 6, 11
  - **Blocked By**: Task 2

  **References**:
  - These files form a single logical unit: removing Traefik support and simplifying tier system
  - e2e_lite_mode test fixes (removing `assert config.enable_traefik is False`) MUST be in this commit

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows ~13 files (10 modified + deletions in 2 dirs)
  - [ ] `grep -r "traefik" src/mesh/ --include="*.py" -l` returns no active imports
  - [ ] `grep -r "INGRESS\|PRODUCTION" src/mesh/infrastructure/progressive_activation/tier_config.py` returns no matches

  **QA Scenarios:**
  ```
  Scenario: No Traefik references remain
    Tool: Bash
    Steps:
      1. Run: `grep -r "traefik" src/mesh/ --include="*.py" -l`
      2. Assert: no results or only comments
      3. Run: `grep -r "INGRESS\|PRODUCTION" src/mesh/infrastructure/progressive_activation/tier_config.py`
      4. Assert: no matches
    Expected Result: All Traefik and broken tier references removed
    Evidence: .sisyphus/evidence/task-3-cleanup.txt
  ```

  **Commit**: YES
  - Message: `refactor(tier): strip Traefik and INGRESS/PRODUCTION tiers for MVP`
  - Files: 13 files as listed above
  - Pre-commit: `pytest src/mesh/infrastructure/progressive_activation/ src/mesh/workloads/deploy_app/`

  **TEST CHECKPOINT**: Run `pytest --tb=short -q` — must pass

- [x] 4. **Snapshot Scaffold CONTEXT.md Commit**

  **What to do**:
  - Stage and commit: `src/mesh/snapshots/CONTEXT.md`
  - Commit: `docs(snapshots): add snapshot engine architecture context`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 7
  - **Blocked By**: Task 3

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows exactly 1 file

  **Commit**: YES
  - Message: `docs(snapshots): add snapshot engine architecture context`
  - Files: `src/mesh/snapshots/CONTEXT.md`

- [x] 5. **Install Script Commit**

  **What to do**:
  - Stage and commit: `scripts/mesh-install.sh`, `scripts/test_mesh_install.py`
  - Commit: `feat(install): add interactive cluster bootstrap script`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 9
  - **Blocked By**: Task 4

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows exactly 2 files
  - [ ] `pytest scripts/test_mesh_install.py -q` passes

  **Commit**: YES
  - Message: `feat(install): add interactive cluster bootstrap script`
  - Files: `scripts/mesh-install.sh`, `scripts/test_mesh_install.py`
  - Pre-commit: `pytest scripts/test_mesh_install.py`

- [x] 6. **Deploy Hardening Commit**

  **What to do**:
  - Stage and commit: `src/mesh/infrastructure/config/env.py`, `src/mesh/cli/commands/test_deploy_hardening.py`
  - Commit: `feat(deploy): harden NOMAD_ADDR discovery with config file fallback`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None directly
  - **Blocked By**: Task 3 (tier changes must be committed first)

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows exactly 2 files
  - [ ] `pytest src/mesh/cli/commands/test_deploy_hardening.py -q` passes

  **QA Scenarios:**
  ```
  Scenario: NOMAD_ADDR discovery works
    Tool: Bash
    Steps:
      1. Run: `pytest src/mesh/cli/commands/test_deploy_hardening.py -q`
      2. Assert: all tests pass
    Expected Result: Config file fallback chain works correctly
    Evidence: .sisyphus/evidence/task-6-deploy.txt
  ```

  **Commit**: YES
  - Message: `feat(deploy): harden NOMAD_ADDR discovery with config file fallback`
  - Files: `src/mesh/infrastructure/config/env.py`, `src/mesh/cli/commands/test_deploy_hardening.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_deploy_hardening.py`

  **TEST CHECKPOINT**: Run `pytest --tb=short -q` — must pass

- [x] 7. **Snapshot Engine + Storage Commit**

  **What to do**:
  - Stage and commit all 4 snapshot implementation files:
    - `src/mesh/snapshots/__init__.py`
    - `src/mesh/snapshots/storage.py`
    - `src/mesh/snapshots/test_snapshots.py`
    - `src/mesh/snapshots/test_storage.py`
  - Commit: `feat(snapshots): implement tar-based volume snapshot engine`

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 4 files, must verify snapshot engine + storage work together
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 8 (CLI commands import from engine)
  - **Blocked By**: Tasks 2, 4

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows exactly 4 files
  - [ ] `pytest src/mesh/snapshots/ -q` passes (53 tests: 23 snapshot + 30 storage)

  **QA Scenarios:**
  ```
  Scenario: Snapshot engine tests pass
    Tool: Bash
    Steps:
      1. Run: `pytest src/mesh/snapshots/ -q`
      2. Assert: all tests pass (0 failures)
    Expected Result: Snapshot create/restore/list/delete and storage operations work
    Evidence: .sisyphus/evidence/task-7-snapshots.txt
  ```

  **Commit**: YES
  - Message: `feat(snapshots): implement tar-based volume snapshot engine`
  - Files: `src/mesh/snapshots/__init__.py`, `src/mesh/snapshots/storage.py`, `src/mesh/snapshots/test_snapshots.py`, `src/mesh/snapshots/test_storage.py`
  - Pre-commit: `pytest src/mesh/snapshots/`

  **TEST CHECKPOINT**: Run `pytest --tb=short -q` — must pass

- [x] 8. **CLI Snapshot Commands Commit**

  **What to do**:
  - Stage and commit (MUST include main.py for registration):
    - `src/mesh/cli/commands/snapshot.py`
    - `src/mesh/cli/commands/test_snapshot_cmd.py`
    - `src/mesh/cli/main.py` (3-line addition: import + add_typer)
  - Commit: `feat(cli): add mesh snapshot create/restore/list/delete commands`

  **Must NOT do**:
  - Do NOT commit main.py separately from snapshot.py — they form a single unit

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 10
  - **Blocked By**: Task 7

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows exactly 3 files
  - [ ] `pytest src/mesh/cli/commands/test_snapshot_cmd.py -q` passes

  **Commit**: YES
  - Message: `feat(cli): add mesh snapshot create/restore/list/delete commands`
  - Files: `src/mesh/cli/commands/snapshot.py`, `src/mesh/cli/commands/test_snapshot_cmd.py`, `src/mesh/cli/main.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_snapshot_cmd.py`

  **TEST CHECKPOINT**: Run `pytest --tb=short -q` — must pass

- [x] 9. **Install Integration Test Commit**

  **What to do**:
  - Stage and commit: `scripts/test_install_integration.py`
  - Commit: `test(install): add integration tests for 2-VM install flow`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: Task 5

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows exactly 1 file
  - [ ] `pytest scripts/test_install_integration.py -q` passes

  **Commit**: YES
  - Message: `test(install): add integration tests for 2-VM install flow`
  - Files: `scripts/test_install_integration.py`
  - Pre-commit: `pytest scripts/test_install_integration.py`

- [x] 10. **E2E MVP Test Commit**

  **What to do**:
  - Stage and commit: `src/mesh/verification/e2e_mvp/__init__.py`, `src/mesh/verification/e2e_mvp/test_mvp_flow.py`
  - Commit: `test(e2e): add MVP golden path end-to-end test suite`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: Tasks 7, 8

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows exactly 2 files

  **Commit**: YES
  - Message: `test(e2e): add MVP golden path end-to-end test suite`
  - Files: `src/mesh/verification/e2e_mvp/__init__.py`, `src/mesh/verification/e2e_mvp/test_mvp_flow.py`

- [x] 11. **Demo Mode Cleanup Commit**

  **What to do**:
  - Stage and commit: `src/mesh/cli/commands/status.py`, `src/mesh/cli/commands/test_status.py`
  - Commit: `refactor(status): remove demo fallback, show error for no cluster`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: Task 3 (tier changes must be committed first)

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows exactly 2 files
  - [ ] `pytest src/mesh/cli/commands/test_status.py -q` passes

  **Commit**: YES
  - Message: `refactor(status): remove demo fallback, show error for no cluster`
  - Files: `src/mesh/cli/commands/status.py`, `src/mesh/cli/commands/test_status.py`
  - Pre-commit: `pytest src/mesh/cli/commands/test_status.py`

  **TEST CHECKPOINT**: Run `pytest --tb=short -q` — must pass

- [x] 12. **Sisyphus Planning Files Commit**

  **What to do**:
  - Stage and commit: `.sisyphus/` directory (6 files)
    - `.sisyphus/plans/mvp-solid.md`
    - `.sisyphus/boulder.json`
    - `.sisyphus/notepads/mvp-solid/decisions.md`
    - `.sisyphus/notepads/mvp-solid/issues.md`
    - `.sisyphus/notepads/mvp-solid/learnings.md`
    - `.sisyphus/notepads/mvp-solid/problems.md`
  - Commit: `chore(planning): add sisyphus planning artifacts for MVP`

  **Must NOT do**:
  - Do NOT modify any file contents — commit as-is
  - Do NOT include `.sisyphus/drafts/` (working files, not permanent)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: None (can be done anytime, but logically last before release)

  **Acceptance Criteria**:
  - [ ] `git diff --stat HEAD~1` shows 6 files

  **Commit**: YES
  - Message: `chore(planning): add sisyphus planning artifacts for MVP`
  - Files: `.sisyphus/` (6 files, excluding drafts/)

- [x] 13. **Towncrier Build + Changelog Generation**

  **What to do**:
  - Run `towncrier build --version 0.4.0 --date $(date +%Y-%m-%d) --yes`
  - This will:
    - Compile all fragments from `changelog.d/`
    - Insert new v0.4.0 section into CHANGELOG.md after the magic comment
    - Delete all fragment files
  - Stage the updated CHANGELOG.md
  - Verify: `grep '\[0.4.0\]' CHANGELOG.md` shows the new section
  - Verify: `ls changelog.d/*.md 2>/dev/null | wc -l` returns 0
  - Commit: `chore(changelog): generate v0.4.0 changelog from towncrier fragments`

  **Must NOT do**:
  - Do NOT manually edit CHANGELOG.md — let towncrier generate it
  - Do NOT skip the `--yes` flag check (review draft output first)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 14
  - **Blocked By**: Tasks 1-12 (all feature commits must be done)

  **Acceptance Criteria**:
  - [ ] `grep -c '\[0.4.0\]' CHANGELOG.md` >= 1
  - [ ] `ls changelog.d/*.md 2>/dev/null | wc -l` equals 0
  - [ ] CHANGELOG.md has sections: Added, Changed, Fixed (at minimum)

  **QA Scenarios:**
  ```
  Scenario: Changelog has all expected sections
    Tool: Bash
    Steps:
      1. Run: `grep '### Added' CHANGELOG.md | wc -l`
      2. Assert: at least 1 match (under [0.4.0])
      3. Run: `grep '### Fixed' CHANGELOG.md | wc -l`
      4. Assert: at least 1 match
    Expected Result: v0.4.0 section has proper Keep a Changelog structure
    Evidence: .sisyphus/evidence/task-13-changelog.txt
  ```

  **Commit**: YES
  - Message: `chore(changelog): generate v0.4.0 changelog from towncrier fragments`
  - Files: `CHANGELOG.md`, `changelog.d/` (deleted fragments)
  - Pre-commit: `towncrier build --draft --version 0.4.0`

  **TEST CHECKPOINT**: Run `pytest --tb=short -q` — must pass

- [x] 14. **Version Bump to 0.4.0**

  **What to do**:
  - Update `pyproject.toml` line 7: `version = "0.3.0"` → `version = "0.4.0"`
  - Stage pyproject.toml
  - Commit: `chore(release): bump version to 0.4.0`

  **Must NOT do**:
  - Do NOT create git tags yet (that happens on merge to main)
  - Do NOT push to remote

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: FINAL verification
  - **Blocked By**: Task 13

  **Acceptance Criteria**:
  - [ ] `grep 'version = "0.4.0"' pyproject.toml` shows 1 match

  **Commit**: YES
  - Message: `chore(release): bump version to 0.4.0`
  - Files: `pyproject.toml`

  **TEST CHECKPOINT**: Run `pytest --tb=short -q` — must pass

---

## Final Verification Wave

- [x] F1. **Content Preservation Check** — `quick`
  Run: `git diff 7347f7c HEAD` — must be empty (same content, different history).
  Also verify: `git log --oneline HEAD~14..HEAD` shows exactly 14 commits.

- [x] F2. **Test Suite Full Run** — `quick`
  Run: `pytest --tb=short -q` — must pass with same results as pre-restructure (507 pass, 76 pre-existing fail).

- [x] F3. **Commit History Review** — `quick`
  Verify: all 14 commits follow conventional format (`type(scope): description`).
  Verify: CHANGELOG.md has v0.4.0 section. Verify: pyproject.toml version is "0.4.0".
  Verify: no fragment files remain in changelog.d/. Verify: `git push` has NOT been run.

---

## Commit Strategy

(Defined in each task below — 14 atomic commits)

---

## Success Criteria

### Verification Commands
```bash
git diff 7347f7c HEAD                    # Expected: empty
git log --oneline HEAD~14..HEAD          # Expected: 14 conventional commits
pytest --tb=short -q                     # Expected: 507 pass, 76 fail (pre-existing)
grep 'version = "0.4.0"' pyproject.toml  # Expected: 1 match
grep '\[0.4.0\]' CHANGELOG.md            # Expected: 1+ matches
ls changelog.d/*.md 2>/dev/null | wc -l  # Expected: 0 (all consumed)
```

### Final Checklist
- [x] All 14 atomic commits present in git log
- [x] Content identical to original mega-commit (diff empty)
- [x] All tests pass (no regressions from restructure)
- [x] CHANGELOG.md has v0.4.0 section with all changes
- [x] Version bumped to 0.4.0
- [x] Towncrier set up and ready for future use
- [x] No git push has occurred
