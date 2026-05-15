# @aeogen/shared

Cross-language DTOs for the aeogenerator monorepo.

**Zod (TypeScript) is the source of truth.** Pydantic v2 models for the
Python side are *generated* from JSON Schema emitted from those Zod
definitions. There are no hand-maintained Python schemas — every change
starts in `src/schemas/*.ts` and propagates outward.

## Layout

```
packages/shared/
├── package.json                 — @aeogen/shared, Zod 4, tsx, vitest
├── tsconfig.json                — typecheck only (noEmit)
├── tsconfig.build.json          — emit .js / .d.ts into ./dist
├── pyproject.toml               — aeogen-shared, pydantic v2, datamodel-code-generator (dev)
├── src/
│   ├── index.ts                 — public TS entry: re-exports schemas
│   ├── schemas/
│   │   ├── site.ts              — SiteSchema (Zod) + Site type
│   │   └── workspace.ts         — WorkspaceSchema (Zod) + Workspace type
│   └── scripts/
│       ├── emit-json-schema.ts  — Zod → JSON Schema (draft 2020-12)
│       ├── codegen-pydantic.ts  — JSON Schema → Pydantic v2 BaseModel
│       └── check-drift.ts       — re-runs codegen, fails if python/ differs
├── dist/                        — gitignored: compiled TS + JSON Schema
├── python/
│   └── aeogen_shared/
│       ├── __init__.py          — re-exports Site, Workspace
│       ├── py.typed             — PEP 561 marker
│       ├── site.py              — GENERATED — do not edit
│       └── workspace.py         — GENERATED — do not edit
└── tests/
    ├── fixtures/                — shared JSON used by both TS + Python
    ├── parity.test.ts           — Vitest: parse fixtures via Zod
    └── python/
        ├── conftest.py
        └── test_parity.py       — pytest: parse SAME fixtures via Pydantic
```

## Add a new schema (the whole workflow)

1. **Define the Zod schema** in `src/schemas/<thing>.ts`:
   ```ts
   import { z } from "zod";
   export const ThingSchema = z.object({
     id: z.uuid(),
     name: z.string().min(1).max(120),
   }).strict();
   export type Thing = z.infer<typeof ThingSchema>;
   ```

2. **Re-export it** in `src/index.ts`:
   ```ts
   export { ThingSchema } from "./schemas/thing.js";
   export type { Thing } from "./schemas/thing.js";
   ```

3. **Register it for codegen** in `src/scripts/emit-json-schema.ts` and
   `src/scripts/codegen-pydantic.ts` (add an entry to the `EXPORTS` /
   `JOBS` arrays).

4. **Regenerate Python**:
   ```powershell
   pnpm --filter @aeogen/shared build
   ```
   This runs three steps in order: `tsc` → `emit-json-schema` →
   `codegen-pydantic`. The Pydantic file lands at
   `python/aeogen_shared/thing.py` with a `# DO NOT EDIT` header.

5. **Add a fixture + parity tests** in `tests/fixtures/thing.valid.json`,
   `tests/parity.test.ts`, and `tests/python/test_parity.py` so both
   languages must accept the same JSON bytes.

6. **Commit BOTH sides.** Generated Python lives in version control
   (treat it like a lockfile — committed but never hand-edited). The
   drift check enforces this on CI.

## Conventions

- **`.strict()` on every object schema.** Unknown keys are an error;
  Pydantic side gets `model_config = ConfigDict(extra="forbid")`.
- **`z.uuid()` for IDs** → JSON Schema `format: "uuid"` → Python `UUID`.
- **`z.url()` for URLs** → JSON Schema `format: "uri"` → Python `AnyUrl`.
- **`z.iso.datetime()` for timestamps** → JSON Schema
  `format: "date-time"` → Python `datetime`.
- **`.nullable()` for null-allowed but required-present fields.** The
  emit script rewrites the resulting `anyOf` into
  `type: ["string", "null"]` so codegen emits `Annotated[T | None, ...]`
  without a `= None` default, preserving the Zod "must be present, may
  be null" semantics.

## TS consumer pattern (apps/web)

```ts
import { SiteSchema, type Site } from "@aeogen/shared";

const parsed = SiteSchema.parse(rawJson);  // throws on invalid input
//    ^^ Site
```

`apps/web` consumes the built artifact at `./dist/index.js`. Run
`pnpm --filter @aeogen/shared build` before the first `pnpm --filter
@aeogen/web build` in a fresh checkout.

## Python consumer pattern (apps/api, agents) — deferred

Editable install of `aeogen-shared` into `apps/api`'s uv project is
**deferred** until the first apps/api code actually imports a model
(Faz 2 B per master plan). When that day comes, add to `apps/api`'s
`pyproject.toml`:

```toml
[tool.uv.sources]
aeogen-shared = { path = "../../packages/shared", editable = true }
```

For now `apps/api` doesn't import anything from this package, so no
install is needed.

## Why generated > handwritten

- **Single source of truth.** A field added to `SiteSchema` in TS shows
  up in Python automatically. No "did we update both sides?" drift.
- **Drift detection.** `pnpm --filter @aeogen/shared run check:drift`
  re-runs codegen and fails if the committed Python differs from what
  the current Zod source would produce. Wired into CI (A.T12) and as a
  pre-commit hook (A.T10).
- **JSON Schema as the wire format.** The intermediate `dist/schemas/
  *.schema.json` files are language-neutral; any consumer (rust,
  go, openapi) can be added later without changing the Zod source.

## Drift detection

```powershell
pnpm --filter @aeogen/shared run check:drift
```

- Re-emits JSON Schema from current Zod source.
- Re-runs `datamodel-code-generator` into `python/aeogen_shared/`.
- Runs `git diff --quiet --exit-code packages/shared/python` — non-zero
  exit means committed Python is stale.

A.T10 wires this into a Husky pre-commit hook. A.T12 wires it into CI
so a PR cannot land with stale generated Python.

## Build script timing

| Hook                       | Status                          |
| -------------------------- | ------------------------------- |
| `pnpm --filter ... build`  | Available now (this task, A.T6) |
| Husky pre-commit           | Wired in A.T10                  |
| GitHub Actions CI gate     | Wired in A.T12                  |
