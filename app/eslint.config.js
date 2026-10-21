import eslint from "@eslint/js";
import stylistic from "@stylistic/eslint-plugin";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { defineConfig } from "eslint/config";
import typescriptEslint from "typescript-eslint";

export default defineConfig(
  {
    ignores: ["dist", "public/data"],
  },
  eslint.configs.recommended,
  ...typescriptEslint.configs.recommended,
  stylistic.configs.customize({
    indent: 2,
    quotes: "double",
    semi: true,
    jsx: true,
  }),
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.flat.recommended.rules,
      ...reactRefresh.configs.vite.rules,
      "@typescript-eslint/no-explicit-any": "error",
      "@stylistic/max-statements-per-line": "off",
      "curly": ["error", "all"],
      "eqeqeq": ["error", "always"],
      "no-console": ["error", { allow: ["warn", "error"] }],
      "no-debugger": "error",
      "no-warning-comments": ["warn", { terms: ["fixme"], location: "anywhere" }],
      "prefer-const": "error",
    },
  },
  {
    files: ["*.config.{js,ts}"],
    languageOptions: {
      globals: globals.node,
    },
  },
);
