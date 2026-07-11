"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { downloadCsv, exportChartAsPng } from "@/lib/chart-export";
import { useAuth } from "@/lib/auth-context";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRef } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// FR-050: the Manager dashboard's sales-vs-forecast chart, exportable as PNG/CSV (FR-053).
function ManagerDashboard() {
  const chartRef = useRef<HTMLDivElement>(null);

  const query = useQuery({
    queryKey: ["dashboards", "manager"],
    queryFn: async () => {
      // GET /dashboards/manager has zero declared parameters, so FastAPI never documents a 403
      // response for it -- openapi-fetch's generated `error` union collapses to `never` even
      // though require_permission("dashboard:view_manager") absolutely can 403 at runtime.
      // Checking response.ok instead of the error sentinel is the established workaround
      // (see apps/web/app/(authenticated)/admin/alert-rules/page.tsx).
      const { data, response } = await api.GET("/api/v1/dashboards/manager");
      if (!response.ok) throw new ApiRequestError("Failed to load the Manager dashboard.", response.status);
      return data;
    },
  });

  if (query.error instanceof ApiRequestError && query.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view the Manager dashboard (requires{" "}
        <code className="font-mono">dashboard:view_manager</code>).
      </Card>
    );
  }
  if (!query.data) return <Card className="p-6 text-sm text-text-muted">Loading…</Card>;
  const d = query.data;

  const chartRows = d.sales_vs_forecast.map((p) => ({
    week: p.week_start,
    actual: p.actual,
    forecast: p.yhat ?? undefined,
    lo: p.yhat_lo80 ?? undefined,
    hi: p.yhat_hi80 != null && p.yhat_lo80 != null ? p.yhat_hi80 - p.yhat_lo80 : undefined,
  }));

  function handleExportPng() {
    // Recharts also renders a 14x14 <svg> icon per legend item inside this container -- a
    // plain `querySelector("svg")` grabs the first one of those instead of the actual chart,
    // exporting a near-blank thumbnail. The main chart's <svg> is always the direct child of
    // .recharts-wrapper, so scope to that.
    const svg = chartRef.current?.querySelector<SVGSVGElement>(".recharts-wrapper > svg");
    if (svg) void exportChartAsPng(svg, `sales-vs-forecast-${d!.month}.png`);
  }
  function handleExportCsv() {
    downloadCsv(
      `sales-vs-forecast-${d.month}.csv`,
      d.sales_vs_forecast.map((p) => ({
        week_start: p.week_start,
        actual: p.actual,
        yhat: p.yhat,
        yhat_lo80: p.yhat_lo80,
        yhat_hi80: p.yhat_hi80,
      })),
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">
            Sales this month vs. forecast
          </h2>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={handleExportPng}>
              Export PNG
            </Button>
            <Button variant="secondary" onClick={handleExportCsv}>
              Export CSV
            </Button>
          </div>
        </div>
        <div ref={chartRef}>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={chartRows}>
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
                name="Forecast"
                stroke="var(--color-primary-600, #2563eb)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="p-6">
          <h2 className="mb-4 text-sm font-semibold text-text-primary">Top models</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {d.top_models.map((m) => (
              <li key={m.model_id} className="flex justify-between">
                <span>{m.display_name}</span>
                <span className="font-mono">${m.revenue.toLocaleString()}</span>
              </li>
            ))}
            {d.top_models.length === 0 && <li className="text-text-muted">No sales yet.</li>}
          </ul>
        </Card>
        <Card className="p-6">
          <h2 className="mb-4 text-sm font-semibold text-text-primary">Bottom models</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {d.bottom_models.map((m) => (
              <li key={m.model_id} className="flex justify-between">
                <span>{m.display_name}</span>
                <span className="font-mono">${m.revenue.toLocaleString()}</span>
              </li>
            ))}
            {d.bottom_models.length === 0 && <li className="text-text-muted">No sales yet.</li>}
          </ul>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="p-6">
          <h2 className="mb-2 text-sm font-semibold text-text-primary">Inventory health</h2>
          <p className="text-xs text-text-muted">ABC × XYZ cell counts</p>
          <div className="mt-2 grid grid-cols-3 gap-1 text-xs">
            {Object.entries(d.inventory_abc_xyz_counts).map(([cell, count]) => (
              <div key={cell} className="rounded-control bg-surface-sunken px-2 py-1 text-center">
                <div className="font-mono">{cell}</div>
                <div className="font-semibold">{count}</div>
              </div>
            ))}
            {Object.keys(d.inventory_abc_xyz_counts).length === 0 && (
              <p className="col-span-3 text-text-muted">No inventory run yet.</p>
            )}
          </div>
          <p className="mt-3 text-xs text-text-muted">
            Aging units: <span className="font-mono">{d.aging_unit_count}</span>
          </p>
          <Link href="/inventory-intel" className="mt-2 block text-xs text-primary-600 underline">
            Open inventory intelligence →
          </Link>
        </Card>
        <Card className="p-6">
          <h2 className="mb-2 text-sm font-semibold text-text-primary">Open anomalies</h2>
          <p className="text-3xl font-bold text-text-primary">{d.open_anomaly_count}</p>
          <Link href="/inventory-intel" className="mt-2 block text-xs text-primary-600 underline">
            Open anomaly explorer →
          </Link>
        </Card>
        <Card className="p-6">
          <h2 className="mb-2 text-sm font-semibold text-text-primary">Unacknowledged alerts</h2>
          <p className="text-3xl font-bold text-text-primary">{d.unacknowledged_alert_count}</p>
          <Link href="/alerts" className="mt-2 block text-xs text-primary-600 underline">
            Open notification center →
          </Link>
        </Card>
      </div>
    </div>
  );
}

