# ADR-028: Interactive handbook reader (docs-app)

- Status: Accepted
- Date: 2026-07-17
- Requirement refs: C-05, Principle I
- Supplements: ADR-001, ADR-027

## Context

ADR-027 established the Diataxis docs portal under `docs/`. Markdown on GitHub is
readable but lacks search, a guided reading path, doc↔code joins, and an offline
pack. The owner's portfolio and EduBridge already use a Vite + vanilla TypeScript
offline reader (`docs-app`) for that UX.

DealerIQ needs the same surface without adopting MkDocs or rewriting the Diataxis
tree into numbered-only chapters.

## Decision

1. **Ship** `docs-app/` as the interactive handbook reader (copied from the
   portfolio method; branded DealerIQ). Markdown under `docs/` remains the source
   of truth.
2. **Reading structure:** `docs/00-reading-path.md` (three sessions) and
   `docs/glossary.md` (authoritative vocabulary for the reader). Diataxis paths
   stay as-is; the corpus classifier maps them to handbook / meta / background.
3. **Operator entrypoints:** `make docs`, `make docs-verify`, `make docs-site`,
   `make docs-pack` (root `package.json` scripts).
4. **Web publish:** `make docs-site` builds into `apps/web/public/handbook/`
   (gitignored), served at `/handbook/`. No marketing publish gate.
5. **CI:** a dedicated workflow job installs `docs-app`, typechecks, tests,
   verifies the corpus, and smoke-builds the static site.

## Alternatives considered

- **MkDocs Material** - rejected: heavier; portfolio/EduBridge already proved the
  handbook reader UX.
- **Docusaurus / Starlight** - rejected: framework overhead for an offline-first
  reader that already exists.
- **Rewrite all docs into `NN-*.md` only** - rejected: Diataxis layout from
  ADR-027 is the durable portal; the reader indexes it.

## Consequences

- Contributors study via `make docs` or `/handbook/` after `docs-site`.
- Corpus verify is a CI gate; broken reading-path links and glossary/lexicon
  collisions fail the build.
- Portfolio and EduBridge trees are not edited by this decision.
