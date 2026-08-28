"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import type { ApiResponse } from "@/lib/api-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

type Alert = ApiResponse<"/api/v1/alerts", "get">["alerts"][number];

const STATUSES = ["", "open", "acknowledged", "resolved"] as const;
const SEVERITIES = ["", "info", "warning", "critical"] as const;

const SEVERITY_BADGE: Record<string, "info" | "warning" | "critical"> = {
  info: "info",
  warning: "warning",
  critical: "critical",
};

const STATUS_BADGE: Record<string, "success" | "warning" | "info" | "neutral"> = {
  open: "warning",
  acknowledged: "info",
  resolved: "success",
};

export function AlertsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<string>("");
  const [severity, setSeverity] = useState<string>("");

  const alertsQuery = useQuery({
    queryKey: ["alerts", status, severity],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/alerts", {
        params: {
          query: {
            ...(status ? { status } : {}),
            ...(severity ? { severity } : {}),
          },
        },
      });
      if (error) throw new ApiRequestError("Failed to load alerts.", response.status);
      return data;
    },
  });

  const acknowledge = useMutation({
    mutationFn: async (alertId: string) => {
      const { error } = await api.POST("/api/v1/alerts/{alert_id}/acknowledge", {
        params: { path: { alert_id: alertId } },
      });
      if (error) throw new Error("Failed to acknowledge alert.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const resolve = useMutation({
    mutationFn: async (alertId: string) => {
      const { error } = await api.POST("/api/v1/alerts/{alert_id}/resolve", {
        params: { path: { alert_id: alertId } },
      });
      if (error) throw new Error("Failed to resolve alert.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  if (alertsQuery.error instanceof ApiRequestError && alertsQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view alerts (requires{" "}
        <code className="font-mono">alerts:view</code>).
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-text-primary">Alerts</h1>
          {alertsQuery.data && (
            <Badge severity="critical" shape="pill">
              {alertsQuery.data.badge_count} open
            </Badge>
          )}
        </div>
        <p className="text-sm text-text-secondary">
          The six built-in alert rules (FR-061): stock reorder point, vehicle aging, sales
          anomalies, forecast stockout risk, discount approval, idle leads.
        </p>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-secondary">Status:</span>
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`rounded-control border px-2.5 py-1 text-xs capitalize ${
                status === s
                  ? "border-primary-600 bg-primary-50 text-primary-700"
                  : "border-border-hairline text-text-secondary"
              }`}
            >
              {s === "" ? "All" : s}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-secondary">Severity:</span>
          {SEVERITIES.map((s) => (
            <button
              key={s}
              onClick={() => setSeverity(s)}
              className={`rounded-control border px-2.5 py-1 text-xs capitalize ${
                severity === s
                  ? "border-primary-600 bg-primary-50 text-primary-700"
                  : "border-border-hairline text-text-secondary"
              }`}
            >
              {s === "" ? "All" : s}
            </button>
          ))}
        </div>
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Rule</th>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {(alertsQuery.data?.alerts ?? []).map((alert: Alert) => (
              <tr key={alert.id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3 font-mono text-xs">{alert.rule_key}</td>
                <td className="px-4 py-3">
                  <Badge severity={SEVERITY_BADGE[alert.severity]}>{alert.severity}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge severity={STATUS_BADGE[alert.status] ?? "neutral"}>{alert.status}</Badge>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-text-muted">
                  {new Date(alert.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right">
                  {alert.status === "open" && (
                    <Button
                      className="text-xs"
                      onClick={() => acknowledge.mutate(alert.id)}
                      disabled={acknowledge.isPending}
                    >
                      Acknowledge
                    </Button>
                  )}
                  {alert.status === "acknowledged" && (
                    <Button
                      className="text-xs"
                      onClick={() => resolve.mutate(alert.id)}
                      disabled={resolve.isPending}
                    >
                      Resolve
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {alertsQuery.data?.alerts.length === 0 && (
          <p className="p-6 text-center text-sm text-text-muted">No alerts match this filter.</p>
        )}
      </Card>
    </div>
  );
}
