"""Benchmark run configuration (DS-OPS-004)."""

import dataclasses
from pathlib import Path

import pandas as pd

# K=3: a single dataset's full generate -> classify -> CV-across-8-methods -> champion-select
# pipeline measured ~10-15 minutes in test_qa003a_scientific_validation.py's own docstring
# (Phase 4). K=3 keeps total runtime to roughly 30-45 minutes while still yielding several
# hundred paired per-series observations for the Wilcoxon test, since each dataset already spans
# all four demand patterns on its own (Phase 4's SBC-coverage validation). See
# specs/011-benchmark-paper/spec.md's Assumptions for the full reasoning.
DEFAULT_N_DATASETS = 3
DEFAULT_BASE_SEED = 42
DEFAULT_WEEK_START = pd.Timestamp("2023-07-17")


@dataclasses.dataclass(frozen=True)
class BenchmarkConfig:
    n_datasets: int = DEFAULT_N_DATASETS
    base_seed: int = DEFAULT_BASE_SEED
    week_start: pd.Timestamp = DEFAULT_WEEK_START
    output_dir: Path = dataclasses.field(default_factory=lambda: Path("docs/paper/results"))

    def seeds(self) -> list[int]:
        return [self.base_seed + k for k in range(self.n_datasets)]
