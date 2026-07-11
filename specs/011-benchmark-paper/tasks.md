# Tasks: Benchmark & Paper

**Input**: plan.md from `specs/011-benchmark-paper/`

## Task list

- [x] T001 `packages/analytics/pyproject.toml` MODIFIED: add `pyarrow` and `scipy` as direct
      dependencies (both already present transitively; this phase imports them directly)
- [x] T002 `packages/analytics/src/dealeriq_analytics/benchmark/config.py` (NEW):
      `BenchmarkConfig` dataclass — `n_datasets` (default 3, documented rationale in plan.md),
      `base_seed` (default 42, matching the generator's own existing default), `week_start`,
      `output_dir`
- [x] T003 `packages/analytics/src/dealeriq_analytics/benchmark/runner.py` (NEW):
      `run_benchmark(config) -> list[PerSeriesResult]` — for each of `K` seeds, calls the
      existing `generate_demand`/`classify_with_stats`/`run_forecast_pipeline` unchanged (the
      exact pattern already proven in `test_qa003a_scientific_validation.py`), flattens every
      series' full `metrics_by_method` (every DS-FC-003 method, not just the champion) into one
      row per `(dataset_seed, series_key, sbc_class, method, mase, smape, pinball_q10/q50/q90,
      coverage80, is_champion)`; a `DegenerateSeriesError` series is recorded with
      `sbc_class="degenerate"`, never silently dropped. `mypy --strict` clean.
- [x] T004 `packages/analytics/src/dealeriq_analytics/benchmark/aggregate.py` (NEW):
      `build_leaderboard(results) -> LeaderboardResult` — per-`(sbc_class, method)` mean
      mase/smape/pinball/coverage80; per-class champion win-rate vs. Seasonal Naive; paired
      `scipy.stats.wilcoxon` on `(champion_mase, seasonal_naive_mase)` per series, per SBC class
      and overall, reporting the real sample size alongside every statistic. Empirically verified
      (not assumed) this scipy version's edge-case behavior for degenerate inputs before writing
      the `except ValueError` handling — n=1 with a zero-difference pair genuinely raises; a
      larger all-zero-difference set does not (returns statistic=0.0, p=1.0 with a RuntimeWarning
      instead), so the fixture test (T005) deliberately avoids depending on that ambiguous case.
- [x] T005 `packages/analytics/tests/test_benchmark_aggregate.py` (NEW, 3 tests): mean-MASE/
      win-rate hand computation; the Wilcoxon statistic/p-value for 5 same-signed paired
      differences, derived from first principles (1 of 32 equally-likely sign permutations →
      exact two-sided p=0.0625) and independently confirmed against scipy directly before being
      encoded — not reverse-engineered from `aggregate.py` itself; a zero-pairs SBC class
      reported without crashing. All 3 pass.
- [x] T006 `packages/analytics/src/dealeriq_analytics/benchmark/report.py` (NEW):
      `write_parquet(results, path)`, `write_leaderboard_markdown(leaderboard, path)`
- [x] T007 `packages/analytics/src/dealeriq_analytics/benchmark/__main__.py` (NEW): CLI —
      `python -m dealeriq_analytics.benchmark [--n-datasets N] [--base-seed S] [--output-dir DIR]`
      (argparse, matching `scripts/benchmark_api.py`'s existing convention), calling
      `run_benchmark` → `build_leaderboard` → both `report.py` writers
- [x] T008 `Makefile` MODIFIED: add `make benchmark-paper` (runs the CLI against
      `docs/paper/results/`, then compiles `docs/paper/paper.tex` via
      `pdflatex`/`bibtex`/`pdflatex`/`pdflatex` — the one-command reproduction path DS-OPS-004
      and §15 both name). Named distinctly from Phase 9's existing `make benchmark` (the NFR-003
      API-latency tool) to avoid a target collision.
- [ ] T009 Run the real benchmark (`K=3`) end-to-end; inspect the real parquet and markdown
      leaderboard; confirm real, non-placeholder numbers and record any real method/series
      failures rather than passing over them (SC-001)
- [ ] T010 Re-run with the same configuration; confirm the same seeds reproduce identical
      per-series results (SC-003's determinism claim, actually checked)
- [x] T011 `docs/paper/references.bib` (NEW): SRS §17's 15 references, transcribed verbatim
      (author/title/venue/year/pages) into BibTeX, not regenerated from memory
- [ ] T012 `docs/paper/paper.tex` (NEW): the paper draft — Abstract, Introduction, Related Work,
      Methodology, Results (populated from T009's real leaderboard output, not invented while
      drafting), Operational Integration (§15 step 5), Limitations (synthetic-data bias, SC-005),
      Conclusion
- [ ] T013 Compile `paper.tex` to `docs/paper/paper.pdf`; confirm a real, non-empty PDF with no
      LaTeX errors (SC-004)
- [ ] T014 Verify SC-002/SC-003: `make benchmark-paper` on a clean invocation reproduces both
      artifacts and the compiled PDF with zero manual steps beyond that one command
