## 2026-04-22 Plan: commit-changelog

### Purpose
Split mega-commit 7347f7c into 14 atomic commits, set up Towncrier, generate v0.4.0 changelog.

### Key Patterns
- All tasks are sequential git operations (NO parallelism)
- Must follow dependency DAG for commit ordering
- Test checkpoints at T2, T3, T6, T7, T8, T11, T13, T14
- Final gate: `git diff 7347f7c HEAD` must be empty

### Conventions
- Conventional commit format: `type(scope): description`
- Towncrier fragment types: Added, Changed, Fixed, Removed, Deprecated, Security
- Fragment naming: `+<slug>.<type>.md` (orphan format)
