# AI Workflow

## Recommended tool allocation

Use **Claude Code as the builder** and **Codex as the reviewer / verifier**.

## Why Claude Code first

Claude Code is better suited for this project because the first phase is not just code generation. It requires:

- product framing
- repository-level context retention
- documentation-heavy iteration
- dashboard narrative design
- metric-design judgment
- multi-file refactoring

Claude Code should own the first implementation path.

## Why Codex second

Codex should be used as a skeptical reviewer and implementation verifier:

- code correctness
- tests
- edge cases
- maintainability
- PR review
- whether instructions in `AGENTS.md` are being followed

## Standard loop

```text
1. Human defines issue / acceptance criteria.
2. Claude Code implements a focused change.
3. Run tests / lint.
4. Codex reviews the diff.
5. Claude Code or human fixes review items.
6. Update README/docs if the behavior changed.
```

## Claude Code prompt template

```text
Read tokyo-market-intelligence-map/CLAUDE.md first.
Implement GitHub issue #[number].
Keep the implementation small and reviewable.
Do not overclaim from synthetic or public data.
Run tests or explain why tests cannot run.
```

## Codex review prompt template

```text
Review this change as a senior BI engineer and market intelligence hiring reviewer.
Focus on correctness, maintainability, metric definitions, reproducibility, data lineage, and whether the dashboard tells a decision story.
Flag anything that looks like a shallow portfolio dashboard.
Return prioritized fixes: P0, P1, P2.
```

## PR review rubric

| Category | Reviewer question |
|---|---|
| Decision clarity | Does the output answer a real decision question? |
| Metric correctness | Are formulas inspectable and not duplicated? |
| Data lineage | Can every metric be traced to a source or placeholder? |
| Reproducibility | Can a reviewer run the project from instructions? |
| UI simplicity | Can a non-technical reader understand the first screen? |
| Caveat handling | Are proxy risks and confidence labels visible? |
| Code maintainability | Is logic separated from presentation? |
| Test coverage | Are scoring edge cases covered? |
| Portfolio narrative | Does this read as BI / Intelligence, not a school project? |

## Anti-patterns

- Asking the agent to build everything at once.
- Letting formulas live only in the dashboard.
- Adding ML before metric definitions are clear.
- Publishing before data caveats are visible.
- Treating synthetic demo outputs as findings.
