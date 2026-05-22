import tseslint from 'typescript-eslint';
import eslintConfigPrettier from 'eslint-config-prettier';

export default [
  { ignores: ['dist/**', 'python/**', 'node_modules/**'] },
  ...tseslint.configs.recommended,
  eslintConfigPrettier,
];
