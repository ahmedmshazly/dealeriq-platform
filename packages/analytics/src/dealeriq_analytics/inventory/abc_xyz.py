"""ABC/XYZ classification (DS-INV-001): revenue-share ABC crossed with demand-variability XYZ,
producing the standard 9-cell matrix.

Boundary convention: models are ranked by revenue descending, and a model is assigned the class
whose cumulative-share ceiling it *first* falls at or under - i.e. the model whose inclusion
pushes cumulative revenue share past 80% is still an A (its inclusion is what crosses the
boundary), not a B. This is the standard convention in the inventory-management literature and
avoids an arbitrary tie-break on models that land exactly on a cutoff.
"""

import dataclasses

import pandas as pd

ABC_A_CUTOFF = 0.80
ABC_B_CUTOFF = 0.95

XYZ_X_CUTOFF = 0.5
XYZ_Y_CUTOFF = 1.0


@dataclasses.dataclass(frozen=True)
class AbcXyzResult:
    model_id: str
    revenue: float
    revenue_share: float
    cumulative_share: float
    abc: str
    demand_cv: float
    xyz: str


def _abc_letter(cumulative_share_before: float) -> str:
    """Classifies by the cumulative share accumulated *before* this model - so the model whose
    own share pushes the running total past a cutoff is still counted in the more exclusive
    class (its inclusion is what crosses the boundary), matching the module docstring's stated
    convention. Using the share *after* inclusion instead would misclassify the top revenue
    model as C whenever it alone exceeds 95% (e.g. a single-model dataset)."""
    if cumulative_share_before < ABC_A_CUTOFF:
        return "A"
    if cumulative_share_before < ABC_B_CUTOFF:
        return "B"
    return "C"


def _xyz_letter(cv: float) -> str:
    if cv < XYZ_X_CUTOFF:
        return "X"
    if cv < XYZ_Y_CUTOFF:
        return "Y"
    return "Z"


def demand_cv(weekly_demand: pd.Series) -> float:
    """Coefficient of variation of weekly unit demand, population statistics (ddof=0) since
    this runs over the model's complete order history, not a sample drawn from it."""
    mean = float(weekly_demand.mean())
    if mean == 0.0:
        return float("inf")
    std = float(weekly_demand.std(ddof=0))
    return std / mean


def classify_abc_xyz(
    revenue_by_model: dict[str, float],
    weekly_demand_by_model: dict[str, pd.Series],
) -> dict[str, AbcXyzResult]:
    """Classifies every model present in `revenue_by_model` - callers exclude models with zero
    order history before calling this (spec.md Edge Cases: no order history means no revenue
    share and no defined CV, so it can't be ranked, not that it defaults into a spurious cell)."""
    total_revenue = sum(revenue_by_model.values())
    ranked = sorted(revenue_by_model.items(), key=lambda kv: kv[1], reverse=True)

    results: dict[str, AbcXyzResult] = {}
    cumulative_before = 0.0
    for model_id, revenue in ranked:
        share = revenue / total_revenue if total_revenue > 0 else 0.0
        abc = _abc_letter(cumulative_before)
        cumulative_after = cumulative_before + share
        cv = demand_cv(weekly_demand_by_model[model_id])
        results[model_id] = AbcXyzResult(
            model_id=model_id,
            revenue=revenue,
            revenue_share=share,
            cumulative_share=cumulative_after,
            abc=abc,
            demand_cv=cv,
            xyz=_xyz_letter(cv),
        )
        cumulative_before = cumulative_after
    return results
