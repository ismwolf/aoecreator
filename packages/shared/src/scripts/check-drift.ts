import { spawnSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = resolve(__dirname, '../..');
const REPO_ROOT = resolve(PKG_ROOT, '../..');

// On Windows, `pnpm` resolves to `pnpm.cmd`, which Node refuses to spawn
// without a shell since the CVE-2024-27980 mitigation. Arguments here are
// hard-coded literals (no user input, no special chars), so `shell: true`
// is safe — the deprecation warning about arg escaping does not apply.
const isWin32 = process.platform === 'win32';

const emit = spawnSync('pnpm', ['run', 'build:json-schema'], {
  cwd: PKG_ROOT,
  stdio: 'inherit',
  shell: isWin32,
});
if (emit.status !== 0) process.exit(emit.status ?? 1);

const codegen = spawnSync('pnpm', ['run', 'codegen:python'], {
  cwd: PKG_ROOT,
  stdio: 'inherit',
  shell: isWin32,
});
if (codegen.status !== 0) process.exit(codegen.status ?? 1);

const diff = spawnSync(
  'git',
  ['diff', '--quiet', '--exit-code', 'packages/shared/python'],
  {
    cwd: REPO_ROOT,
    stdio: 'inherit',
  }
);
if (diff.status !== 0) {
  console.error(
    '\nDRIFT DETECTED: packages/shared/python is out of sync with current Zod source.'
  );
  console.error(
    'Run `pnpm --filter @aeogen/shared build` and commit the result.'
  );
  process.exit(1);
}
console.log('drift check: OK');
