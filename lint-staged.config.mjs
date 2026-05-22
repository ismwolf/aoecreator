export default {
  // Uses pnpm --filter per-package instead of bare `eslint --fix` because Husky
  // on Windows does not reliably add workspace node_modules/.bin to PATH.
  '*.{ts,tsx,js,mjs,cjs}': (files) => {
    const web = files.filter(
      (f) => f.includes('/apps/web/') || f.includes('\\apps\\web\\')
    );
    const shared = files.filter(
      (f) =>
        f.includes('/packages/shared/') || f.includes('\\packages\\shared\\')
    );
    const cmds = ['prettier --write ' + files.join(' ')];
    if (web.length)
      cmds.push(`pnpm --filter @aeogen/web exec eslint --fix ${web.join(' ')}`);
    if (shared.length)
      cmds.push(
        `pnpm --filter @aeogen/shared exec eslint --fix ${shared.join(' ')}`
      );
    return cmds;
  },
  '*.{json,md,yml,yaml}': ['pnpm exec prettier --write'],
  'apps/api/**/*.py': (files) => [
    `uv run --directory apps/api ruff check --fix ${files.join(' ')}`,
    `uv run --directory apps/api ruff format ${files.join(' ')}`,
  ],
};
