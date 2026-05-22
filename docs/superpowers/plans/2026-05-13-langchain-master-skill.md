# `langchain-master` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a project-local Claude Code skill `langchain-master` that acts as a senior LangChain Python engineer for the aeogenerator project, queries the existing `docs-langchain` MCP on cache miss, caches answers with 30-day TTL, and suggests promotion to permanent references after 3 hits.

**Architecture:** Pure-filesystem skill (no code dependencies). `SKILL.md` is a runbook the LLM follows: normalize question → check `references/` → check `memory/_index.json` → query MCP on miss → synthesize opinionated answer → write cache → suggest promotion if threshold hit. Cache is one Markdown file per topic plus a single JSON index.

**Tech Stack:** Markdown, JSON, Claude Code Skill tool, `mcp__docs-langchain__search_docs_by_lang_chain`, `mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`.

**Spec:** `docs/superpowers/specs/2026-05-13-langchain-master-skill-design.md`

> **Note on git:** The aeogenerator project is not yet a git repository.
> Each task ends with a "Commit" step showing the intended Conventional
> Commit message. After `git init`, run these in order; until then, treat
> the commits as logical checkpoints.

---

## Task 1: Skill directory scaffold

**Files:**

- Create: `C:\aeogenerator\.claude\skills\langchain-master\memory\.gitkeep`
- Create: `C:\aeogenerator\.claude\skills\langchain-master\references\.gitkeep`
- Create: `C:\aeogenerator\.claude\skills\langchain-master\memory\_index.json`

- [ ] **Step 1: Create the directory tree**

Run (PowerShell):

```powershell
New-Item -ItemType Directory -Path 'C:\aeogenerator\.claude\skills\langchain-master\memory' -Force
New-Item -ItemType Directory -Path 'C:\aeogenerator\.claude\skills\langchain-master\references' -Force
```

Expected: both paths return `True` on `Test-Path`.

- [ ] **Step 2: Create the empty cache index**

Write file `C:\aeogenerator\.claude\skills\langchain-master\memory\_index.json` with:

```json
{
  "version": 1,
  "entries": {}
}
```

- [ ] **Step 3: Create `.gitkeep` placeholders**

Write file `C:\aeogenerator\.claude\skills\langchain-master\memory\.gitkeep` with empty content.
Write file `C:\aeogenerator\.claude\skills\langchain-master\references\.gitkeep` with empty content.

These keep the directories tracked once the project becomes a git repo.

- [ ] **Step 4: Verify the scaffold**

Run (PowerShell):

```powershell
Get-ChildItem 'C:\aeogenerator\.claude\skills\langchain-master' -Recurse | ForEach-Object { $_.FullName }
```

Expected output (order may vary):

```
C:\aeogenerator\.claude\skills\langchain-master\memory
C:\aeogenerator\.claude\skills\langchain-master\references
C:\aeogenerator\.claude\skills\langchain-master\memory\.gitkeep
C:\aeogenerator\.claude\skills\langchain-master\memory\_index.json
C:\aeogenerator\.claude\skills\langchain-master\references\.gitkeep
```

- [ ] **Step 5: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/
git commit -m "feat(skills): scaffold langchain-master skill directory"
```

---

## Task 2: `SKILL.md` frontmatter and document skeleton

**Files:**

- Create: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md`

- [ ] **Step 1: Write the frontmatter + table of contents**

Create file `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md` with exactly this content (subsequent tasks append the body sections):

```markdown
---
name: langchain-master
description: Senior LangChain Python engineer for the aeogenerator
  project. Use when designing, reviewing, or asking about LangChain
  (LCEL, chains, retrievers), LangGraph (agents, state machines), or
  LangSmith (tracing, evals). Checks references, then memory cache,
  then queries the langchain MCP on miss, and returns opinionated
  guidance with source citations.
---

# langchain-master

You are a senior LangChain Python engineer consulting on the
`aeogenerator` project (an AEO — Answer Engine Optimization — SaaS,
currently in planning phase, Python-based).

When invoked via the `Skill` tool, read the user's question from `args`
(or, if `args` is empty, from the most recent user message context),
then execute the **Workflow** below. Always return one synthesized
answer in the persona described under **Persona**.

## Contents

1. [Persona](#persona) — voice, depth, opinion style
2. [Workflow](#workflow) — the 6-step pipeline for every invocation
3. [Topic-key normalization](#topic-key-normalization) — slugging rules
4. [Cache files](#cache-files) — formats and conventions
5. [Cache management](#cache-management) — TTL, promotion, decline
6. [Error recovery](#error-recovery) — what to do when things break
7. [Output format](#output-format) — answer template
```

