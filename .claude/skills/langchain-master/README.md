# langchain-master skill

Project-local Claude Code skill that acts as a senior LangChain Python
engineer for the `aeogenerator` project (Python AEO SaaS).

## Invoke

```
Skill(skill="langchain-master", args="<your LangChain / LangGraph / LangSmith question>")
```

## What it does

- Reads your question and checks `references/` (promoted permanent
  answers) first.
- Falls back to a 30-day-TTL cache under `memory/`.
- On miss or staleness, queries the `docs-langchain` MCP for breadth
  + depth, synthesizes an opinionated answer, and writes it to cache.
- After 3 hits on the same topic, suggests promoting the entry to
  `references/` for permanent reuse.

## Files

| Path | Purpose |
|---|---|
| `SKILL.md` | The runbook the LLM follows on invocation. |
| `memory/_index.json` | Cache registry (topic → metadata). |
| `memory/<topic>.md` | Cached synthesized answer with frontmatter. |
| `references/<topic>.md` | Promoted permanent answer (immutable). |

## Spec & plan

- Design: `docs/superpowers/specs/2026-05-13-langchain-master-skill-design.md`
- Plan: `docs/superpowers/plans/2026-05-13-langchain-master-skill.md`
