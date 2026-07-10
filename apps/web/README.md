# apps/web — DealerIQ Web

Next.js 15 (App Router, TypeScript) frontend. Consumes the API exclusively through the
generated client in `packages/api-client` (C-05, ADR-012) — no hand-written fetch calls to
undocumented endpoints (the one temporary exception, the Phase 0 home page's direct `/health`
fetch, is documented inline and will be removed once real endpoints exist).

## Brand system

Design tokens are copied verbatim from the brand kit tokens into `app/tokens.css` and wired
into `tailwind.config.ts` (colors/radius/shadow reference CSS custom properties so
`[data-theme="dark"]` swaps them live — see `next-themes` usage in
`components/theme-provider.tsx`, `attribute="data-theme"`, `defaultTheme="light"`). Fonts
(Inter + JetBrains Mono) are self-hosted via `next/font/google`, not the Brand Kit mockups' CDN
`<link>` approach. Icons come from `lucide-react`, stroke-width 1.5 per the brand guidelines.

Two brand kit inconsistencies were resolved during implementation (see
`docs/adr/`): card radius standardized on 14px
(`--radius-card`), and responsive breakpoints use Tailwind's stock scale with the mockups'
fixed content widths (1120/1180px) kept as named `maxWidth` tokens (`content`, `dashboard`)
instead.

## Running locally

From the repo root: `make dev`, or standalone: `npm run dev --workspace apps/web`.

## Tests

```bash
npm run test --workspace apps/web       # Vitest + React Testing Library
npm run typecheck --workspace apps/web  # tsc --noEmit
npm run lint --workspace apps/web       # eslint
```

Playwright E2E golden-path tests land in Phase 9 (`docs/srs/DealerIQ-SRS.md` QA-004).