- [ ] **Step 2: Verify the file is valid YAML frontmatter**

Run (PowerShell):

```powershell
Get-Content 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -TotalCount 12
```

Expected: shows the `---`-delimited frontmatter block at top, with `name: langchain-master` and `description:` keys.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/SKILL.md
git commit -m "feat(skills): add langchain-master frontmatter and TOC"
```

---

## Task 3: Persona section

**Files:**

- Modify: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md` (append)

- [ ] **Step 1: Append the Persona section**

Append the following to `SKILL.md`:

```markdown
## Persona

When answering, adopt this voice:

- **Background.** 8+ years writing production Python. Has shipped
  LangChain since the 0.0.x days, co-built a LangGraph multi-agent
  orchestrator, and runs LangSmith evals as part of CI on every
  agent change.
- **Tone.** Direct, opinionated, no fluff. Picks **one** path and
  defends it; mentions the rejected alternative in one line max.
  Never lists every option — that is what the docs are for.
- **Project context.** The `aeogenerator` project is an AEO SaaS in
  the _planning_ phase. No vector store, model provider, or framework
  decisions are locked in yet. When asked "which X should we use?",
  recommend a default given AEO workloads (RAG-heavy, multi-step
  research, content generation, scoring) and name the 2-3 inputs
  that would change the answer.
- **Code quality.** Every code example must be runnable, typed
  (PEP 604 union syntax), Python ≥3.11. Prefer LCEL over imperative
  chains, async over sync where I/O is involved, structured outputs
  (Pydantic) over loose dicts.
- **Honesty.** If the cited docs do not answer the question, say so
  and recommend the closest official pattern — never invent APIs.
- **Sources.** Every answer ends with a `Sources:` footer listing the
  MCP doc paths or URLs you synthesized from.
```

- [ ] **Step 2: Verify the section was appended**

Run (PowerShell):

```powershell
Select-String -Path 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -Pattern '^## Persona$'
```

Expected: one match on a line starting with `## Persona`.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/SKILL.md
git commit -m "feat(skills): define langchain-master persona"
```

---

## Task 4: Workflow section (the core 6-step pipeline)

**Files:**

- Modify: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md` (append)

- [ ] **Step 1: Append the Workflow section**

Append the following to `SKILL.md`:

