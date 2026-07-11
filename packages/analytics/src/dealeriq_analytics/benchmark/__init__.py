"""DS-OPS-004 / SRS §15: the benchmark harness. Composes the already-validated
generator/forecasting/SBC pipeline (unchanged) across several independently-seeded synthetic
datasets, aggregates per-series results into a per-demand-pattern leaderboard, and runs a paired
statistical comparison. See `docs/paper/paper.tex` for the resulting write-up."""
