"""Generator configuration (GEN-001, GEN-002) — every magic number here traces to the
per-segment parameter table in specs/004-synthetic-data/plan.md."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SegmentSpec:
    key: str
    display_name: str
    target_sbc_class: str
    mu0_range: tuple[float, float]
    dispersion_range: tuple[float, float]
    n_models: int
    list_price_range: tuple[float, float]


DEFAULT_SEGMENTS: tuple[SegmentSpec, ...] = (
    # Empirically calibrated (see docs/adr/021-synthetic-demand-volume-vs-sbc-coverage.md and
    # phase report 03-synthetic-data.md for the calibration trace): ADI/CV2 classification is far
    # more sensitive to mu0 than a priori expected, and SBC-class-reachable mu0 for smooth/erratic
    # is materially more expensive (in order-volume terms) than for intermittent/lumpy — getting
    # >=10 series into both bands costs ~15k units total, well over GEN-001's ~4-8k estimate.
    # ADR-021 documents the deliberate choice to satisfy GEN-002's four-class coverage SHALL over
    # GEN-001's approximate volume figure. Model counts below are imbalanced (more economy/sedan
    # models, fewer suv/luxury/commercial) to buy enough independent draws at the
    # classification-reachable mu0 for the two expensive classes without spending more than
    # necessary.
    SegmentSpec(
        key="economy",
        display_name="Economy/Compact",
        target_sbc_class="smooth",
        mu0_range=(1.65, 1.85),
        dispersion_range=(0.02, 0.05),
        n_models=7,
        list_price_range=(16000, 22000),
    ),
    SegmentSpec(
        key="sedan",
        display_name="Sedan/Mid-size",
        target_sbc_class="erratic",
        mu0_range=(3.2, 3.6),
        dispersion_range=(0.85, 1.0),
        n_models=6,
        list_price_range=(22000, 32000),
    ),
    SegmentSpec(
        key="suv_truck",
        display_name="SUV/Truck",
        target_sbc_class="intermittent",
        mu0_range=(0.3, 0.5),
        dispersion_range=(0.2, 0.35),
        n_models=3,
        list_price_range=(32000, 48000),
    ),
    SegmentSpec(
        key="luxury",
        display_name="Luxury/Sports",
        target_sbc_class="lumpy",
        mu0_range=(0.35, 0.5),
        dispersion_range=(12.0, 20.0),
        n_models=3,
        list_price_range=(55000, 95000),
    ),
    SegmentSpec(
        key="commercial",
        display_name="Commercial/Van",
        target_sbc_class="mixed",
        mu0_range=(0.15, 0.5),
        dispersion_range=(0.5, 2.0),
        n_models=3,
        list_price_range=(35000, 55000),
    ),
)

DEFAULT_BRANCHES: tuple[tuple[str, str, float], ...] = (
    ("Downtown Motors", "Metropolis", 1.0),
    ("Westside Auto", "Metropolis", 0.8),
    ("Airport Branch", "Gateway City", 0.6),
)

MAKES_MODELS_BY_SEGMENT: dict[str, list[tuple[str, str]]] = {
    "economy": [
        ("Toyota", "Corolla"),
        ("Honda", "Civic"),
        ("Hyundai", "Elantra"),
        ("Kia", "Forte"),
        ("Nissan", "Sentra"),
        ("Volkswagen", "Jetta"),
        ("Mazda", "Mazda3"),
    ],
    "sedan": [
        ("Toyota", "Camry"),
        ("Honda", "Accord"),
        ("Ford", "Fusion"),
        ("Nissan", "Altima"),
        ("Mazda", "Mazda6"),
        ("Hyundai", "Sonata"),
        ("Kia", "K5"),
    ],
    "suv_truck": [
        ("Ford", "F-150"),
        ("Toyota", "RAV4"),
        ("Chevrolet", "Silverado"),
        ("Jeep", "Grand Cherokee"),
        ("Honda", "CR-V"),
    ],
    "luxury": [
        ("BMW", "5 Series"),
        ("Mercedes-Benz", "E-Class"),
        ("Audi", "A6"),
        ("Porsche", "911"),
        ("Lexus", "LS"),
    ],
    "commercial": [
        ("Ford", "Transit"),
        ("Mercedes-Benz", "Sprinter"),
        ("Ram", "ProMaster"),
        ("Chevrolet", "Express"),
        ("Nissan", "NV200"),
    ],
}


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 42
    n_weeks: int = 156
    branches: tuple[tuple[str, str, float], ...] = DEFAULT_BRANCHES
    segments: tuple[SegmentSpec, ...] = DEFAULT_SEGMENTS
    makes_models_by_segment: dict[str, list[tuple[str, str]]] = field(
        default_factory=lambda: MAKES_MODELS_BY_SEGMENT
    )
    trend_std: float = 0.15
    fourier_amplitude_std: float = 0.15
    promo_min_windows: int = 8
    promo_max_windows: int = 15
    promo_min_len_weeks: int = 1
    promo_max_len_weeks: int = 3
    promo_effect_range: tuple[float, float] = (0.3, 0.8)
    per_model_jitter: float = 0.25
