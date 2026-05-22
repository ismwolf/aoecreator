import { createEnv } from '@t3-oss/env-nextjs';
import { z } from 'zod';

/**
 * Validated environment variables for @aeogen/web.
 *
 * Server-only secrets (e.g. `SUPABASE_SECRET_KEY`) must NEVER be exposed to the
 * client. Client-visible Supabase config uses the new-format publishable key
 * (`sb_publishable_*`). Legacy JWT-format keys are rejected by the regex —
 * rotate keys via the Supabase Dashboard if validation fails on boot.
 *
 * Import the `env` object instead of reading `process.env` directly so that
 * missing or malformed values fail fast at module load.
 */
export const env = createEnv({
  server: {
    SUPABASE_SECRET_KEY: z
      .string()
      .regex(
        /^sb_secret_/,
        'must be a new-format Supabase secret key (sb_secret_...)'
      )
      .min(20),
  },
  client: {
    NEXT_PUBLIC_APP_URL: z.string().url().default('http://localhost:3000'),
    NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: z
      .string()
      .regex(
        /^sb_publishable_/,
        'must be a new-format Supabase publishable key (sb_publishable_...)'
      )
      .min(20),
  },
  runtimeEnv: {
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_SECRET_KEY: process.env.SUPABASE_SECRET_KEY,
  },
  emptyStringAsUndefined: true,
  skipValidation: !!process.env.SKIP_ENV_VALIDATION,
});
