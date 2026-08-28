# Feature Specification: Benchmark & Paper

**Feature Branch**: `011-benchmark-paper`

**Created**: 2026-07-12

**Status**: Draft

**Input**: SRS DIQ-SRS-001 v1.0.0 §13 Phase 10 - "DS-OPS-004, §15"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reader can see a rigorous, statistically-grounded method comparison (Priority: P1)

As a reader evaluating this project's forecasting claims, I want to see, across multiple
independently-generated synthetic datasets spanning every demand pattern (smooth, erratic,
intermittent, lumpy), how each candidate forecasting method actually performs - not just a
single lucky run - with a real statistical test showing whether the winning method's advantage
is genuine or noise, and an honest discussion of what a synthetic-data benchmark can and can't
prove.

**Why this priority**: This is the project's own stated scientific contribution (§15's working
title and protocol) and the phase's own named exit criterion ("reproducible benchmark artifact").

**Independent Test**: Run the benchmark; confirm it produces real per-method, per-demand-pattern
accuracy figures across multiple independent datasets, a real paired statistical test result
(not a placeholder), and that the paper's own limitations section is genuine, not boilerplate.

**Acceptance Scenarios**:

1. **Given** several independently-generated synthetic datasets, each spanning all four demand
   patterns, **When** the benchmark runs, **Then** every candidate method is evaluated on every
   series via the same rolling-origin backtesting procedure already used operationally, and
   accuracy is reported per demand pattern, not just an overall average (DS-OPS-004, §15).
2. **Given** the resulting per-series accuracy figures, **When** the paper reports whether the
   best-performing method's advantage is real, **Then** it includes an actual paired statistical
   comparison across series (not just "method A is highest on average"), so a reader can judge
   significance, not just ranking (§15).
3. **Given** the benchmark is built entirely on synthetic data, **When** the paper draws
   conclusions, **Then** it explicitly discloses that limitation and does not overstate what a
   synthetic benchmark proves about real dealership data (§15).

---

### User Story 2 - Anyone can reproduce the exact benchmark with one command (Priority: P1)

As anyone checking this project's claims, I want to run a single command and get back the same
kind of results (methodology, structure) the paper reports, using the same code path the paper's
own numbers came from, so the benchmark is a real, checkable artifact rather than a one-off
report I have to take on faith.

**Why this priority**: Reproducibility is this project's foundational discipline (NFR-007,
Principle IX) applied to its own research claim - a benchmark nobody else can re-run isn't
evidence, it's an assertion.

**Independent Test**: On a clean checkout, run the one reproduction command; confirm it produces
a results file and a leaderboard summary without any manual steps beyond the single command, and
that the leaderboard's structure matches what the paper describes.

**Acceptance Scenarios**:

1. **Given** a clean checkout with the project's standard toolchain installed, **When** the
   single reproduction command runs, **Then** it produces a raw results dataset and a
   human-readable leaderboard summarizing method performance per demand pattern, with zero
   manual steps beyond that one command (DS-OPS-004).
2. **Given** the benchmark has already produced results once, **When** it's re-run with the same
   configuration, **Then** the same random seeds produce the same datasets, so results are
   deterministic and comparable across runs (matching every other analytics job in this system).

---

### User Story 3 - A reader understands how the benchmark connects to the operational system (Priority: P2)

As a reader who's seen the benchmark numbers, I want the paper to explain how forecast accuracy
actually feeds real dealership decisions (reorder points, stockout alerts) in this system, so
the benchmark reads as evidence for a working system, not an abstract academic exercise
disconnected from what was actually built.

**Why this priority**: P2 - §15's own protocol step 5, valuable applied context but not required
for the benchmark's own statistical validity (User Story 1) or its reproducibility
(User Story 2).

**Independent Test**: Read the paper's operational-integration section; confirm it references
real, already-built system behavior (how a forecast becomes a reorder point, how a
forecast-implied stockout becomes an alert) rather than a hypothetical description.

**Acceptance Scenarios**:

1. **Given** the paper's operational-integration section, **When** a reader reads it, **Then**
   it describes, with reference to what the system actually does today, how a forecast's output
   flows into a reorder point and a stockout alert (§15).

### Edge Cases

- What happens if a candidate method fails to fit on a particular series (e.g. a numerical
  convergence failure)? That series/method combination is recorded as a real failure in the
  results data, not silently dropped or replaced with a fabricated number - the leaderboard and
  paper disclose the failure rate if nonzero.
