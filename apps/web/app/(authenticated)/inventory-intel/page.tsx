"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import type { ApiResponse } from "@/lib/api-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Fragment, useState } from "react";

type Anomaly = ApiResponse<"/api/v1/anomalies", "get">["anomalies"][number];

const ABC_LETTERS = ["A", "B", "C"] as const;
const XYZ_LETTERS = ["X", "Y", "Z"] as const;

const CELL_INTENSITY: Record<string, string> = {
  "A-X": "bg-success-bg border-success-border",
  "A-Y": "bg-success-bg border-success-border",
  "A-Z": "bg-warning-bg border-warning-border",
  "B-X": "bg-info-bg border-info-border",
  "B-Y": "bg-surface-sunken border-border-hairline",
  "B-Z": "bg-warning-bg border-warning-border",
  "C-X": "bg-surface-sunken border-border-hairline",
  "C-Y": "bg-surface-sunken border-border-hairline",
  "C-Z": "bg-critical-bg border-critical-border",
};

const RUN_STATUS_SEVERITY: Record<string, "info" | "warning" | "success" | "critical" | "neutral"> = {
  running: "info",
  succeeded: "success",
  failed: "critical",
};

const SEVERITY_BADGE = (severity: number): "critical" | "warning" | "info" => {
  if (severity >= 3) return "critical";
  if (severity >= 1.5) return "warning";
  return "info";
};

export default function InventoryIntelPage() {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<string>("");

  const heatmapQuery = useQuery({
    queryKey: ["inventory", "heatmap"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/inventory/abc-xyz", {});
      if (error) throw new ApiRequestError("Failed to load the ABC/XYZ heatmap.", response.status);
      return data;
    },
  });

  const anomaliesQuery = useQuery({
    queryKey: ["anomalies", scope],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/anomalies", {
        params: { query: scope ? { scope } : {} },
      });
      if (error) throw new ApiRequestError("Failed to load anomalies.", response.status);
      return data;
    },
  });

  const runsQuery = useQuery({
    queryKey: ["jobs", "inventory", "runs"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/jobs/{job_name}/runs", {
        params: { path: { job_name: "inventory" } },
      });
      if (error) throw new ApiRequestError("Failed to load run history.", response.status);
      return data;
    },
    refetchInterval: (query) =>
      query.state.data?.some((r) => r.status === "running") ? 2000 : false,
  });

  const triggerRun = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/jobs/{job_name}/run", {
        params: { path: { job_name: "inventory" } },
      });
      if (error) throw new Error("Failed to trigger the inventory job.");
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", "inventory", "runs"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["anomalies"] });
    },
  });

  if (heatmapQuery.error instanceof ApiRequestError && heatmapQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view inventory intelligence (requires{" "}
        <code className="font-mono">inventory-intel:view</code>).
      </Card>
    );
  }

  const latestRun = runsQuery.data?.[0];
  const isRunning = latestRun?.status === "running";
  const cellsByKey = new Map((heatmapQuery.data?.cells ?? []).map((c) => [`${c.abc}-${c.xyz}`, c]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Inventory Intelligence</h1>
          <p className="text-sm text-text-secondary">
            ABC/XYZ classification, reorder points, aging/survival risk, and anomaly detection
            (DS-INV-001..004, DS-ANO-001..004).
          </p>
        </div>
        <Button onClick={() => triggerRun.mutate()} disabled={triggerRun.isPending || isRunning}>
          {isRunning ? "Run in progress…" : "Trigger inventory run"}
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

      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-text-primary">ABC/XYZ Heatmap</h2>
        <div className="grid grid-cols-[auto_repeat(3,1fr)] gap-2">
          <div />
          {XYZ_LETTERS.map((xyz) => (
            <div key={xyz} className="text-center text-xs font-mono uppercase text-text-muted">
              {xyz}
            </div>
          ))}
          {ABC_LETTERS.map((abc) => (
            <Fragment key={abc}>
              <div className="flex items-center text-xs font-mono uppercase text-text-muted">
                {abc}
              </div>
              {XYZ_LETTERS.map((xyz) => {
                const cell = cellsByKey.get(`${abc}-${xyz}`);
                return (
                  <div
                    key={`${abc}-${xyz}`}
                    className={`min-h-[90px] rounded-md border p-2 text-xs ${CELL_INTENSITY[`${abc}-${xyz}`]}`}
                  >
                    <div className="mb-1 font-mono text-[10px] text-text-muted">
                      {cell?.models.length ?? 0} model{cell?.models.length === 1 ? "" : "s"}
                    </div>
                    <div className="flex flex-col gap-0.5">
                      {(cell?.models ?? []).slice(0, 4).map((m) => (
                        <Link
                          key={m.model_id}
                          href={`/inventory-intel/${m.model_id}`}
                          className="truncate text-text-primary underline decoration-dotted"
                        >
                          {m.model_name}
                        </Link>
                      ))}
                      {(cell?.models.length ?? 0) > 4 && (
                        <span className="text-text-muted">+{(cell?.models.length ?? 0) - 4} more</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>
      </Card>

      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-text-secondary">Filter anomalies by scope:</span>
        {["", "series", "transaction"].map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`rounded-control border px-2.5 py-1 text-xs capitalize ${
              scope === s
                ? "border-primary-600 bg-primary-50 text-primary-700"
                : "border-border-hairline text-text-secondary"
            }`}
          >
            {s === "" ? "All" : s}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Entity</th>
              <th className="px-4 py-3">Scope</th>
              <th className="px-4 py-3">Method</th>
              <th className="px-4 py-3">Score</th>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">ESD confirmed</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {(anomaliesQuery.data?.anomalies ?? []).map((a: Anomaly) => (
              <tr key={a.id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3">{a.display_name}</td>
                <td className="px-4 py-3 font-mono text-xs">{a.scope}</td>
                <td className="px-4 py-3 font-mono text-xs">{a.method}</td>
                <td className="px-4 py-3 font-mono text-xs">{a.score.toFixed(2)}</td>
                <td className="px-4 py-3">
                  <Badge severity={SEVERITY_BADGE(a.severity)}>{a.severity.toFixed(2)}</Badge>
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {a.esd_confirmed === null ? "n/a" : a.esd_confirmed ? "yes" : "no"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{a.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {anomaliesQuery.data?.anomalies.length === 0 && (
          <p className="p-6 text-center text-sm text-text-muted">
            No anomalies found for this run/filter.
          </p>
        )}
      </Card>
    </div>
  );
}
