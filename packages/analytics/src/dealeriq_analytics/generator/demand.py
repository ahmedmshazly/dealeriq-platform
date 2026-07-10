"""NB-GLM weekly demand simulation (GEN-002). Pure numpy — no DB dependency, deterministic
given a seed, drawn in a fixed order so the same seed always produces the same output (GEN-001,
SC-005).

log mu(t) = beta0 + beta_trend*(t/T) + sum_k[gamma_k*cos(2*pi*k*t/52) + delta_k*sin(2*pi*k*t/52)]
            + beta_promo*1[promo week] + log(branch_effect)
Y(t) ~ NegativeBinomial(mean=mu(t), dispersion=alpha)

branch_effect is specified on the linear scale (e.g. 0.8 = 80% of the flagship branch's volume),
so it enters the log-mean sum as log(branch_effect) — the only way "linear scale" and "additive
in log-space" are both true at once.
"""

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dealeriq_analytics.generator.config import GeneratorConfig


@dataclass(frozen=True)
class ModelDef:
    key: str
    make: str
    model: str
    segment_key: str
    target_sbc_class: str
    list_price: float
    mu0: float
    dispersion: float


@dataclass(frozen=True)
class SeriesParams:
    model_key: str
    branch_name: str
    beta0: float
    beta_trend: float
    fourier: tuple[tuple[float, float], ...]
    branch_effect: float
    dispersion: float
    promo_weeks: tuple[int, ...]
    beta_promo: float
    target_sbc_class: str


@dataclass(frozen=True)
class GeneratedDemand:
    model_defs: list[ModelDef]
    series_params: list[SeriesParams]
    series: dict[tuple[str, str], NDArray[np.int64]] = field(default_factory=dict)


def build_model_defs(config: GeneratorConfig, rng: np.random.Generator) -> list[ModelDef]:
    defs: list[ModelDef] = []
    for segment in config.segments:
        candidates = config.makes_models_by_segment[segment.key][: segment.n_models]
        for make, model in candidates:
            jitter = 1.0 + rng.uniform(-config.per_model_jitter, config.per_model_jitter)
            mu0 = float(rng.uniform(*segment.mu0_range)) * jitter
            dispersion = float(rng.uniform(*segment.dispersion_range)) * jitter
            list_price = float(rng.uniform(*segment.list_price_range))
            defs.append(
                ModelDef(
                    key=f"{segment.key}:{make}:{model}",
                    make=make,
                    model=model,
                    segment_key=segment.key,
                    target_sbc_class=segment.target_sbc_class,
                    list_price=round(list_price, 2),
                    mu0=max(mu0, 0.02),
                    dispersion=max(dispersion, 0.01),
                )
            )
    return defs


def build_series_params(
    config: GeneratorConfig, model_defs: list[ModelDef], rng: np.random.Generator
) -> list[SeriesParams]:
    params: list[SeriesParams] = []
    for model_def in model_defs:
        for branch_name, _city, branch_effect in config.branches:
            beta_trend = float(rng.normal(0, config.trend_std))
            fourier = tuple(
                (
                    float(rng.normal(0, config.fourier_amplitude_std)),
                    float(rng.normal(0, config.fourier_amplitude_std)),
                )
                for _ in range(2)
            )
            n_promo = int(rng.integers(config.promo_min_windows, config.promo_max_windows + 1))
            promo_weeks: set[int] = set()
            for _ in range(n_promo):
                start = int(rng.integers(0, config.n_weeks))
                length = int(
                    rng.integers(config.promo_min_len_weeks, config.promo_max_len_weeks + 1)
                )
                promo_weeks.update(range(start, min(start + length, config.n_weeks)))
            beta_promo = float(rng.uniform(*config.promo_effect_range))

            params.append(
                SeriesParams(
                    model_key=model_def.key,
                    branch_name=branch_name,
                    beta0=float(np.log(model_def.mu0)),
                    beta_trend=beta_trend,
                    fourier=fourier,
                    branch_effect=branch_effect,
                    dispersion=model_def.dispersion,
                    promo_weeks=tuple(sorted(promo_weeks)),
                    beta_promo=beta_promo,
                    target_sbc_class=model_def.target_sbc_class,
                )
            )
    return params


def _negative_binomial(rng: np.random.Generator, mean: float, dispersion: float) -> int:
    """Samples NB(mean=mean, dispersion=dispersion) via numpy's (n, p) parameterization,
    where variance = mean + dispersion*mean^2 (the standard NB2/GLM parameterization)."""
    if mean <= 0:
        return 0
    r = 1.0 / dispersion
    p = r / (r + mean)
    return int(rng.negative_binomial(r, p))


def simulate_series(
    params: SeriesParams, n_weeks: int, rng: np.random.Generator
) -> NDArray[np.int64]:
    weeks = np.arange(n_weeks)
    log_mu = params.beta0 + params.beta_trend * (weeks / n_weeks)
    for k, (gamma_k, delta_k) in enumerate(params.fourier, start=1):
        log_mu = (
            log_mu
            + gamma_k * np.cos(2 * np.pi * k * weeks / 52)
            + delta_k * np.sin(2 * np.pi * k * weeks / 52)
        )
    promo_mask = np.isin(weeks, np.array(params.promo_weeks, dtype=int))
    log_mu = log_mu + params.beta_promo * promo_mask
    log_mu = log_mu + np.log(params.branch_effect)

    mu = np.exp(log_mu)
    values = np.array(
        [_negative_binomial(rng, float(m), params.dispersion) for m in mu], dtype=np.int64
    )
    return values


def generate_demand(config: GeneratorConfig) -> GeneratedDemand:
    rng = np.random.default_rng(config.seed)
    model_defs = build_model_defs(config, rng)
    series_params = build_series_params(config, model_defs, rng)

    series: dict[tuple[str, str], NDArray[np.int64]] = {}
    for params in series_params:
        series[(params.model_key, params.branch_name)] = simulate_series(
            params, config.n_weeks, rng
        )

    return GeneratedDemand(model_defs=model_defs, series_params=series_params, series=series)
