"""NFR-003 latency benchmark: real p50/p95/mean latency for a representative set of CRUD
endpoints plus the two Phase 8 dashboard endpoints, against a real running API and the real
seeded database. Sequential requests, matching NFR-003's own framing ("p95 API latency... on a
laptop") -- this is a measurement tool, not a concurrent-load generator.

Usage (against an already-running `make dev` stack, or `make benchmark`):
    uv run python scripts/benchmark_api.py [--base-url http://localhost:8000] [--n 100]
"""

import argparse
import statistics
import sys
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_N = 100

# NFR-003: p95 < 300ms for CRUD endpoints, dashboard initial load < 2s.
ENDPOINTS: list[tuple[str, str, float]] = [
    ("GET /orders", "/api/v1/orders", 0.300),
    ("GET /customers", "/api/v1/customers", 0.300),
    ("GET /leads", "/api/v1/leads", 0.300),
    ("GET /vehicle-units", "/api/v1/vehicle-units", 0.300),
    ("GET /dashboards/manager", "/api/v1/dashboards/manager", 2.000),
    ("GET /dashboards/sales", "/api/v1/dashboards/sales", 2.000),
]


def login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def benchmark_endpoint(client: httpx.Client, path: str, n: int) -> list[float]:
    latencies = []
    for _ in range(n):
        start = time.perf_counter()
        resp = client.get(path)
        elapsed = time.perf_counter() - start
        resp.raise_for_status()
        latencies.append(elapsed)
    return latencies


def percentile(values: list[float], p: float) -> float:
    return statistics.quantiles(values, n=100, method="inclusive")[int(p) - 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="requests per endpoint")
    parser.add_argument("--email", default="manager1@dealeriq.dev")
    parser.add_argument("--password", default="SeedUser123!")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        token = login(client, args.email, args.password)
        client.headers["Authorization"] = f"Bearer {token}"

        print(f"{'Endpoint':<28} {'p50 (ms)':>10} {'p95 (ms)':>10} {'mean (ms)':>10}  target")
        print("-" * 78)

        any_missed = False
        for label, path, target_s in ENDPOINTS:
            latencies = benchmark_endpoint(client, path, args.n)
            p50 = statistics.median(latencies) * 1000
            p95 = percentile(latencies, 95) * 1000
            mean = statistics.mean(latencies) * 1000
            target_ms = target_s * 1000
            missed = p95 > target_ms
            any_missed = any_missed or missed
            marker = " MISS" if missed else " ok"
            print(
                f"{label:<28} {p50:>10.1f} {p95:>10.1f} {mean:>10.1f}  <{target_ms:.0f}ms{marker}"
            )

        if any_missed:
            print("\nOne or more endpoints missed their NFR-003 target -- see real figures above.")
        else:
            print("\nAll endpoints met their NFR-003 target.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
