import { FlatCompat } from "@eslint/eslintrc";
import jsxA11y from "eslint-plugin-jsx-a11y";

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname,
});

// NFR-008: eslint-plugin-jsx-a11y's recommended ruleset, enforces baseline accessibility
// (labeled controls, keyboard operability, valid ARIA usage) as a build-blocking gate rather
// than one-off vigilance.
const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  // next/core-web-vitals already registers the `jsx-a11y` plugin itself (and enables a subset
  // of its rules), re-declaring the plugin here would conflict, so only the rule set is added.
  {
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      // `<Input>` (components/ui/input.tsx) always renders a real <input> as its root element;
      // the rule can't see through a custom component name by default.
      "jsx-a11y/label-has-associated-control": ["error", { controlComponents: ["Input"] }],
    },
  },
  {
    // public/handbook/ is the docs-app reader's Vite build output (ADR-028), published by
    // `make docs-site` and gitignored. Minified vendor bundles, not source.
    ignores: [".next/**", "node_modules/**", "next-env.d.ts", "public/handbook/**"],
  },
];

export default eslintConfig;
