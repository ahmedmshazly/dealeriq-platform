"""Population Stability Index (FR-074): a small, hand-implemented, unit-tested primitive —
no actively-maintained package implements PSI as a standalone function, and the formula itself
is short enough to validate directly against a hand-computed fixture, matching ADR-017's
established precedent for this project (GESD was hand-implemented for the same reason).

PSI compares a "reference" distribution against a "current" one, binned by the reference's own
decile edges, so both distributions are measured against the same yardstick. A value above 0.25
is the conventional industry threshold for "substantial population shift" (FR-074's own stated
cutoff).
"""

import numpy as np
import pandas as pd

PSI_DRIFT_THRESHOLD = 0.25
DEFAULT_BINS = 10
_EPSILON = 1e-4  # floors zero-count bins so log() never sees a zero or divides by one


def compute_psi(reference: pd.Series, current: pd.Series, *, bins: int = DEFAULT_BINS) -> float:
    """Both series are numeric. A low-cardinality reference (at most `bins` distinct values —
    e.g. a 0/1 one-hot column) is binned by its exact values, one bin per value: quantile edges
    on a binary column collapse to a single (-inf, +inf) bin (every quantile point lands on the
    same 0 or 1), which would silently report zero PSI for any shift in a categorical feature's
    proportions, no matter how large. A higher-cardinality reference is binned by its own decile
    boundaries — the current series is then binned against those same edges, so a population
    that has shifted entirely outside the reference's observed range still lands in the
    reference's outermost bin rather than raising."""
    if len(reference) == 0 or len(current) == 0:
        return 0.0

    unique_values = np.sort(reference.unique())
    if len(unique_values) <= bins:
        return _compute_psi_categorical(reference, current, unique_values)

    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(reference.quantile(quantiles).to_numpy())
    if len(edges) < 2:
        # The reference feature has (near-)zero variance — no meaningful bins to compare across.
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf

    ref_counts = pd.cut(reference, bins=edges, include_lowest=True).value_counts(sort=False)
    cur_counts = pd.cut(current, bins=edges, include_lowest=True).value_counts(sort=False)

    ref_pct = (ref_counts / len(reference)).clip(lower=_EPSILON)
    cur_pct = (
        (cur_counts / len(current)).reindex(ref_pct.index, fill_value=0.0).clip(lower=_EPSILON)
    )

    return float(((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)).sum())


def _compute_psi_categorical(
    reference: pd.Series, current: pd.Series, reference_values: np.ndarray
) -> float:
    """One bin per exact value seen in the reference — `current` values the reference never saw
    at all fall into their own extra bin(s) rather than being silently dropped."""
    all_values = sorted(set(reference_values) | set(current.unique()))
    ref_counts = reference.value_counts()
    cur_counts = current.value_counts()

    ref_pct = pd.Series(
        [ref_counts.get(v, 0) / len(reference) for v in all_values], index=all_values
    ).clip(lower=_EPSILON)
    cur_pct = pd.Series(
        [cur_counts.get(v, 0) / len(current) for v in all_values], index=all_values
    ).clip(lower=_EPSILON)

    return float(((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)).sum())


def compute_psi_report(
    reference_df: pd.DataFrame, current_df: pd.DataFrame, feature_names: list[str]
) -> dict[str, float]:
    """One PSI value per named numeric feature present in both frames."""
    return {
        name: compute_psi(reference_df[name], current_df[name])
        for name in feature_names
        if name in reference_df.columns and name in current_df.columns
    }
