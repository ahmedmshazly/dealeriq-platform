"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useAuth } from "@/lib/auth-context";
import type { ApiResponse } from "@/lib/api-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

type Customer = ApiResponse<"/api/v1/customers", "get">["items"][number];
type VehicleModel = ApiResponse<"/api/v1/vehicle-models", "get">[number];

// Mirrors apps/api/src/dealeriq_api/domain/lead_state_machine.py - UI-only convenience so we
// only offer buttons for transitions the server will actually accept; the server is still the
// real enforcement point.
const NEXT_STATUSES: Record<string, string[]> = {
  new: ["contacted", "lost"],
  contacted: ["test_drive", "negotiating", "lost"],
  test_drive: ["negotiating", "lost"],
  negotiating: ["won", "lost"],
  won: [],
  lost: [],
};

const STATUS_SEVERITY: Record<string, "info" | "warning" | "success" | "critical" | "neutral"> = {
  new: "info",
  contacted: "info",
  test_drive: "warning",
  negotiating: "warning",
  won: "success",
  lost: "critical",
};

export function LeadsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ customer_id: "", model_id: "", budget_band: "" });

  const leadsQuery = useQuery({
    queryKey: ["leads"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/leads");
      if (error) throw new ApiRequestError("Failed to load leads.", response.status);
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

  const modelsQuery = useQuery({
    queryKey: ["vehicle-models"],
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/vehicle-models");
      return data;
    },
  });

  const createLead = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/leads", {
        body: {
          customer_id: form.customer_id,
          model_id: form.model_id,
          budget_band: form.budget_band,
          owner_id: user!.id,
        },
      });
      if (error) throw new Error("Failed to create lead.");
    },
    onSuccess: () => {
      setForm({ customer_id: "", model_id: "", budget_band: "" });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  const transitionLead = useMutation({
    mutationFn: async (vars: { id: string; target_status: string }) => {
      const { error } = await api.POST("/api/v1/leads/{lead_id}/transition", {
        params: { path: { lead_id: vars.id } },
        body: { target_status: vars.target_status as "won" },
      });
      if (error) throw new Error("Failed to transition lead.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["leads"] }),
  });

  if (leadsQuery.error instanceof ApiRequestError && leadsQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view leads (requires{" "}
        <code className="font-mono">leads:view</code>).
      </Card>
    );
  }

  const customerById = new Map((customersQuery.data?.items ?? []).map((c: Customer) => [c.id, c]));
  const modelById = new Map((modelsQuery.data ?? []).map((m: VehicleModel) => [m.id, m]));

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createLead.mutate();
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Leads</h1>
        <p className="text-sm text-text-secondary">
          A validated status funnel (FR-031); Sales edit only their own leads (FR-012).
        </p>
      </div>

      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-text-primary">New lead (assigned to you)</h2>
        <form onSubmit={handleSubmit} className="flex flex-wrap gap-3">
          <select
            className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            value={form.customer_id}
            onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
            required
          >
            <option value="">Customer...</option>
            {(customersQuery.data?.items ?? []).map((c: Customer) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            value={form.model_id}
            onChange={(e) => setForm({ ...form, model_id: e.target.value })}
            required
          >
            <option value="">Model of interest...</option>
            {(modelsQuery.data ?? []).map((m: VehicleModel) => (
              <option key={m.id} value={m.id}>
                {m.make} {m.model}
              </option>
            ))}
          </select>
          <input
            className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            placeholder="Budget band (e.g. 20k-30k)"
            value={form.budget_band}
            onChange={(e) => setForm({ ...form, budget_band: e.target.value })}
            required
          />
          <Button type="submit" disabled={createLead.isPending}>
            Create lead
          </Button>
        </form>
      </Card>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Customer</th>
              <th className="px-4 py-3">Segment</th>
              <th className="px-4 py-3">Model</th>
              <th className="px-4 py-3">Budget</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Score</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(leadsQuery.data?.items ?? []).map((lead) => (
              <tr key={lead.id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3">{customerById.get(lead.customer_id)?.name ?? "—"}</td>
                <td className="px-4 py-3 text-xs text-text-muted">{lead.rfm_segment ?? "—"}</td>
                <td className="px-4 py-3">
                  {modelById.get(lead.model_id)
                    ? `${modelById.get(lead.model_id)!.make} ${modelById.get(lead.model_id)!.model}`
                    : "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{lead.budget_band}</td>
                <td className="px-4 py-3">
                  <Badge severity={STATUS_SEVERITY[lead.status]}>{lead.status}</Badge>
                </td>
                <td className="px-4 py-3 text-xs text-text-muted">
                  {lead.conversion_probability == null ? (
                    "Not yet scored"
                  ) : (
                    <details>
                      <summary className="cursor-pointer font-mono">
                        {(lead.conversion_probability * 100).toFixed(0)}%
                      </summary>
                      <ul className="mt-1 flex flex-col gap-0.5 pl-3 text-[11px]">
                        {lead.top_features.map((feature, i) => (
                          <li key={i}>
                            {feature.label}: {feature.contribution >= 0 ? "+" : ""}
                            {feature.contribution.toFixed(2)}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </td>
                <td className="flex flex-wrap gap-2 px-4 py-3">
                  {NEXT_STATUSES[lead.status]?.map((next) => (
                    <Button
                      key={next}
                      variant="secondary"
                      onClick={() => transitionLead.mutate({ id: lead.id, target_status: next })}
                    >
                      {next.replace("_", " ")}
                    </Button>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
