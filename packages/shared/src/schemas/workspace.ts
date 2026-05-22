import { z } from 'zod';

/**
 * Workspace — a per-customer workspace owned by an organization (digital agency).
 * Source of truth for the cross-language `Workspace` DTO. Pydantic version
 * is generated from JSON Schema export of this Zod definition — DO NOT
 * hand-edit packages/shared/python/aeogen_shared/workspace.py.
 */
export const WorkspaceSchema = z
  .object({
    id: z.uuid(),
    org_id: z.uuid(),
    name: z.string().min(1).max(120),
    slug: z
      .string()
      .min(1)
      .max(120)
      .regex(/^[a-z0-9-]+$/),
    created_at: z.iso.datetime(),
  })
  .strict();

export type Workspace = z.infer<typeof WorkspaceSchema>;
