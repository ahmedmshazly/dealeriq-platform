# ADR-007: Recharts for visualization

- Status: Accepted
- Date: 2026-07-10
- Requirement refs: SRS §3.4, FR-050..054, NFR-008

## Context

Dashboards need fan charts (forecast point + 80% interval band), control-chart-style anomaly
views, and a 9-cell ABC/XYZ heatmap, all free/open-source (C-01) and accessible (chart data must
have a CSV fallback per NFR-008/FR-053).

## Decision

Use Recharts (React-native, composable, free) for all chart components.

## Consequences

- `ComposedChart` (Line + Area) directly expresses the actuals/forecast/interval-band visual
  language the Brand Kit specifies (solid actuals line, dashed forecast line, translucent fill).
- Being React-native avoids a second rendering paradigm (e.g., D3-managed DOM) inside Next.js
  components.
- CSV export (FR-053) is straightforward since chart data is already plain JS arrays/objects
  passed as props, not hidden inside a canvas/WebGL abstraction.
