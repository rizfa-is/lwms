---
name: git-conventions
description: Branch naming and conventional commit rules for lwms.
---

# Git conventions

## Branch prefixes

| Prefix | Use for |
|---|---|
| `feat/` | new functionality |
| `fix/` | bug fixes |
| `chore/` | tooling, deps, formatting |
| `docs/` | docs and skills only |
| `test/` | test-only changes |

`branch-guard.sh` blocks edits when the current branch is `main` or
`master`. Always create a feature branch first.

## Conventional commits

```
<type>[scope]: <subject>

[body, optional]
```

Examples:

```
feat(trade): add place_market_order with dry-run guard
fix(client): timeout init when terminal is unresponsive
chore(deps): upgrade fastmcp to 2.4.0
docs(readme): document remote SSE transport
```

## What we don't do

- No `--amend` to published commits.
- No `--force` push to shared branches.
- No commits straight to `main`.
- No mixing unrelated changes in one commit (split with `git add -p`).

## Releases

Out of scope for the scaffold. We ship from `main` to a single demo
terminal.