// FR-051: the Sales dashboard, scoped server-side to the current user's own data.
function SalesDashboard() {
  const query = useQuery({
    queryKey: ["dashboards", "sales"],
    queryFn: async () => {
      // Same zero-parameter openapi-fetch inference gap as the Manager dashboard above.
      const { data, response } = await api.GET("/api/v1/dashboards/sales");
      if (!response.ok) throw new ApiRequestError("Failed to load the Sales dashboard.", response.status);
      return data;
    },
  });

  if (query.error instanceof ApiRequestError && query.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view the Sales dashboard (requires{" "}
        <code className="font-mono">dashboard:view_sales</code>).
      </Card>
    );
  }
  if (!query.data) return <Card className="p-6 text-sm text-text-muted">Loading…</Card>;
  const d = query.data;
  const pct = Math.min(100, (d.my_sales_this_month / d.my_target) * 100);

  return (
    <div className="flex flex-col gap-6">
      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-text-primary">My sales this month</h2>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-text-primary">
            ${d.my_sales_this_month.toLocaleString()}
          </span>
          <span className="text-sm text-text-muted">of ${d.my_target.toLocaleString()} target</span>
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-surface-sunken">
          <div className="h-full rounded-full bg-primary-600" style={{ width: `${pct}%` }} />
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="mb-2 text-sm font-semibold text-text-primary">My notifications</h2>
        <p className="text-3xl font-bold text-text-primary">{d.unacknowledged_alert_count}</p>
        <Link href="/alerts" className="mt-2 block text-xs text-primary-600 underline">
          Open notification center →
        </Link>
      </Card>

      <Card className="overflow-hidden">
        <h2 className="p-6 pb-0 text-sm font-semibold text-text-primary">
          My open leads, ranked by conversion score
        </h2>
        {d.open_leads.length === 0 ? (
          <p className="p-6 text-sm text-text-muted">No open leads.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
              <tr>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Score</th>
              </tr>
            </thead>
            <tbody>
              {d.open_leads.map((lead) => (
                <tr key={lead.lead_id} className="border-b border-border-hairline last:border-0">
                  <td className="px-4 py-3">{lead.customer_name}</td>
                  <td className="px-4 py-3">{lead.model_name}</td>
                  <td className="px-4 py-3">
                    <Badge>{lead.status}</Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {lead.conversion_probability == null
                      ? "Not yet scored"
                      : `${(lead.conversion_probability * 100).toFixed(0)}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">
          {user?.role_key === "sales" ? "My dashboard" : "Dashboard"}
        </h1>
        <p className="text-sm text-text-secondary">
          Signed in as <span className="font-mono">{user?.email}</span> ({user?.role_key})
        </p>
      </div>

      {(user?.role_key === "admin" || user?.role_key === "manager") && <ManagerDashboard />}
      {user?.role_key === "sales" && <SalesDashboard />}
      {user?.role_key === "analyst" && (
        <Card className="p-6">
          <p className="text-sm text-text-secondary">
            The Analyst workbench lives at{" "}
            <Link href="/analytics" className="text-primary-600 underline">
              Analytics
            </Link>{" "}
            (forecast diagnostics, leaderboard, model-run history) and{" "}
            <Link href="/inventory-intel" className="text-primary-600 underline">
              Inventory Intel
            </Link>{" "}
            (ABC/XYZ heatmap, anomaly explorer).
          </p>
        </Card>
      )}
    </div>
  );
}
