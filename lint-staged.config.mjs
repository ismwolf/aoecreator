// Per-workspace ESLint resolution: lint-staged spawns commands from repo root,
// but ESLint binaries live in workspace node_modules (apps/web, packages/shared).
// `pnpm --filter <ws> exec` resolves to the correct workspace's bin.
const eslintForFile = (file) => {
  if (file.includes('apps/web/') || file.includes('apps\\web\\')) {
    return `pnpm --filter @aeogen/web exec eslint --fix ${file}`;
  }
  if (
    file.includes('packages/shared/') ||
    file.includes('packages\\shared\\')
  ) {
    return `pnpm --filter @aeogen/shared exec eslint --fix ${file}`;
  }
  return null;
};

export default {
  '*.{ts,tsx,js,mjs,cjs}': (files) => {
    const tasks = ['pnpm exec prettier --write ' + files.join(' ')];
    const eslintCmds = files.map(eslintForFile).filter(Boolean);
    tasks.push(...eslintCmds);
    return tasks;
  },
  '*.{json,md,yml,yaml}': ['pnpm exec prettier --write'],
  'apps/api/**/*.py': (files) => [
    `uv run --directory apps/api ruff check --fix ${files.join(' ')}`,
    `uv run --directory apps/api ruff format ${files.join(' ')}`,
  ],
};
