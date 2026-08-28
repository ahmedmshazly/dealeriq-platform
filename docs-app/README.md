# DealerIQ handbook reader

A local, desktop-class reader for the DealerIQ documentation in [`docs/`](../docs/README.md).
Copied from the portfolio handbook reader design and adapted for this monorepo (ADR-028).

```bash
# from the repository root
make docs          # index, serve, open in a chromeless window
make docs-pack     # one self-contained dist/handbook.html
make docs-verify   # mechanical audit of the generated corpus
make docs-site     # publish to apps/web/public/handbook/ (/handbook/)
```

## Shape

```
scripts/     indexer + verify
src/ui/      reader, palette, graph, code view, mermaid
src/lib/     router, search, store
src/lexicon/ app-authored definitions (not derived from the indexer)
src/generated/   corpus.json, code.json — gitignored
```

See the portfolio `docs-app/README.md` for the full design rationale; this tree keeps that
method and visual language while indexing DealerIQ's Diataxis `docs/` taxonomy and
`apps/` / `packages/` / `infra/` source.
