import { writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { z } from 'zod';
import { SiteSchema } from '../schemas/site.js';
import { WorkspaceSchema } from '../schemas/workspace.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = resolve(__dirname, '../../dist/schemas');

interface SchemaExport {
  name: string;
  filename: string;
  schema: z.ZodTypeAny;
}

const EXPORTS: SchemaExport[] = [
  { name: 'Site', filename: 'site.schema.json', schema: SiteSchema },
  {
    name: 'Workspace',
    filename: 'workspace.schema.json',
    schema: WorkspaceSchema,
  },
];

/**
 * Strip redundant `pattern` keywords from string subschemas that already declare
 * a structural `format` (uuid, date-time). Zod 4's `z.uuid()` and
 * `z.iso.datetime()` emit both a format AND a regex pattern; Pydantic v2
 * refuses to apply a `pattern` constraint to UUID / datetime core schemas,
 * crashing with `Unable to apply constraint 'pattern' to ... schema of type
 * 'uuid'`. The format alone carries the constraint, so the pattern is safe
 * to drop for those two cases. We DO NOT strip patterns from plain `string`
 * fields (e.g. Workspace.slug) — those are real, semantic constraints.
 */
function stripRedundantPatterns(node: unknown): void {
  if (node === null || typeof node !== 'object') return;
  if (Array.isArray(node)) {
    for (const item of node) stripRedundantPatterns(item);
    return;
  }
  const obj = node as Record<string, unknown>;
  const format = obj['format'];
  if (
    typeof format === 'string' &&
    (format === 'uuid' || format === 'date-time') &&
    'pattern' in obj
  ) {
    delete obj['pattern'];
  }
  for (const value of Object.values(obj)) stripRedundantPatterns(value);
}

/**
 * Collapse `anyOf: [{ type: "X", ...constraints }, { type: "null" }]` shapes
 * (emitted by Zod's `.nullable()`) into `{ type: ["X", "null"], ...constraints }`.
 *
 * Two reasons:
 *  1. datamodel-code-generator emits a separate `RootModel` wrapper class for
 *     each inline `anyOf` member that carries constraints, leaving consumer
 *     code with awkward `obj.field.root` access on what should be a plain str.
 *  2. With `type: [..., "null"]` the generator emits `field: T | None` as a
 *     required field WITHOUT a default, preserving Zod's required-nullable
 *     semantics. With `anyOf` it adds `= None` and silently accepts missing
 *     keys, which is a cross-language parity break.
 *
 * Only handles the two-member case where exactly one member is `{ type: "null" }`.
 * Patterns with more than two members or with refs are left untouched.
 */
function collapseNullableAnyOf(node: unknown): void {
  if (node === null || typeof node !== 'object') return;
  if (Array.isArray(node)) {
    for (const item of node) collapseNullableAnyOf(item);
    return;
  }
  const obj = node as Record<string, unknown>;
  const anyOf = obj['anyOf'];
  if (Array.isArray(anyOf) && anyOf.length === 2) {
    const nullIdx = anyOf.findIndex(
      (m) =>
        m !== null &&
        typeof m === 'object' &&
        !Array.isArray(m) &&
        (m as Record<string, unknown>)['type'] === 'null' &&
        Object.keys(m as Record<string, unknown>).length === 1
    );
    const otherIdx = nullIdx === 0 ? 1 : nullIdx === 1 ? 0 : -1;
    if (nullIdx !== -1 && otherIdx !== -1) {
      const other = anyOf[otherIdx] as Record<string, unknown>;
      const otherType = other['type'];
      if (typeof otherType === 'string') {
        delete obj['anyOf'];
        for (const [k, v] of Object.entries(other)) {
          if (k === 'type') {
            obj['type'] = [otherType, 'null'];
          } else {
            obj[k] = v;
          }
        }
      }
    }
  }
  for (const value of Object.values(obj)) collapseNullableAnyOf(value);
}

async function main(): Promise<void> {
  await mkdir(OUT_DIR, { recursive: true });
  for (const exp of EXPORTS) {
    const json = z.toJSONSchema(exp.schema, {
      target: 'draft-2020-12',
      reused: 'inline',
    });
    stripRedundantPatterns(json);
    collapseNullableAnyOf(json);
    const enriched = {
      $schema: 'https://json-schema.org/draft/2020-12/schema',
      $id: `https://aeogen.local/schemas/${exp.filename}`,
      title: exp.name,
      ...json,
    };
    const path = resolve(OUT_DIR, exp.filename);
    await writeFile(path, JSON.stringify(enriched, null, 2) + '\n', 'utf8');
    console.log(`emit: ${exp.filename}`);
  }
}

await main();
