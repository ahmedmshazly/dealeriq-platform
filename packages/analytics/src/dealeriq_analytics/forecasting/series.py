"""Weekly series construction from the order ledger (DS-FC-001).

Two series families share this function: (model, branch) — one series per distinct vehicle
model sold at a branch — and (segment, branch) — unit counts summed across every model in that
segment at that branch. Both need explicit calendar alignment and zero-fill: a week with no
deliveries is a real zero, not a missing row, since ADI/CV² (DS-FC-002) and every method in the
DS-FC-003 pool depend on a complete, gap-free weekly index.
"""

import pandas as pd


def compute_week_start(timestamps: pd.Series) -> pd.Series:
    """Floors each timestamp to that week's Monday (matches infra/seed/generate.py's own
    Monday-start week convention, so series line up with the weeks the data was generated on)."""
    normalized = timestamps.dt.normalize()
    return normalized - pd.to_timedelta(normalized.dt.weekday, unit="D")


def build_weekly_series(
    orders: pd.DataFrame,
    group_cols: list[str],
    date_col: str,
    keys: list[tuple[str, ...]],
    week_start: pd.Timestamp,
    n_weeks: int,
) -> dict[tuple[str, ...], pd.Series]:
    """Counts rows of `orders` per (group_cols..., week) and reindexes onto a complete
    `n_weeks`-long calendar starting at `week_start`. Every key in `keys` gets a series — even
    one with zero matching orders across the entire window gets an all-zero series, rather than
    being silently omitted, since a missing series is a generator/data bug, not a valid outcome."""
    calendar = pd.date_range(week_start, periods=n_weeks, freq="W-MON")

    if orders.empty:
        return {key: pd.Series(0, index=calendar, dtype="int64") for key in keys}

    df = orders.copy()
    df["_week"] = compute_week_start(df[date_col])
    counts = df.groupby([*group_cols, "_week"]).size().rename("count").reset_index()

    grouped = dict(iter(counts.groupby(group_cols)))
    normalized: dict[tuple[str, ...], pd.DataFrame] = {
        (key if isinstance(key, tuple) else (key,)): sub for key, sub in grouped.items()
    }

    series: dict[tuple[str, ...], pd.Series] = {}
    for key in keys:
        sub = normalized.get(key)
        if sub is None:
            series[key] = pd.Series(0, index=calendar, dtype="int64")
        else:
            series[key] = (
                sub.set_index("_week")["count"].reindex(calendar, fill_value=0).astype("int64")
            )
    return series