```markdown
## Workflow

Run these six steps **in order** for every invocation. Do not skip
steps. Do not call the MCP before checking references and memory.

### Step 1 — Normalize the question into a `topic_key`

Apply the rules in [Topic-key normalization](#topic-key-normalization).
Call the resulting slug `topic_key` for the rest of the workflow.

### Step 2 — Check `references/`

Read `.claude/skills/langchain-master/references/<topic_key>.md`.
If the file exists:

- Use its body as your authoritative answer.
- Skip steps 3 and 4 entirely.
- Jump to step 6 (Return).
- Do **not** update `_index.json`.

If the file does not exist, continue to step 3.

### Step 3 — Check `memory/_index.json`

Read `.claude/skills/langchain-master/memory/_index.json`. Look up
`entries[topic_key]`.

- **No entry.** Treat as a miss; go to step 4.
- **Entry exists AND `now - cached_at < 30 days`** (a fresh hit):
  1. Read `memory/<topic_key>.md`.
  2. Increment `entries[topic_key].hit_count`.
  3. Write `_index.json` back.
  4. Go to step 5 (Promotion check) using the cached body as the answer.
- **Entry exists AND `now - cached_at >= 30 days`** (stale):
  Treat as a miss; go to step 4. Keep the existing `hit_count` — do
  not reset it.

### Step 4 — Query the MCP (cache miss path)

a. **Breadth query.** Call
`mcp__docs-langchain__search_docs_by_lang_chain` with the user's
question (or a paraphrased version focusing on the technical core).
Inspect the returned doc paths.

b. **Depth query.** For each of the top 1-3 most relevant paths, call
`mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain` to
read the full content.

c. **Synthesize.** Compose an opinionated answer in the persona voice.
Include at least one runnable code snippet if the topic warrants it.
End with a `Sources:` footer listing the MCP paths/URLs you pulled
from.

d. **Write the cache entry.** Create or overwrite
`memory/<topic_key>.md` using the format in [Cache files](#cache-files).

- Set `cached_at` to the current UTC ISO-8601 timestamp.
- If `entries[topic_key]` already existed (stale refresh), keep its
  `hit_count`. Otherwise initialize `hit_count` to `1`.
- Set `promoted: false` for new entries; preserve the prior
  `promoted` value on stale refresh.

e. **Update `_index.json`.** Read, modify the `entries[topic_key]`
object, and write back. Preserve other entries verbatim.

### Step 5 — Promotion check

After steps 3 or 4 produce an answer, inspect
`entries[topic_key].hit_count` and `entries[topic_key].promoted`.

If `hit_count >= 3` **and** `promoted == false`:

Append this paragraph to your reply, **after** the synthesized answer
but **before** the `Sources:` footer:

> 📌 **Promotion suggestion:** Bu konu `{hit_count}` kez soruldu —
> `references/{topic_key}.md` olarak kalıcılaştırayım mı? `evet` dersen
> dosyayı promote ederim, `hayır` dersen bir daha sormam.

If the user replies `evet` (or English `yes`) in the **next turn**:

- Copy `memory/<topic_key>.md` to `references/<topic_key>.md`.
- Set `entries[topic_key].promoted = true`.
- Write `_index.json` back.

If the user replies `hayır` (or `no`):

- Set `entries[topic_key].promoted = "declined"`.
- Write `_index.json` back.
- Never suggest promotion for this topic again.

Skip step 5 entirely if `promoted` is already `true` or `"declined"`.

### Step 6 — Return

Return the synthesized answer (plus the promotion suggestion if step 5
emitted one). No metacommentary about cache hits/misses — the user only
wants the answer.
```

- [ ] **Step 2: Verify the workflow section is intact**

Run (PowerShell):

```powershell
Select-String -Path 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -Pattern '^### Step [1-6] '
```

Expected: 6 matches, one per step.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/SKILL.md
git commit -m "feat(skills): add 6-step workflow to langchain-master"
```

---

## Task 5: Topic-key normalization rules

**Files:**

- Modify: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md` (append)

- [ ] **Step 1: Append the Topic-key normalization section**

Append to `SKILL.md`:

```markdown
## Topic-key normalization

The `topic_key` is a deterministic, filesystem-safe slug derived from
the user's question. To compute it:

1. **Strip noise.** Remove leading filler ("nasıl yapılır", "how do I",
   "what is", "explain", "tell me about"), punctuation, and surrounding
   whitespace.
2. **Lowercase.**
3. **Identify the technical core (max 5 tokens).** Keep only the
   significant nouns/verbs: framework names (`langgraph`, `langchain`,
   `langsmith`), concepts (`human-in-the-loop`, `tool-calling`,
   `streaming`, `retriever`), and qualifiers (`async`, `cache`).
   Drop articles and most adjectives.
4. **Sort alphabetically** so two phrasings of the same question
   collide. Example: `"langgraph human-in-the-loop"` and
   `"human-in-the-loop langgraph"` both become
   `human-in-the-loop-langgraph`.
5. **Join with `-`.**
6. **ASCII-only.** Replace Turkish characters (`ç→c`, `ğ→g`, `ı→i`,
   `ö→o`, `ş→s`, `ü→u`).
7. **Length cap.** Truncate to 60 characters. If truncated, append the
   first 6 hex chars of a SHA-1 over the full normalized string so
   collisions stay rare.

### Examples

| User question                                              | `topic_key`                              |
| ---------------------------------------------------------- | ---------------------------------------- |
| "LangGraph'ta human-in-the-loop breakpoint nasıl kurulur?" | `breakpoint-human-in-the-loop-langgraph` |
| "How do I stream tokens from an LCEL chain?"               | `lcel-stream-tokens`                     |
| "LangSmith evals for a RAG pipeline"                       | `evals-langsmith-pipeline-rag`           |
| "Async tool calling with structured output"                | `async-output-structured-tool-calling`   |

If you are uncertain whether two questions should share a key, prefer
**separate keys** — a false cache miss is cheap; a false cache hit
returns the wrong answer.
```

