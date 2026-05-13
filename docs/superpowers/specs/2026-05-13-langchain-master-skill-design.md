# Design Spec — `langchain-master` Skill

**Date:** 2026-05-13
**Status:** Approved (brainstorming gate)
**Project:** aeogenerator (AEO SaaS, Python, planning phase)
**Author:** Claude (with user `ismailmardin10@gmail.com`)

---

## Problem

The `aeogenerator` project will be built on the LangChain Python stack
(LangChain core, LangGraph, LangSmith). The team needs an in-session
"senior LangChain engineer" persona that:

1. Other agents (main conversation, subagents) can invoke for opinionated
   guidance on LangChain design questions.
2. Resolves questions against the official LangChain docs via the existing
   `docs-langchain` MCP server (`mcp__docs-langchain__search_docs_by_lang_chain`,
   `mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`).
3. Caches answers so repeat questions do not re-hit the MCP, saving tokens
   and latency.
4. Promotes frequently-asked topics from cache into permanent reference
   material the skill loads up-front.

## Goals

- **G1**: A project-local Claude Code skill at
  `C:\aeogenerator\.claude\skills\langchain-master\` invocable via the
  `Skill` tool.
- **G2**: When invoked, the skill behaves as a senior LangChain Python
  engineer with deep LangGraph + LangSmith experience, delivering
  opinionated guidance — not raw doc dumps.
- **G3**: A file-based cache under `memory/` keyed by topic, with
  `cached_at` timestamps and 30-day TTL.
- **G4**: A hybrid promotion mechanism: once a cache entry's hit count
  reaches 3, the skill *suggests* promoting it to `references/`; the user
  approves before the move.
- **G5**: All answers cite the MCP source path/URL they were synthesized
  from, so the user can verify.

## Non-Goals

- **NG1**: This skill does NOT cover non-LangChain stack pieces
  (general Python, FastAPI, Postgres, Supabase). Those have their own
  skills or live in global CLAUDE.md.
- **NG2**: This skill does NOT cover LangChain JS/TS, integration libraries
  outside core/graph/smith (e.g., LangServe, LangChain Hub MCP), or
  third-party vector store specifics beyond what the LangChain docs cover.
- **NG3**: No external server, no database — purely filesystem-backed
  cache.
- **NG4**: No automatic eviction of cache entries beyond marking stale;
  the user can prune manually.

## Approach

### Directory layout

```
C:\aeogenerator\.claude\skills\langchain-master\
├── SKILL.md              # Frontmatter + persona + workflow instructions
├── README.md             # Human-readable overview (optional, brief)
├── memory/
│   ├── _index.json       # Registry of cache entries
│   └── <topic-key>.md    # One file per cached topic
└── references/           # Promoted permanent knowledge (starts empty)
```

### `SKILL.md` frontmatter

```yaml
---
name: langchain-master
description: Senior LangChain Python engineer for the aeogenerator project.
  Use when designing, reviewing, or asking about LangChain (LCEL, chains,
  retrievers), LangGraph (agents, state machines), or LangSmith (tracing,
  evals). Checks references, then memory cache, then queries the
  langchain MCP on miss, and returns opinionated guidance with source
  citations.
---
```

### Persona definition (inside `SKILL.md`)

The skill instructs the caller to adopt this persona when answering:

- 8+ years Python; production LangChain since 0.0.x; co-built a LangGraph
  multi-agent orchestrator; runs LangSmith evals as part of CI.
- Replies are **opinionated**: picks one path, explains why, calls out the
  rejected alternative in one line.
- Knows the `aeogenerator` context: AEO (Answer Engine Optimization) SaaS,
  Python, no tech locked in yet (planning phase) — so when the user asks
  "which vector store?", the skill says "depends on X/Y/Z, here's my
  default recommendation given AEO workloads."
- Always cites the MCP doc source(s) it pulled from, as a footer.

### `_index.json` schema

```json
{
  "version": 1,
  "entries": {
    "<topic-key>": {
      "file": "memory/<topic-key>.md",
      "cached_at": "2026-05-13T12:34:56Z",
      "hit_count": 3,
      "promoted": false,
      "source_urls": ["https://python.langchain.com/docs/..."]
    }
  }
}
```

**`promoted` field** accepts three values:
- `false` — not yet promoted, skill may suggest at hit_count ≥ 3
- `true` — already promoted; `references/<topic-key>.md` exists
- `"declined"` — user said no to promotion; skill never suggests again
  for this entry (R4 mitigation)

### Cache entry file format

Each `memory/<topic-key>.md` file:

```markdown
---
topic_key: langgraph-human-in-the-loop
cached_at: 2026-05-13T12:34:56Z
hit_count: 1
sources:
  - https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/
