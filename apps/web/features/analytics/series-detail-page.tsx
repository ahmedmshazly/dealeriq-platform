"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { downloadCsv, exportChartAsPng } from "@/lib/chart-export";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Area,
} from "recharts";

const PATTERN_SEVERITY: Record<string, "info" | "warning" | "success" | "critical" | "neutral"> = {
  smooth: "success",
  erratic: "warning",
  intermittent: "info",
  lumpy: "critical",
};

export function SeriesDetailPage() {
  const params = useParams<{ seriesKey: string }>();
  const seriesKey = decodeURIComponent(params.seriesKey);
  const chartRef = useRef<HTMLDivElement>(null);

  const detailQuery = useQuery({
    queryKey: ["forecasts", "series", seriesKey],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/forecasts/{series_key}", {
        params: { path: { series_key: seriesKey } },
      });
      if (error) throw new ApiRequestError("Failed to load this series.", response.status);
      return data;
    },
  });

  const accuracyQuery = useQuery({
    queryKey: ["forecasts", "series", seriesKey, "achieved-accuracy"],
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/api/v1/forecasts/{series_key}/achieved-accuracy",
        { params: { path: { series_key: seriesKey } } },
      );
      if (error) throw new ApiRequestError("Failed to load achieved accuracy.", response.status);
      return data;
    },
  });

  if (detailQuery.error instanceof ApiRequestError && detailQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view forecasts (requires{" "}
        <code className="font-mono">forecasts:view</code>).
      </Card>
    );
  }

  if (detailQuery.error instanceof ApiRequestError && detailQuery.error.status === 404) {
    return <Card className="p-6 text-sm text-text-secondary">This series has no forecast yet.</Card>;
  }

  const detail = detailQuery.data;
  if (!detail) {
    return <Card className="p-6 text-sm text-text-muted">Loading…</Card>;
  }

  // Merge actuals + forecast into one chart-friendly array, keyed by week_start, so the
  // interval band and the champion's point forecast render as a single continuous series.
  const chartData: Record<string, { week: string; actual?: number; forecast?: number; lo?: number; hi?: number }> = {};
  for (const point of detail.actuals) {
    chartData[point.week_start] = { week: point.week_start, actual: point.y };
  }
  for (const point of detail.forecast) {
    chartData[point.week_start] = {
      ...chartData[point.week_start],
      week: point.week_start,
      forecast: point.yhat,
      lo: point.yhat_lo80,
      hi: point.yhat_hi80 - point.yhat_lo80,
    };
  }
  const rows = Object.values(chartData).sort((a, b) => a.week.localeCompare(b.week));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/analytics" className="text-xs text-primary-600 underline">
          ← Leaderboard
        </Link>
        <div className="mt-1 flex items-center gap-3">
          <h1 className="text-2xl font-bold text-text-primary">{detail.display_name}</h1>
          <Badge severity={PATTERN_SEVERITY[detail.pattern_class]}>{detail.pattern_class}</Badge>
        </div>
        <p className="text-sm text-text-secondary">
          Champion: <span className="font-mono">{detail.champion_method}</span>
        </p>
      </div>

      <Card className="p-6">
        <div className="mb-4 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              // Recharts also renders a 14x14 <svg> icon per legend item inside this container
              //, a plain `querySelector("svg")` grabs the first one of those instead of the
              // actual chart, exporting a near-blank thumbnail. The main chart's <svg> is
              // always the direct child of .recharts-wrapper, so scope to that.
              const svg = chartRef.current?.querySelector<SVGSVGElement>(".recharts-wrapper > svg");
              if (svg) void exportChartAsPng(svg, `${seriesKey}-fan-chart.png`);
            }}
          >
            Export PNG
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              downloadCsv(
                `${seriesKey}-fan-chart.csv`,
                rows.map((r) => ({
                  week_start: r.week,
                  actual: r.actual ?? null,
                  forecast: r.forecast ?? null,
                  yhat_lo80: r.lo ?? null,
                  yhat_hi80: r.lo != null && r.hi != null ? r.lo + r.hi : null,
                })),
              )
            }
          >
            Export CSV
          </Button>
        </div>
        <div ref={chartRef}>
        <ResponsiveContainer width="100%" height={360}>
          <ComposedChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border-hairline" />
            <XAxis dataKey="week" tick={{ fontSize: 10 }} minTickGap={40} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area
              dataKey="lo"
              stackId="interval"
              stroke="none"
              fill="transparent"
              legendType="none"
              isAnimationActive={false}
            />
            <Area
              dataKey="hi"
              stackId="interval"
              name="80% interval"
              stroke="none"
              fill="var(--color-primary-200, #bfdbfe)"
              fillOpacity={0.6}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="actual"
              name="Actual"
              stroke="var(--color-neutral-700, #374151)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="forecast"
              name="Champion forecast"
              stroke="var(--color-primary-600, #2563eb)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="mb-2 text-sm font-semibold text-text-primary">
          Achieved accuracy (last {accuracyQuery.data?.n_weeks_evaluated ?? 12} weeks)
        </h2>
        <p className="mb-3 text-xs text-text-muted">
          Real out-of-sample accuracy - how far past forecasts were from what actually happened,
          distinct from the training-time cross-validation metrics below (FR-073).
        </p>
        {accuracyQuery.data?.mase == null ? (
          <p className="text-sm text-text-muted">
            Not enough history yet - no forecast for this series is old enough to have real
            actuals to compare against.
          </p>
        ) : (
          <p className="text-2xl font-bold text-text-primary">
            {accuracyQuery.data.mase.toFixed(3)}{" "}
            <span className="text-sm font-normal text-text-muted">achieved MASE</span>
          </p>
        )}
      </Card>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Method</th>
              <th className="px-4 py-3">MASE</th>
              <th className="px-4 py-3">sMAPE</th>
              <th className="px-4 py-3">Pinball q10</th>
              <th className="px-4 py-3">Pinball q50</th>
              <th className="px-4 py-3">Pinball q90</th>
              <th className="px-4 py-3">80% coverage</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {detail.metrics_by_method
              .slice()
              .sort((a, b) => a.mase - b.mase)
              .map((m) => (
                <tr key={m.method} className="border-b border-border-hairline last:border-0">
                  <td className="px-4 py-3 font-mono text-xs">{m.method}</td>
                  <td className="px-4 py-3 font-mono text-xs">{m.mase.toFixed(3)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{m.smape.toFixed(1)}%</td>
                  <td className="px-4 py-3 font-mono text-xs">{m.pinball_q10.toFixed(2)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{m.pinball_q50.toFixed(2)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{m.pinball_q90.toFixed(2)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{(m.coverage80 * 100).toFixed(0)}%</td>
                  <td className="px-4 py-3">
                    {m.is_champion && <Badge severity="success">champion</Badge>}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
