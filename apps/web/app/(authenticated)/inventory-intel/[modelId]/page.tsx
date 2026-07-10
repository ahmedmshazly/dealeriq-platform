"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

export default function ModelDetailPage() {
  const params = useParams<{ modelId: string }>();
  const modelId = params.modelId;

  const detailQuery = useQuery({
    queryKey: ["inventory", "model", modelId],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/inventory/models/{model_id}", {
        params: { path: { model_id: modelId } },
      });
      if (error) throw new ApiRequestError("Failed to load this model.", response.status);
      return data;
    },
  });

  if (detailQuery.error instanceof ApiRequestError && detailQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view inventory intelligence (requires{" "}
        <code className="font-mono">inventory-intel:view</code>).
      </Card>
    );
  }

  if (detailQuery.error instanceof ApiRequestError && detailQuery.error.status === 404) {
    return <Card className="p-6 text-sm text-text-secondary">This model has no inventory intelligence yet.</Card>;
  }

  const detail = detailQuery.data;
  if (!detail) {
    return <Card className="p-6 text-sm text-text-muted">Loading…</Card>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/inventory-intel" className="text-xs text-primary-600 underline">
          ← Heatmap
        </Link>
        <div className="mt-1 flex items-center gap-3">
          <h1 className="text-2xl font-bold text-text-primary">{detail.model_name}</h1>
          <Badge severity="neutral">
            {detail.abc}
            {detail.xyz}
          </Badge>
        </div>
      </div>

      <Card className="overflow-hidden">
        <h2 className="border-b border-border-hairline bg-surface-sunken px-4 py-3 text-sm font-semibold text-text-primary">
          Reorder points by branch
        </h2>
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Branch</th>
              <th className="px-4 py-3">Reorder point</th>
              <th className="px-4 py-3">Safety stock</th>
              <th className="px-4 py-3">Service level</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {detail.reorder_points.map((rp) => (
              <tr key={rp.branch_id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3">{rp.branch_name}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  {rp.reorder_point !== null ? rp.reorder_point.toFixed(1) : "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {rp.safety_stock !== null ? rp.safety_stock.toFixed(1) : "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {rp.service_level !== null ? `${(rp.service_level * 100).toFixed(0)}%` : "—"}
                </td>
                <td className="px-4 py-3 text-xs text-text-muted">{rp.skipped_reason ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card className="overflow-hidden">
        <h2 className="border-b border-border-hairline bg-surface-sunken px-4 py-3 text-sm font-semibold text-text-primary">
          Units currently on the lot
        </h2>
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">VIN</th>
              <th className="px-4 py-3">Branch</th>
              <th className="px-4 py-3">Days on lot</th>
              <th className="px-4 py-3">30-day sale probability</th>
              <th className="px-4 py-3">Risk decile</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {detail.at_risk_units.map((u) => (
              <tr key={u.unit_id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3 font-mono text-xs">{u.vin}</td>
                <td className="px-4 py-3">{u.branch_name}</td>
                <td className="px-4 py-3 font-mono text-xs">{u.days_on_lot}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  {u.p_sale_30d !== null ? `${(u.p_sale_30d * 100).toFixed(0)}%` : "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{u.risk_decile ?? "—"}</td>
                <td className="px-4 py-3">
                  {u.is_aging && <Badge severity="warning">aging</Badge>}
                  {u.risk_decile === 1 && <Badge severity="critical">worst decile</Badge>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {detail.at_risk_units.length === 0 && (
          <p className="p-6 text-center text-sm text-text-muted">No units currently on the lot for this model.</p>
        )}
      </Card>
    </div>
  );
}
