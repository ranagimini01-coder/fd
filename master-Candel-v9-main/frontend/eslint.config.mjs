import js from '@eslint/js';
import babelParser from '@babel/eslint-parser';
import globals from 'globals';

export default [
  { ignores: ['dist/**', 'node_modules/**', 'plugins/**', 'public/**'] },
  {
    files: ['**/*.{js,mjs,jsx}'],
    ...js.configs.recommended,
    languageOptions: { globals: { ...globals.browser, ...globals.node }, parserOptions: { ecmaFeatures: { jsx: true } } },
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: babelParser,
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { requireConfigFile: false, babelOptions: { parserOpts: { plugins: ['typescript', 'jsx'] } } },
    },
    // TypeScript's build checks bindings/types; ESLint covers control-flow defects.
    rules: { 'no-unreachable': 'error', 'no-constant-binary-expression': 'error', 'no-dupe-args': 'error', 'no-unsafe-finally': 'error', 'valid-typeof': 'error' },
  },
];