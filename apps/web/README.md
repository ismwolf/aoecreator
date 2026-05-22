# @aeogen/web

Next.js 15 App Router web frontend for aeogenerator.

## Quick start

```powershell
# from repo root
pnpm install
pnpm --filter @aeogen/web dev
```

Open http://localhost:3000

## Environment

`src/lib/env.ts` validates env vars via `@t3-oss/env-nextjs` + Zod and fails
fast at module load. `NEXT_PUBLIC_APP_URL` defaults to `http://localhost:3000`
so the build works on a fresh clone without an `.env.local`. For non-default
deployments, copy `.env.example` to `.env.local` and override.

Supabase + OpenRouter keys are added in A.T8 — not yet wired.

## Stack

- **Next.js** 15.5+ (App Router, RSC default, Turbopack dev)
- **React** 19.2+
- **TypeScript** strict (`noUncheckedIndexedAccess`)
- **Tailwind** v4 (CSS-first config via `@import "tailwindcss"`)
- **shadcn/ui** baseline (`base-nova` style preset — ships a default `Button` component built on `@base-ui/react`; additional components added later in Faz 6)
- **Security headers** in `next.config.ts`: HSTS, X-Content-Type-Options, Referrer-Policy, X-Frame-Options, Permissions-Policy, CSP placeholder (A.T8 will tighten CSP once Supabase + OpenRouter origins are known)

## Route groups

- `(marketing)/` — `/` (landing)
- `(auth)/login` — sign-in placeholder
- `(app)/dashboard` — authenticated dashboard placeholder

No root `app/page.tsx` — the `(marketing)` group owns `/` to avoid route collisions.

## Scripts

| Script      | What it does                                        |
| ----------- | --------------------------------------------------- |
| `dev`       | `next dev --turbopack -p 3000`                      |
| `build`     | `next build`                                        |
| `start`     | `next start -p 3000`                                |
| `lint`      | `eslint .`                                          |
| `typecheck` | `tsc --noEmit`                                      |
| `test`      | placeholder (Vitest config arrives in a later task) |
