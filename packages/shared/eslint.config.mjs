import tseslint from 'typescript-eslint';

export default [
  { ignores: ['dist/**', 'python/**', 'node_modules/**'] },
  ...tseslint.configs.recommended,
];
