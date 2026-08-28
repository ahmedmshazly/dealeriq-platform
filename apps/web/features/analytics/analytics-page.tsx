"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import type { ApiResponse } from "@/lib/api-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

type LeaderboardEntry = ApiResponse<"/api/v1/forecasts", "get">["entries"][number];

const PATTERN_CLASSES = ["smooth", "erratic", "intermittent", "lumpy"] as const;

const PATTERN_SEVERITY: Record<string, "info" | "warning" | "success" | "critical" | "neutral"> = {
  smooth: "success",
  erratic: "warning",
  intermittent: "info",
  lumpy: "critical",
};

const RUN_STATUS_SEVERITY: Record<string, "info" | "warning" | "success" | "critical" | "neutral"> = {
  running: "info",
  succeeded: "success",
  failed: "critical",
};

export function AnalyticsPage() {
  const queryClient = useQueryClient();
  const [patternClass, setPatternClass] = useState<string>("");

  const leaderboardQuery = useQuery({
    queryKey: ["forecasts", "leaderboard", patternClass],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/forecasts", {
        params: { query: patternClass ? { pattern_class: patternClass } : {} },
      });
      if (error) throw new ApiRequestError("Failed to load the leaderboard.", response.status);
      return data;
    },
  });

  const runsQuery = useQuery({
    queryKey: ["jobs", "forecast", "runs"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/jobs/{job_name}/runs", {
        params: { path: { job_name: "forecast" } },
      });
      if (error) throw new ApiRequestError("Failed to load run history.", response.status);
      return data;
    },
    refetchInterval: (query) =>
      query.state.data?.items?.some((r) => r.status === "running") ? 2000 : false,
  });

  const triggerRun = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/jobs/{job_name}/run", {
        params: { path: { job_name: "forecast" } },
      });
      if (error) throw new Error("Failed to trigger the forecast job.");
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", "forecast", "runs"] });
      queryClient.invalidateQueries({ queryKey: ["forecasts"] });
    },
  });

  if (leaderboardQuery.error instanceof ApiRequestError && leaderboardQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view forecasts (requires{" "}
        <code className="font-mono">forecasts:view</code>).
      </Card>
    );
  }

  const latestRun = runsQuery.data?.items?.[0];
  const isRunning = latestRun?.status === "running";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Analytics</h1>
          <p className="text-sm text-text-secondary">
            Per-series champion forecasts vs. Seasonal Naive, evaluated by rolling-origin
            cross-validation (DS-FC-001..007).
          </p>
        </div>
        <Button onClick={() => triggerRun.mutate()} disabled={triggerRun.isPending || isRunning}>
          {isRunning ? "Run in progress…" : "Trigger forecast run"}
        </Button>
      </div>

      {latestRun && (
        <Card className="flex items-center gap-3 p-4 text-sm">
          <span className="text-text-secondary">Latest run:</span>
          <Badge severity={RUN_STATUS_SEVERITY[latestRun.status]}>{latestRun.status}</Badge>
          <span className="font-mono text-xs text-text-muted">
            {new Date(latestRun.started_at).toLocaleString()}
          </span>
          {latestRun.status === "failed" && (
            <span className="text-xs text-critical-fg">
              {String(latestRun.metrics?.error ?? "unknown error")}
            </span>
          )}
        </Card>
      )}

      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-text-secondary">Filter by demand pattern:</span>
        <button
          onClick={() => setPatternClass("")}
          className={`rounded-control border px-2.5 py-1 text-xs ${
            patternClass === ""
              ? "border-primary-600 bg-primary-50 text-primary-700"
              : "border-border-hairline text-text-secondary"
          }`}
        >
          All
        </button>
        {PATTERN_CLASSES.map((pc) => (
          <button
            key={pc}
            onClick={() => setPatternClass(pc)}
            className={`rounded-control border px-2.5 py-1 text-xs capitalize ${
              patternClass === pc
                ? "border-primary-600 bg-primary-50 text-primary-700"
                : "border-border-hairline text-text-secondary"
            }`}
          >
            {pc}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Series</th>
              <th className="px-4 py-3">Pattern</th>
              <th className="px-4 py-3">Champion</th>
              <th className="px-4 py-3">MASE</th>
              <th className="px-4 py-3">sMAPE</th>
              <th className="px-4 py-3">80% coverage</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {(leaderboardQuery.data?.entries ?? []).map((entry: LeaderboardEntry) => (
              <tr key={entry.series_key} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3">{entry.display_name}</td>
                <td className="px-4 py-3">
                  <Badge severity={PATTERN_SEVERITY[entry.pattern_class]}>{entry.pattern_class}</Badge>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{entry.champion_method}</td>
                <td className="px-4 py-3 font-mono text-xs">{entry.mase.toFixed(3)}</td>
                <td className="px-4 py-3 font-mono text-xs">{entry.smape.toFixed(1)}%</td>
                <td className="px-4 py-3 font-mono text-xs">{(entry.coverage80 * 100).toFixed(0)}%</td>
                <td className="px-4 py-3">
                  <Link
                    href={`/analytics/${encodeURIComponent(entry.series_key)}`}
                    className="text-xs text-primary-600 underline"
                  >
                    Fan chart
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {leaderboardQuery.data?.entries.length === 0 && (
          <p className="p-6 text-center text-sm text-text-muted">
            No successful forecast run yet — trigger one above.
          </p>
        )}
      </Card>
    </div>
  );
}
