import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

/**
 * Validated environment variables for @aeogen/web.
 *
 * Server-only secrets (Supabase service role, OpenRouter key, etc.) will be
 * added in A.T8 alongside the Supabase client wiring. For now only the public
 * application URL is required so that auth callback URLs and metadata can be
 * generated deterministically.
 *
 * Import the `env` object instead of reading `process.env` directly so that
 * missing or malformed values fail fast at module load.
 */
export const env = createEnv({
  server: {},
  client: {
    NEXT_PUBLIC_APP_URL: z.string().url().default("http://localhost:3000"),
  },
  runtimeEnv: {
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
  },
  emptyStringAsUndefined: true,
  skipValidation: !!process.env.SKIP_ENV_VALIDATION,
});