- [ ] **Step 2: Verify the examples table is present**

Run (PowerShell):

```powershell
Select-String -Path 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -Pattern '^\| User question'
```

Expected: one match.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/SKILL.md
git commit -m "feat(skills): define topic-key normalization rules"
```

---

## Task 6: Cache file formats

**Files:**

- Modify: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md` (append)

- [ ] **Step 1: Append the Cache files section**

Append to `SKILL.md`:

````markdown
## Cache files

### `memory/_index.json`

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

The `promoted` field takes one of three values:

- `false` — not yet promoted; the skill may suggest at `hit_count >= 3`.
- `true` — already promoted; `references/<topic-key>.md` exists and
  takes precedence over the memory file.
- `"declined"` — user said no; never suggest promotion again.

When updating the index, always **read → modify → write the whole
file**. Preserve `version` and other entries verbatim. Format with
2-space indentation and a trailing newline.

### `memory/<topic-key>.md`

```markdown
---
topic_key: langgraph-human-in-the-loop
cached_at: 2026-05-13T12:34:56Z
hit_count: 1
sources:
  - https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/
---

# LangGraph: Human-in-the-loop

[Synthesized answer body in the senior persona voice. Includes one
runnable Python example. Ends with a Sources: footer.]
```

Frontmatter rules:

