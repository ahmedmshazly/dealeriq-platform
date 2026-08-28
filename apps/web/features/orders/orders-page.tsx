"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useAuth } from "@/lib/auth-context";
import type { ApiResponse } from "@/lib/api-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { type FormEvent, useState } from "react";

type Customer = ApiResponse<"/api/v1/customers", "get">["items"][number];
type VehicleUnit = ApiResponse<"/api/v1/vehicle-units", "get">["items"][number];

const STATUS_SEVERITY: Record<string, "info" | "warning" | "success" | "critical" | "neutral"> = {
  draft: "neutral",
  pending_approval: "warning",
  approved: "info",
  delivered: "success",
  cancelled: "critical",
};

export function OrdersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    customer_id: "",
    unit_id: "",
    negotiated_price: "",
    discount: "0",
    payment_type: "cash",
  });

  const ordersQuery = useQuery({
    queryKey: ["orders"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/orders");
      if (error) throw new ApiRequestError("Failed to load orders.", response.status);
      return data;
    },
  });

  const customersQuery = useQuery({
    queryKey: ["customers"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/customers");
      return data;
    },
  });

  const unitsQuery = useQuery({
    queryKey: ["vehicle-units", "in_stock"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/vehicle-units", {
        params: { query: { status: "in_stock" } },
      });
      return data;
    },
  });

  const createOrder = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/orders", {
        body: {
          customer_id: form.customer_id,
          unit_id: form.unit_id,
          salesperson_id: user!.id,
          negotiated_price: Number(form.negotiated_price),
          discount: Number(form.discount),
          payment_type: form.payment_type as "cash",
        },
      });
      if (error) throw new Error("Failed to create order.");
      return data;
    },
    onSuccess: () => {
      setForm({ customer_id: "", unit_id: "", negotiated_price: "", discount: "0", payment_type: "cash" });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["vehicle-units"] });
    },
  });

  if (ordersQuery.error instanceof ApiRequestError && ordersQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view orders (requires{" "}
        <code className="font-mono">orders:view</code>).
      </Card>
    );
  }

  const customerById = new Map((customersQuery.data?.items ?? []).map((c: Customer) => [c.id, c]));

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createOrder.mutate();
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Orders</h1>
        <p className="text-sm text-text-secondary">
          draft → submit → pending_approval/approved → delivered, or cancelled (FR-040..045).
        </p>
      </div>

      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-text-primary">New order (draft)</h2>
        <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
          <select
            className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            value={form.customer_id}
            onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
            required
          >
            <option value="">Customer…</option>
            {(customersQuery.data?.items ?? []).map((c: Customer) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            value={form.unit_id}
            onChange={(e) => setForm({ ...form, unit_id: e.target.value })}
            required
          >
            <option value="">In-stock unit…</option>
            {(unitsQuery.data?.items ?? []).map((u: VehicleUnit) => (
              <option key={u.id} value={u.id}>
                …{u.vin.slice(-8)}
              </option>
            ))}
          </select>
          <input
            className="w-36 rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            type="number"
            placeholder="Negotiated price"
            value={form.negotiated_price}
            onChange={(e) => setForm({ ...form, negotiated_price: e.target.value })}
            required
          />
          <input
            className="w-28 rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            type="number"
            placeholder="Discount"
            value={form.discount}
            onChange={(e) => setForm({ ...form, discount: e.target.value })}
          />
          <select
            className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            value={form.payment_type}
            onChange={(e) => setForm({ ...form, payment_type: e.target.value })}
          >
            <option value="cash">Cash</option>
            <option value="finance">Finance</option>
          </select>
          <Button type="submit" disabled={createOrder.isPending}>
            Create draft
          </Button>
        </form>
      </Card>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Customer</th>
              <th className="px-4 py-3">Negotiated price</th>
              <th className="px-4 py-3">Discount</th>
              <th className="px-4 py-3">Margin</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {(ordersQuery.data?.items ?? []).map((order) => (
              <tr key={order.id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3">{customerById.get(order.customer_id)?.name ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-xs">${order.negotiated_price.toFixed(2)}</td>
                <td className="px-4 py-3 font-mono text-xs">${order.discount.toFixed(2)}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  {order.margin == null ? "—" : `$${order.margin.toFixed(2)}`}
                </td>
                <td className="px-4 py-3">
                  <Badge severity={STATUS_SEVERITY[order.status]}>{order.status}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/orders/${order.id}`} className="text-xs text-primary-600 underline">
                    Open
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
