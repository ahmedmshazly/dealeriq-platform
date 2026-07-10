"""Transaction-level anomaly detection (DS-ANO-003): orders whose negotiated price is
suspiciously below what that model's own historical discounting pattern would predict.

Works in discount *fraction* space (`1 - negotiated_price/list_price`), not raw dollar amount —
matching Phase 3's own pricing-error injector (`infra/seed/generate.py`'s
`_inject_pricing_errors`) exactly, since this detector's whole point is to recover that
injector's ground truth (QA-003b). An order is flagged when its own discount fraction exceeds
`mean_fraction + k*sigma_fraction` for that model — equivalently, `negotiated_price` falls below
`list_price * (1 - mean_fraction - k*sigma_fraction)`. Models with fewer than
`MIN_ORDERS_FOR_DISCOUNT_STATS` historical orders are skipped — sigma is not meaningfully
estimable from a handful of points, mirroring the exact floor the generator used when injecting
these same errors (`MIN_ORDERS_FOR_PRICING_STATS=5`).
"""

import dataclasses

import numpy as np

MIN_ORDERS_FOR_DISCOUNT_STATS = 5
DEFAULT_K = 3.0


@dataclasses.dataclass(frozen=True)
class OrderRecord:
    order_id: str
    model_id: str
    list_price: float
    negotiated_price: float


@dataclasses.dataclass(frozen=True)
class TransactionAnomaly:
    order_id: str
    model_id: str
    observed: float
    expected_floor: float
    discount_fraction_mean: float
    discount_fraction_std: float


def detect_transaction_anomalies(
    orders: list[OrderRecord], *, k: float = DEFAULT_K
) -> list[TransactionAnomaly]:
    by_model: dict[str, list[OrderRecord]] = {}
    for order in orders:
        by_model.setdefault(order.model_id, []).append(order)

    anomalies: list[TransactionAnomaly] = []
    for model_id, model_orders in by_model.items():
        if len(model_orders) < MIN_ORDERS_FOR_DISCOUNT_STATS:
            continue
        fractions = np.array(
            [1.0 - o.negotiated_price / o.list_price for o in model_orders], dtype=float
        )
        mean = float(np.mean(fractions))
        std = float(np.std(fractions))
        if std <= 0.0:
            continue
        threshold_fraction = mean + k * std
        for order, fraction in zip(model_orders, fractions, strict=True):
            if fraction > threshold_fraction:
                floor = order.list_price * (1.0 - threshold_fraction)
                anomalies.append(
                    TransactionAnomaly(
                        order_id=order.order_id,
                        model_id=model_id,
                        observed=order.negotiated_price,
                        expected_floor=floor,
                        discount_fraction_mean=mean,
                        discount_fraction_std=std,
                    )
                )
    return anomalies