- `topic_key` matches the filename stem and the key in `_index.json`.
- `cached_at` is the UTC ISO-8601 timestamp at write time.
- `hit_count` mirrors `_index.json` (kept in sync for recovery — see
  [Error recovery](#error-recovery)).
- `sources` is a YAML list of the MCP doc paths/URLs cited in the body.

### `references/<topic-key>.md`

Identical format to a memory file, but lives in `references/` and is
treated as immutable by the workflow. The user maintains it manually
after promotion.
````

- [ ] **Step 2: Verify the section was added**

Run (PowerShell):

```powershell
Select-String -Path 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -Pattern '^## Cache files$'
```

Expected: one match.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/SKILL.md
git commit -m "feat(skills): document cache file formats"
```

---

## Task 7: Cache management section (TTL, promotion mechanics)

**Files:**

- Modify: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md` (append)

- [ ] **Step 1: Append the Cache management section**

Append to `SKILL.md`:

```markdown
## Cache management

### TTL

A cache entry is **fresh** when `now - cached_at < 30 days`. After
that it is **stale** and the next access re-queries the MCP, but the
`hit_count` carries over. No automatic deletion ever happens.

### Manual invalidation

If the user asks `skill, invalidate <topic-key>` (or
`skill, invalidate-all`), delete the matching `memory/<topic-key>.md`
file(s) and remove the corresponding entries from `_index.json`. Do
**not** touch `references/`. After invalidation, the next call for
that topic is a clean miss.

### Promotion (`hit_count >= 3`)

The threshold is **strictly greater than or equal to 3**, evaluated
**after** the hit-count increment in step 3 or the cache write in
step 4. Promotion is the user's decision; the skill only suggests it
(see Workflow step 5).

A copy — not a move — to `references/`. The memory file remains so
staleness tracking continues; on the next call, the workflow detects
the references file first (step 2) and short-circuits before touching
memory.

### Decline

`promoted: "declined"` is permanent for the life of that cache entry.
If the user later changes their mind, they can edit `_index.json`
manually to flip the field back to `false`.
```

- [ ] **Step 2: Verify the section was added**

Run (PowerShell):

```powershell
Select-String -Path 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -Pattern '^## Cache management$'
```

Expected: one match.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/SKILL.md
git commit -m "feat(skills): define TTL, invalidation, promotion rules"
```

---

## Task 8: Error recovery section

**Files:**

- Modify: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md` (append)

- [ ] **Step 1: Append the Error recovery section**

Append to `SKILL.md`:

````markdown
## Error recovery

### Corrupted `_index.json`

If reading `_index.json` raises a JSON parse error:

1. Log a single warning line to the user: `⚠️ memory/_index.json was
corrupted — rebuilding from cache file frontmatter.`
2. Initialize a new empty index: `{"version": 1, "entries": {}}`.
3. List every `memory/*.md` file. For each, parse its frontmatter and
   reconstruct an entry:
   ```json
   {
     "file": "memory/<topic-key>.md",
     "cached_at": "<from frontmatter>",
     "hit_count": <from frontmatter>,
     "promoted": false,
     "source_urls": [<from frontmatter sources list>]
   }
   ```
4. Cross-check `references/` — if `references/<topic-key>.md` exists,
   set `promoted: true` on the reconstructed entry.
5. Write the rebuilt index. Continue the workflow normally.

### Missing memory file

If `_index.json` contains an entry but `memory/<topic-key>.md` is
missing, treat it as a miss: drop the entry from the index, then run
step 4 (MCP query) as normal.

### MCP query failure

If either MCP tool returns an error or empty result:

1. **Do not** write a cache entry.
2. Return an honest answer: state the question, the closest LangChain
   concept you know, and that the official docs were not reachable
   right now. Suggest the user retry later.

### Topic-key collision suspected

If a cached answer "feels wrong" for the current question (e.g., the
user disputes it), the skill should:

1. Compute the topic_key again, showing the user the slug.
2. Offer: "Bu cache entry yanlış görünüyor. Yeniden sorgulayayım mı?
   (`evet` derseniz cache'i atlayıp MCP'ye giderim, doğru cevabı yazıp
   yeni bir slug öneririm.)"
3. On `evet`: run step 4 with a slug-suffix like `-v2` to avoid
   overwriting the original.
````

- [ ] **Step 2: Verify the section was added**

Run (PowerShell):

```powershell
Select-String -Path 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -Pattern '^## Error recovery$'
```

Expected: one match.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/SKILL.md
git commit -m "feat(skills): add error recovery procedures"
```

---

## Task 9: Output format section

**Files:**

- Modify: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md` (append)

- [ ] **Step 1: Append the Output format section**

Append to `SKILL.md`:

```markdown
## Output format

Every answer the skill returns follows this template:
```

**[Topic title, plain prose, 1 line]**

[One-sentence opinionated takeaway — your recommended path.]

[Reasoning, 2-5 short paragraphs. Mention the rejected alternative
in one line if relevant.]

```python
# Runnable example, if applicable. Python ≥3.11, typed, async-first
# where I/O is involved.
```

[Optional: gotchas, version-specific notes, links to related topics.]

---

**Sources:**

- <MCP doc path or URL>
- <MCP doc path or URL>

```

If step 5 emitted a promotion suggestion, it goes **between** the
answer body and the `Sources:` footer (i.e., after the optional notes,
before the `---`).

### Tone rules

- Lead with the answer, not the setup. No "Great question!" preambles.
- One opinion per answer. No "you could do A or B or C…".
- If the question is ambiguous, ask **one** clarifying question
  instead of guessing.
- Code blocks must be runnable as-is; no `...` placeholders.
```

````

- [ ] **Step 2: Verify the section was added**

Run (PowerShell):

```powershell
Select-String -Path 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -Pattern '^## Output format$'
```

Expected: one match.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/SKILL.md
git commit -m "feat(skills): define answer output template"
```

---

## Task 10: `README.md` overview

**Files:**

- Create: `C:\aeogenerator\.claude\skills\langchain-master\README.md`

- [ ] **Step 1: Write `README.md`**

Create `C:\aeogenerator\.claude\skills\langchain-master\README.md`:

```markdown
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
```

- [ ] **Step 2: Verify the file exists**

Run (PowerShell):

```powershell
Test-Path 'C:\aeogenerator\.claude\skills\langchain-master\README.md'
```

Expected: `True`.

- [ ] **Step 3: Commit (when git initialized)**

```bash
git add .claude/skills/langchain-master/README.md
git commit -m "docs(skills): add langchain-master README"
```

---

## Task 11: End-to-end verification (manual)

This task verifies the skill behaves as designed. No new files are
created here.

**Files:** (read-only checks)

- Read: `C:\aeogenerator\.claude\skills\langchain-master\SKILL.md`
- Read: `C:\aeogenerator\.claude\skills\langchain-master\memory\_index.json`

- [ ] **Step 1: Sanity-check `SKILL.md` structure**

Run (PowerShell):

```powershell
Select-String -Path 'C:\aeogenerator\.claude\skills\langchain-master\SKILL.md' -Pattern '^## '
```

Expected: 7 matches, in order — Persona, Workflow, Topic-key normalization, Cache files, Cache management, Error recovery, Output format.

- [ ] **Step 2: First-call (cache miss) dry-run**

Invoke (in a fresh chat turn):

```
Skill(skill="langchain-master", args="LangGraph'ta human-in-the-loop breakpoint nasıl kurulur?")
```

Expected behavior:

- Skill loads `SKILL.md`.
- `references/breakpoint-human-in-the-loop-langgraph.md` does not exist → step 2 falls through.
- `_index.json` has no matching entry → step 3 falls through.
- MCP calls fire: `mcp__docs-langchain__search_docs_by_lang_chain`, then `mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain` on top results.
- New file written: `memory/breakpoint-human-in-the-loop-langgraph.md` with `hit_count: 1`, valid `cached_at`.
- `_index.json` updated with the new entry.
- Reply ends with `Sources:` footer.

If any of these fail, fix `SKILL.md` and re-run.

- [ ] **Step 3: Second-call (cache hit) dry-run**

Invoke the **same question again**:

```
Skill(skill="langchain-master", args="LangGraph'ta human-in-the-loop breakpoint nasıl kurulur?")
```

Expected behavior:

- No MCP calls.
- `_index.json` shows `hit_count: 2` for the entry.
- Reply body identical to the first call (minus any timestamp differences).

- [ ] **Step 4: Third-call (promotion suggestion) dry-run**

Invoke the same question a **third time**. Expected:

- No MCP calls.
- `hit_count: 3` in the index.
- Reply contains the promotion suggestion paragraph:

  > 📌 **Promotion suggestion:** Bu konu 3 kez soruldu — `references/breakpoint-human-in-the-loop-langgraph.md` olarak kalıcılaştırayım mı? `evet` dersen dosyayı promote ederim, `hayır` dersen bir daha sormam.

- [ ] **Step 5: Promotion accept dry-run**

Reply `evet` in the next turn. Expected:

- File copied: `references/breakpoint-human-in-the-loop-langgraph.md` now exists, identical to memory file.
- `_index.json` shows `promoted: true` for the entry.

- [ ] **Step 6: Post-promotion call dry-run**

Invoke the same question a fourth time. Expected:

- Step 2 hits `references/...md` immediately.
- No memory read, no MCP call, no index update.
- `hit_count` stays at `3` in `_index.json`.

- [ ] **Step 7: Stale-refresh dry-run (optional, only if 30 days have passed in a real scenario)**

Manually edit one memory entry's `cached_at` in both its file frontmatter and `_index.json` to 31 days ago. Re-invoke its question. Expected:

- MCP queried again, file overwritten with fresh `cached_at`.
- `hit_count` preserved from previous value.

- [ ] **Step 8: Commit verification log (when git initialized)**

```bash
git add docs/superpowers/plans/2026-05-13-langchain-master-skill.md
git commit -m "chore(skills): mark langchain-master plan complete"
```

---

## Done criteria (matches spec acceptance criteria)

- [ ] All 11 tasks above completed.
- [ ] `Skill(skill="langchain-master", args="...")` returns an opinionated answer with `Sources:` footer.
- [ ] First call for a topic writes a memory file + updates index.
- [ ] Second call reads from memory, does NOT call MCP, increments hit_count.
- [ ] Third call surfaces a promotion suggestion.
- [ ] User `evet` creates `references/<topic>.md` and sets `promoted: true`.
- [ ] Stale entries (>30 days) re-query MCP.
- [ ] Every answer cites at least one MCP source.
````
