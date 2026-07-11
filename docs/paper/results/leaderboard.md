# Benchmark Leaderboard

198 total series (0 degenerate, excluded below).

## Mean accuracy by demand pattern and method

| SBC class | Method | n series | MASE | sMAPE | Pinball q10 | Pinball q50 | Pinball q90 | 80% coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| erratic | AutoARIMA | 27 | 0.763 | 91.1% | 0.54 | 1.51 | 1.03 | 89% |
| erratic | AutoETS | 27 | 0.774 | 91.5% | 0.57 | 1.53 | 1.03 | 88% |
| erratic | CrostonClassic | 27 | 0.780 | 91.6% | 0.68 | 1.54 | 1.15 | 60% |
| erratic | CrostonSBA | 27 | 0.766 | 91.4% | 0.66 | 1.52 | 1.17 | 60% |
| erratic | Naive | 27 | 1.013 | 112.3% | 1.87 | 1.97 | 1.87 | 96% |
| erratic | SESOpt | 27 | 0.780 | 91.8% | 0.68 | 1.54 | 1.15 | 61% |
| erratic | SeasonalNaive | 27 | 0.999 | 112.2% | 1.16 | 1.98 | 1.19 | 79% |
| erratic | TSB | 27 | 0.779 | 91.7% | 0.67 | 1.54 | 1.15 | 60% |
| intermittent | AutoARIMA | 86 | 0.916 | 146.6% | 0.11 | 0.34 | 0.20 | 88% |
| intermittent | AutoETS | 86 | 0.919 | 147.1% | 0.12 | 0.34 | 0.21 | 88% |
| intermittent | CrostonClassic | 86 | 0.940 | 146.1% | 0.12 | 0.35 | 0.24 | 62% |
| intermittent | CrostonSBA | 86 | 0.924 | 146.8% | 0.12 | 0.34 | 0.24 | 62% |
| intermittent | Naive | 86 | 1.024 | 85.8% | 0.38 | 0.40 | 0.39 | 97% |
| intermittent | SESOpt | 86 | 0.913 | 147.9% | 0.14 | 0.34 | 0.24 | 61% |
| intermittent | SeasonalNaive | 86 | 1.005 | 84.4% | 0.23 | 0.39 | 0.24 | 80% |
| intermittent | TSB | 86 | 0.911 | 147.2% | 0.13 | 0.34 | 0.24 | 61% |
| lumpy | AutoARIMA | 54 | 0.856 | 145.8% | 0.32 | 0.76 | 0.61 | 92% |
| lumpy | AutoETS | 54 | 0.885 | 148.2% | 0.34 | 0.77 | 0.62 | 92% |
| lumpy | CrostonClassic | 54 | 0.902 | 147.6% | 0.29 | 0.78 | 0.63 | 62% |
| lumpy | CrostonSBA | 54 | 0.883 | 147.8% | 0.29 | 0.77 | 0.63 | 62% |
| lumpy | Naive | 54 | 0.917 | 78.2% | 1.13 | 0.88 | 1.16 | 97% |
| lumpy | SESOpt | 54 | 0.840 | 149.2% | 0.33 | 0.76 | 0.63 | 63% |
| lumpy | SeasonalNaive | 54 | 0.995 | 80.3% | 0.70 | 0.94 | 0.72 | 85% |
| lumpy | TSB | 54 | 0.846 | 148.6% | 0.32 | 0.76 | 0.63 | 60% |
| smooth | AutoARIMA | 31 | 0.770 | 75.8% | 0.22 | 0.64 | 0.35 | 81% |
| smooth | AutoETS | 31 | 0.776 | 76.3% | 0.23 | 0.65 | 0.35 | 82% |
| smooth | CrostonClassic | 31 | 0.785 | 76.3% | 0.30 | 0.65 | 0.42 | 60% |
| smooth | CrostonSBA | 31 | 0.778 | 76.8% | 0.29 | 0.65 | 0.43 | 60% |
| smooth | Naive | 31 | 1.035 | 99.2% | 0.67 | 0.86 | 0.67 | 97% |
| smooth | SESOpt | 31 | 0.795 | 77.5% | 0.30 | 0.66 | 0.42 | 60% |
| smooth | SeasonalNaive | 31 | 1.004 | 97.7% | 0.41 | 0.84 | 0.42 | 78% |
| smooth | TSB | 31 | 0.784 | 76.5% | 0.29 | 0.65 | 0.42 | 60% |

## Champion vs. Seasonal Naive (paired Wilcoxon signed-rank on MASE)

| SBC class | n pairs | Champion win rate | Wilcoxon statistic | p-value |
|---|---:|---:|---:|---:|
| smooth | 31 | 100.0% | 0.00 | 0.0000 |
| erratic | 27 | 100.0% | 0.00 | 0.0000 |
| intermittent | 86 | 88.4% | 0.00 | 0.0000 |
| lumpy | 54 | 100.0% | 0.00 | 0.0000 |
| overall | 198 | 94.9% | 0.00 | 0.0000 |
