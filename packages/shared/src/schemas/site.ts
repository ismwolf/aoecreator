import { z } from "zod";

/**
 * Site — a customer website registered under a workspace.
 * Source of truth for the cross-language `Site` DTO. Pydantic version
 * is generated from JSON Schema export of this Zod definition — DO NOT
 * hand-edit packages/shared/python/aeogen_shared/site.py.
 */
export const SiteLanguageEnum = z.enum(["tr", "en", "de", "fr", "es"]);
export type SiteLanguage = z.infer<typeof SiteLanguageEnum>;

export const SiteSchema = z
  .object({
    id: z.uuid(),
    workspace_id: z.uuid(),
    url: z.url(),
    default_language: SiteLanguageEnum,
    sector: z.string().min(1).max(120).nullable(),
  })
  .strict();

export type Site = z.infer<typeof SiteSchema>;