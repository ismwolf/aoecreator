# `supabase/` — Cloud project sync directory

This directory mirrors local state needed to sync with the Supabase Cloud
project `ngjlxlkdfgfhiookndpl`. All schema operations (migrations, table
creation, type generation) flow through the **Supabase MCP server**
(see `.mcp.json` at repo root); the CLI is used only for local bootstrap
(`supabase init`, `supabase login`) and as a fallback for MCP downtime.

## Live Cloud project

- Project ref: `ngjlxlkdfgfhiookndpl`
- URL: `https://ngjlxlkdfgfhiookndpl.supabase.co`
- Tier: free (pauses after 7 days idle; visit Dashboard to unpause)

## First-time setup (per dev machine)

```powershell
# 1. Interactive OAuth login (one-time, writes ~/.supabase/access-token)
pnpm exec supabase login

# 2. Link CLI to Cloud project (one-time)
pnpm exec supabase link --project-ref ngjlxlkdfgfhiookndpl

# 3. Restart Claude Code so Supabase MCP loads (.mcp.json)
#    Verify in Claude Code: `mcp__supabase__list_projects` should be callable.

# 4. Initial type generation (via MCP)
#    In Claude Code: invoke `mcp__supabase__generate_typescript_types`
#    and pipe output to apps/web/src/lib/database.types.ts.
#
#    Fallback (if MCP unavailable):
pwsh -c "pnpm exec supabase gen types typescript --linked > apps/web/src/lib/database.types.ts"
```

## Migration workflow (MCP-first, Faz 2 B onwards)

Per global CLAUDE.md (`~/.claude/rules/supabase.md`):

> `apply_migration` via MCP does NOT create local .sql files —
> always also write to `supabase/migrations/`.

So the canonical workflow is:

```
1. Author migration SQL locally:
   pnpm exec supabase migration new <descriptive_name>
   (creates supabase/migrations/<ts>_<name>.sql — edit it)

2. Apply via MCP (NOT `supabase db push`):
   In Claude Code: invoke `mcp__supabase__apply_migration`
   with the SQL body. MCP applies it to Cloud directly.

3. Regenerate types via MCP:
   `mcp__supabase__generate_typescript_types`
   -> pipe to apps/web/src/lib/database.types.ts

4. Commit BOTH the SQL file AND the regenerated types.
```

CLI fallback (`pnpm exec supabase db push`) is acceptable for offline
work but ALWAYS reconcile via MCP `list_migrations` on next online turn.

## Hard rules

- NEVER edit Cloud schema via Dashboard SQL Editor.
- NEVER commit `supabase/.env`, `.temp/`, `.branches/`.
- NEVER use `@supabase/auth-helpers-nextjs` — deprecated. Use `@supabase/ssr`.
- API keys: `sb_publishable_*` (public) + `sb_secret_*` (server). Never `NEXT_PUBLIC_` the secret. Always `import 'server-only'` for modules touching it.
- MCP access mode for dev project is governed by `.mcp.json` URL params (see file). NEVER point MCP at a prod ref with write access.