- What happens if the paired statistical test's assumptions are questionable for a given
  demand-pattern subgroup (e.g. too few series in a class for the test to be meaningful)? The
  paper reports the actual sample size for every statistical claim and does not present a test
  result computed on an inadequately small sample as if it were conclusive.
- What happens if a re-run of the benchmark on the same configuration produces different results
  due to an environment difference (e.g. a library version change)? The reproduction artifact
  records the exact tool/library versions used, so a discrepancy is diagnosable rather than
  silently accepted as noise.

## Requirements *(mandatory)*

### Functional Requirements

- **DS-OPS-004**: The benchmark SHALL be runnable as a single command, producing a raw results
  dataset and a human-readable leaderboard summary, without requiring any database or running
  service.
- **§15 protocol step 1**: The benchmark SHALL evaluate methods across multiple independently
  generated synthetic datasets (not a single dataset), each spanning all four demand patterns.
- **§15 protocol step 3**: Method evaluation SHALL use the same rolling-origin backtesting
  procedure already validated and used operationally by the weekly forecast job.
- **§15 protocol step 4**: The paper SHALL report accuracy (scale-free error, percentage error,
  probabilistic-forecast quality, and interval-coverage metrics) broken down by demand pattern,
  include a real paired statistical comparison across series, and explicitly disclose the
  synthetic-data limitation.
- **§15 protocol step 5**: The paper SHALL discuss how forecast output integrates into the
  system's real operational behavior (reorder points, stockout alerting).
- **§15 deliverables**: The benchmark artifact and a paper draft SHALL both be committed to the
  repository, and the paper SHALL be renderable to a final readable form using only tools already
  available in this project's standard environment.

### Key Entities

*(names describe the concepts introduced; exact schema is a planning-phase decision.)*

- **Benchmark run**: one full execution of the harness across all configured datasets and
  methods - a random seed per dataset, the set of methods evaluated, and a timestamp, so a
  specific run's provenance is always traceable.
- **Per-series result**: one method's accuracy metrics on one series from one dataset - the
  atomic unit both the leaderboard aggregation and the paired statistical test are built from.
- **Leaderboard**: the human-readable rollup of per-series results into per-method,
  per-demand-pattern summary statistics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The benchmark evaluates every candidate method against every series across
  multiple independently-generated synthetic datasets and produces real, non-fabricated
  per-demand-pattern accuracy figures for each.
- **SC-002**: The paper includes a real paired statistical comparison (not just an average-based
  ranking) showing whether the best method's advantage over the baseline is statistically
  distinguishable from noise, with the real sample size disclosed.
- **SC-003**: The one-command reproduction produces a results dataset and leaderboard on a clean
  checkout with zero manual steps beyond that command, and re-running it with the same
  configuration reproduces the same datasets (deterministic given the seed).
- **SC-004**: The paper draft renders to a final, readable document using only tools already
  available in this project's environment, with zero fabricated numbers - every figure in the
  paper traces back to the benchmark's own output.
- **SC-005**: The paper's limitations section explicitly and honestly discloses the synthetic-
  data bias rather than presenting the benchmark's conclusions as generalizing to real dealership
  data without qualification.

## Assumptions

- **The candidate method pool is exactly the set already implemented and operationally used**
  (Naive, Seasonal Naive, Simple Exponential Smoothing, ETS, AutoARIMA, Croston, SBA, TSB) - no
  new forecasting method is introduced this phase; the benchmark's contribution is rigorous
  *evaluation* of what already exists, not new methods.
- **The number of independent synthetic datasets is chosen to balance statistical power against
  runtime**: each dataset's full evaluation (all methods × all series) takes on the order of 15
  minutes based on the single-dataset run already measured in an earlier phase. A handful of
  independent datasets (each already spanning all four demand patterns on its own) yields several
  hundred paired per-series observations for the statistical comparison - enough for a
  meaningful paired test - while keeping total runtime on the order of an hour, not many hours.
  The exact count is a planning-phase decision, documented with this reasoning.
- **The optional public dataset (§15 protocol step 2) is out of scope for this phase.** No
  public retail/vehicle-sales dataset can be sourced, licensed, and vendored into the repository
  with confidence about licensing and long-term reproducibility within this phase's scope; the
  SRS itself marks this step optional. Recorded as a backlog item for a future revisit rather
  than built now.
- **The paper targets whatever document-preparation tooling is already available in this
  project's environment** for producing a final, renderable document - no new toolchain
  installation is required to view the deliverable in its intended final form.
- **The paper is a draft, not a submission-ready manuscript** - §15 itself frames the target
  venue as "arXiv preprint + portfolio write-up," and this phase's own exit criterion is "paper
  draft," not peer-review-ready copy.
