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
    """Both series are numeric. Bin edges are the reference distribution's own quantile
    boundaries (deduplicated, since a low-cardinality reference feature can produce fewer than
    `bins` distinct edges) — the current series is then binned against those same edges, so a
    population that has shifted entirely outside the reference's observed range still lands in
    the reference's outermost bin rather than raising."""
    if len(reference) == 0 or len(current) == 0:
        return 0.0

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


def compute_psi_report(
    reference_df: pd.DataFrame, current_df: pd.DataFrame, feature_names: list[str]
) -> dict[str, float]:
    """One PSI value per named numeric feature present in both frames."""
    return {
        name: compute_psi(reference_df[name], current_df[name])
        for name in feature_names
        if name in reference_df.columns and name in current_df.columns
    }
