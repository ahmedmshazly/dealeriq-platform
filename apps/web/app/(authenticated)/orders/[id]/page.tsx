"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

const STATUS_SEVERITY: Record<string, "info" | "warning" | "success" | "critical" | "neutral"> = {
  draft: "neutral",
  pending_approval: "warning",
  approved: "info",
  delivered: "success",
  cancelled: "critical",
};

export default function OrderDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const orderQuery = useQuery({
    queryKey: ["order", params.id],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/orders/{order_id}", {
        params: { path: { order_id: params.id } },
      });
      if (error) throw new ApiRequestError("Failed to load order.", response.status);
      return data;
    },
  });

  const timelineQuery = useQuery({
    queryKey: ["order-timeline", params.id],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/orders/{order_id}/timeline", {
        params: { path: { order_id: params.id } },
      });
      return data ?? [];
    },
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["order", params.id] });
    queryClient.invalidateQueries({ queryKey: ["order-timeline", params.id] });
    queryClient.invalidateQueries({ queryKey: ["orders"] });
  }

  const submit = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/orders/{order_id}/submit", {
        params: { path: { order_id: params.id } },
      });
      if (error) throw new Error("Failed to submit order.");
    },
    onSuccess: invalidate,
    onError: () => setErrorMessage("Could not submit this order."),
  });

  const approve = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/orders/{order_id}/approve", {
        params: { path: { order_id: params.id } },
      });
      if (error) throw new Error("Failed to approve order.");
    },
    onSuccess: invalidate,
    onError: () => setErrorMessage("Could not approve this order (do you have orders:approve?)."),
  });

  const deliver = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/orders/{order_id}/deliver", {
        params: { path: { order_id: params.id } },
      });
      if (error) throw new Error("Failed to deliver order.");
    },
    onSuccess: invalidate,
    onError: () => setErrorMessage("Could not deliver this order."),
  });

  const cancel = useMutation({
    mutationFn: async (reason: string) => {
      const { error } = await api.POST("/api/v1/orders/{order_id}/cancel", {
        params: { path: { order_id: params.id } },
        body: { reason },
      });
      if (error) throw new Error("Failed to cancel order.");
    },
    onSuccess: invalidate,
    onError: () => setErrorMessage("Could not cancel this order."),
  });

  if (orderQuery.error instanceof ApiRequestError && orderQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view this order.
      </Card>
    );
  }
  if (!orderQuery.data) return null;

  const order = orderQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push("/orders")}
            className="mb-2 text-xs text-text-muted underline"
          >
            ← Back to orders
          </button>
          <h1 className="text-2xl font-bold text-text-primary">Order</h1>
        </div>
        <Badge severity={STATUS_SEVERITY[order.status]}>{order.status}</Badge>
      </div>

      {errorMessage && (
        <p className="rounded-control border border-critical-border bg-critical-bg p-3 text-xs text-critical-fg">
          {errorMessage}
        </p>
      )}

      <Card className="p-6">
        <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase text-text-muted">Negotiated price</dt>
            <dd className="font-mono">${order.negotiated_price.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-text-muted">Discount</dt>
            <dd className="font-mono">${order.discount.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-text-muted">Payment</dt>
            <dd>{order.payment_type}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-text-muted">Margin</dt>
            <dd className="font-mono">
              {order.margin == null ? "— (Manager+ only)" : `$${order.margin.toFixed(2)}`}
            </dd>
          </div>
        </dl>

        <div className="mt-6 flex flex-wrap gap-3">
          {order.status === "draft" && (
            <Button onClick={() => submit.mutate()} disabled={submit.isPending}>
              Submit
            </Button>
          )}
          {order.status === "pending_approval" && (
            <Button onClick={() => approve.mutate()} disabled={approve.isPending}>
              Approve
            </Button>
          )}
          {order.status === "approved" && (
            <Button onClick={() => deliver.mutate()} disabled={deliver.isPending}>
              Deliver
            </Button>
          )}
          {(order.status === "approved" || order.status === "pending_approval") && (
            <Button
              variant="destructive"
              onClick={() => {
                const reason = window.prompt("Reason for cancellation?");
                if (reason) cancel.mutate(reason);
              }}
              disabled={cancel.isPending}
            >
              Cancel
            </Button>
          )}
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-text-primary">Timeline</h2>
        <ol className="flex flex-col gap-3">
          {(timelineQuery.data ?? []).map((event) => (
            <li key={event.id} className="flex items-center gap-3 text-sm">
              <span className="font-mono text-xs text-text-muted">
                {new Date(event.at).toLocaleString()}
              </span>
              <span>
                {event.from_status || "—"} → <strong>{event.to_status}</strong>
              </span>
              {event.reason && <span className="text-xs text-text-muted">({event.reason})</span>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