---

# LangGraph: Human-in-the-loop

[Synthesized answer body — senior persona, opinionated, includes code.]
```

### Workflow (executed each time skill is invoked)

1. **Normalize question** → derive `topic_key` (kebab-slug, deterministic).
2. **Reference hit?** If `references/<topic-key>.md` exists, read it,
   return synthesis (no MCP, no cache write).
3. **Memory hit?** Look up `topic_key` in `_index.json`.
   - Exists AND `cached_at` < 30 days old → read `memory/<topic-key>.md`,
     increment `hit_count`, save index, return.
   - Exists AND stale (≥30 days) → treat as miss; re-query MCP, overwrite
     file, reset `cached_at`, keep `hit_count`.
4. **Miss** → query MCP:
   - First: `mcp__docs-langchain__search_docs_by_lang_chain` for breadth.
   - Then: `mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`
     on the most relevant doc paths for depth.
   - Synthesize answer in senior persona, including a "Sources:" footer.
   - Write `memory/<topic-key>.md`, update `_index.json` with
     `hit_count=1`, `cached_at=now`, `promoted=false`.
5. **Promotion check** → after step 3 or 4, if `hit_count >= 3` AND
   `promoted = false`:
   - Ask the user (in the skill's reply): "Bu konu N kez soruldu —
     `references/<topic-key>.md` olarak kalıcılaştırayım mı? (evet/hayır)"
   - On user 'yes' in a follow-up turn: copy file to `references/`, set
     `promoted = true` in index. The cache file stays for staleness
     tracking but `references/` takes precedence on next read.
6. **Return** the synthesized answer.

### Cache invalidation policy

- **TTL**: 30 days from `cached_at`. After that, treated as miss but the
  hit_count carries over.
- **No automatic deletion**: stale entries remain until refreshed or
  user-pruned. LangChain doc cache is small (text only); space is not a
  concern.
- **Manual invalidation**: user can run "skill, invalidate `<topic-key>`"
  via a follow-up message; skill deletes the file and index entry.

### How agents invoke

Main agent or subagent:

```
Skill(skill="langchain-master", args="LangGraph'ta human-in-the-loop
       breakpoint nasıl kurulur, hangi pattern AEO için uygun?")
```

The skill loads, parses `args` as the question, runs the workflow,
returns the synthesized answer.

## Architecture notes

- **No code dependencies.** This is a pure-Markdown + JSON skill. The
  workflow is executed by the LLM following `SKILL.md` instructions; the
  LLM does the file reads/writes via its built-in tools.
- **Idempotent index updates.** `_index.json` is read-modify-write each
  turn — small enough that this is fine; no locking needed (single LLM
  caller).
- **Topic-key collisions.** Deterministic slug avoids most collisions; if
  two questions map to the same key but ask different things, the second
  one will look like a stale-cache refresh — acceptable for v1.

## Risks

- **R1: LangChain doc churn.** LangChain APIs evolve fast. 30-day TTL
  mitigates but does not eliminate stale guidance.
  *Mitigation:* TTL + always-cite-source forces the user to see the doc
  link, can spot-check.
- **R2: Topic-key drift.** Two semantically similar questions might get
  different slugs and bypass the cache.
  *Mitigation:* skill normalizes (lowercase, strip stopwords, sort
  significant terms) before slugging. Accept some miss rate as v1.
- **R3: `_index.json` corruption.** If a write is interrupted, index can
  be malformed.
  *Mitigation:* skill validates JSON on read; on parse error, reinitializes
  index from `memory/*.md` frontmatter (recoverable).
- **R4: Promotion suggestion noise.** If skill nags every 3rd hit, becomes
  annoying.
  *Mitigation:* skill only suggests once per entry; if user says no, sets
  `promoted: "declined"` and never asks again.

## Open Questions

None at this gate — all earlier clarifying questions answered.

## Acceptance Criteria

1. `Skill(skill="langchain-master", args="...")` returns an opinionated
   answer formatted with the senior persona + sources footer.
2. First call for a topic queries MCP and writes `memory/<topic-key>.md`
   + updates `_index.json`.
3. Second call for the same topic within 30 days reads from
   `memory/<topic-key>.md` and increments `hit_count` — does NOT call
   MCP.
4. Third call triggers a promotion suggestion in the reply.
5. After user-approved promotion, `references/<topic-key>.md` exists and
   is consulted before `memory/`.
6. Stale entries (>30 days) re-query MCP and refresh `cached_at`.
7. Skill never invents LangChain APIs — every claim is backed by a cited
   MCP source.

---

**Next step:** Invoke `superpowers:writing-plans` to produce the
file-by-file implementation plan.
