"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";

// ADR-022's five segments.
const SEGMENT_SEVERITY: Record<string, "success" | "info" | "warning" | "neutral"> = {
  Champions: "success",
  "Loyal Customers": "info",
  "At Risk": "warning",
  Hibernating: "neutral",
  New: "neutral",
};

const ORDER_STATUS_SEVERITY: Record<string, "info" | "warning" | "success" | "critical" | "neutral"> = {
  draft: "neutral",
  pending_approval: "warning",
  approved: "info",
  delivered: "success",
  cancelled: "critical",
};

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();

  const customerQuery = useQuery({
    queryKey: ["customer", params.id],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/customers/{customer_id}", {
        params: { path: { customer_id: params.id } },
      });
      if (error) throw new ApiRequestError("Failed to load customer.", response.status);
      return data;
    },
  });

  if (customerQuery.error instanceof ApiRequestError && customerQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view this customer (requires{" "}
        <code className="font-mono">customers:view</code>).
      </Card>
    );
  }
  if (customerQuery.error instanceof ApiRequestError && customerQuery.error.status === 404) {
    return <Card className="p-6 text-sm text-critical-fg">Customer not found.</Card>;
  }
  if (!customerQuery.data) return null;

  const detail = customerQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <button
          onClick={() => router.push("/customers")}
          className="mb-2 text-xs text-text-muted underline"
        >
          ← Back to customers
        </button>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-text-primary">{detail.customer.name}</h1>
          {detail.rfm_segment && (
            <Badge severity={SEGMENT_SEVERITY[detail.rfm_segment] ?? "neutral"}>
              {detail.rfm_segment}
            </Badge>
          )}
        </div>
        <p className="text-sm text-text-secondary">
          {detail.customer.email ?? "—"} · {detail.customer.phone ?? "—"} ·{" "}
          {detail.customer.city ?? "—"}
        </p>
      </div>

      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-text-primary">RFM profile</h2>
        {detail.rfm_segment == null ? (
          <p className="text-sm text-text-muted">Not yet scored — run the customer-analytics job.</p>
        ) : detail.recency_score == null ? (
          <p className="text-sm text-text-muted">
            No purchase history yet — segmented as <strong>New</strong>.
          </p>
        ) : (
          <dl className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <dt className="text-xs uppercase text-text-muted">Recency</dt>
              <dd className="font-mono">{detail.recency_score} / 5</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-text-muted">Frequency</dt>
              <dd className="font-mono">{detail.frequency_score} / 5</dd>
            </div>
            <div>
              <dt className="text-xs uppercase text-text-muted">Monetary</dt>
              <dd className="font-mono">{detail.monetary_score} / 5</dd>
            </div>
          </dl>
        )}
      </Card>

      <Card className="overflow-hidden">
        <h2 className="p-6 pb-0 text-sm font-semibold text-text-primary">Purchase history</h2>
        {detail.orders.length === 0 ? (
          <p className="p-6 text-sm text-text-muted">No orders yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Negotiated price</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {detail.orders.map((order) => (
                <tr key={order.id} className="border-b border-border-hairline last:border-0">
                  <td className="px-4 py-3 font-mono text-xs">
                    {new Date(order.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">{order.model_name}</td>
                  <td className="px-4 py-3 font-mono">${order.negotiated_price.toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <Badge severity={ORDER_STATUS_SEVERITY[order.status]}>{order.status}</Badge>
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
