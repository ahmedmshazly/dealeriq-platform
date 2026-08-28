"use client";

import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

// FR-054: monthly report — sales/margin, achieved accuracy, and alert statistics for one
// completed calendar month. `month` starts empty so the server resolves and returns the most
// recently completed month (domain/monthly_report.py's most_recently_completed_month) rather
// than duplicating that resolution logic client-side; the picker then reflects whatever the
// server resolved.
export function ReportsPage() {
  const [month, setMonth] = useState("");

  const query = useQuery({
    queryKey: ["reports", "monthly", month],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/reports/monthly", {
        params: { query: month ? { month } : {} },
      });
      if (!response.ok) {
        throw new ApiRequestError("Failed to load the monthly report.", response.status);
      }
      return data;
    },
  });

  if (query.error instanceof ApiRequestError && query.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view monthly reports (requires{" "}
        <code className="font-mono">dashboard:view_manager</code>).
      </Card>
    );
  }

  const d = query.data;
  const pickerValue = month || (d ? d.month.slice(0, 7) : "");
  const isBadRequest = query.error instanceof ApiRequestError && query.error.status === 400;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Monthly report</h1>
          <p className="text-sm text-text-secondary">
            Sales, margin, achieved forecast accuracy, and alert activity for one completed month.
          </p>
        </div>
        <Input
          type="month"
          value={pickerValue}
          onChange={(e) => setMonth(e.target.value)}
          className="w-auto"
        />
      </div>

      {isBadRequest && (
        <Card className="p-6 text-sm text-critical-fg">
          That month can&apos;t be reported on yet — pick a month that has already fully
          completed.
        </Card>
      )}

      {!d && !isBadRequest && (
        <Card className="p-6 text-sm text-text-muted">Loading…</Card>
      )}

      {d && (
        <>
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="p-6">
              <h2 className="mb-2 text-sm font-semibold text-text-primary">Total revenue</h2>
              <p className="text-2xl font-bold text-text-primary">
                ${d.total_revenue.toLocaleString()}
              </p>
            </Card>
            <Card className="p-6">
              <h2 className="mb-2 text-sm font-semibold text-text-primary">Total margin</h2>
              <p className="text-2xl font-bold text-text-primary">
                ${d.total_margin.toLocaleString()}
              </p>
            </Card>
          </div>

          <Card className="overflow-hidden">
            <h2 className="p-6 pb-0 text-sm font-semibold text-text-primary">
              Achieved forecast accuracy
            </h2>
            <p className="px-6 pb-4 text-xs text-text-muted">
              Real out-of-sample accuracy per series for this month — distinct from
              training-time cross-validation metrics.
            </p>
            {d.achieved_accuracy.length === 0 ? (
              <p className="p-6 pt-0 text-sm text-text-muted">
                No series has forecast history old enough to score yet.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
                  <tr>
                    <th className="px-4 py-3">Series</th>
                    <th className="px-4 py-3">Achieved MASE</th>
                    <th className="px-4 py-3">Weeks evaluated</th>
                  </tr>
                </thead>
                <tbody>
                  {d.achieved_accuracy.map((a) => (
                    <tr key={a.series_key} className="border-b border-border-hairline last:border-0">
                      <td className="px-4 py-3 font-mono text-xs">{a.series_key}</td>
                      <td className="px-4 py-3 font-mono text-xs">{a.mase.toFixed(3)}</td>
                      <td className="px-4 py-3 font-mono text-xs">{a.n_weeks_evaluated}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card className="p-6">
              <h2 className="mb-4 text-sm font-semibold text-text-primary">
                Alerts by rule ({d.alert_statistics.total} total)
              </h2>
              <ul className="flex flex-col gap-2 text-sm">
                {Object.entries(d.alert_statistics.counts_by_rule).map(([rule, count]) => (
                  <li key={rule} className="flex justify-between">
                    <span className="font-mono text-xs">{rule}</span>
                    <span className="font-semibold">{count}</span>
                  </li>
                ))}
                {Object.keys(d.alert_statistics.counts_by_rule).length === 0 && (
                  <li className="text-text-muted">No alerts this month.</li>
                )}
              </ul>
            </Card>
            <Card className="p-6">
              <h2 className="mb-4 text-sm font-semibold text-text-primary">Alerts by severity</h2>
              <ul className="flex flex-col gap-2 text-sm">
                {Object.entries(d.alert_statistics.counts_by_severity).map(([severity, count]) => (
                  <li key={severity} className="flex justify-between">
                    <span className="font-mono text-xs">{severity}</span>
                    <span className="font-semibold">{count}</span>
                  </li>
                ))}
                {Object.keys(d.alert_statistics.counts_by_severity).length === 0 && (
                  <li className="text-text-muted">No alerts this month.</li>
                )}
              </ul>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
