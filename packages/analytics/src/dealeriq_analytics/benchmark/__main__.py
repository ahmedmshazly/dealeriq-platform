"""DS-OPS-004: `python -m dealeriq_analytics.benchmark [--n-datasets N] [--base-seed S]
[--output-dir DIR]`. No database, no running service, pure composition of the already-tested
generator/forecasting/SBC pipeline."""

import argparse
import sys
import time
from pathlib import Path

from dealeriq_analytics.benchmark.aggregate import build_leaderboard
from dealeriq_analytics.benchmark.config import (
    DEFAULT_BASE_SEED,
    DEFAULT_N_DATASETS,
    BenchmarkConfig,
)
from dealeriq_analytics.benchmark.report import write_leaderboard_markdown, write_parquet
from dealeriq_analytics.benchmark.runner import run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-datasets", type=int, default=DEFAULT_N_DATASETS)
    parser.add_argument("--base-seed", type=int, default=DEFAULT_BASE_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/paper/results"))
    args = parser.parse_args()

    config = BenchmarkConfig(
        n_datasets=args.n_datasets, base_seed=args.base_seed, output_dir=args.output_dir
    )

    print(f"Running benchmark: {config.n_datasets} dataset(s), seeds {config.seeds()}")
    start = time.perf_counter()
    results = run_benchmark(config)
    elapsed = time.perf_counter() - start
    print(f"Done in {elapsed:.1f}s -- {len(results)} per-series-per-method rows.")

    leaderboard = build_leaderboard(results)

    parquet_path = config.output_dir / "benchmark_results.parquet"
    markdown_path = config.output_dir / "leaderboard.md"
    write_parquet(results, parquet_path)
    write_leaderboard_markdown(leaderboard, markdown_path)

    print(f"Wrote {parquet_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
