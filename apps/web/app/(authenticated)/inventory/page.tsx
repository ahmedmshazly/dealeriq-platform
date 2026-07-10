"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import type { ApiResponse } from "@/lib/api-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

type Branch = ApiResponse<"/api/v1/branches", "get">[number];
type VehicleModel = ApiResponse<"/api/v1/vehicle-models", "get">[number];

const STATUS_SEVERITY = {
  in_stock: "success",
  reserved: "warning",
  sold: "neutral",
  transferred: "info",
} as const;

export default function InventoryPage() {
  const queryClient = useQueryClient();
  const [branchFilter, setBranchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const [newBranch, setNewBranch] = useState({ name: "", city: "" });
  const [newModel, setNewModel] = useState({
    make: "",
    model: "",
    segment: "",
    list_price: "",
  });
  const [newUnit, setNewUnit] = useState({
    vin: "",
    model_id: "",
    branch_id: "",
    acquisition_date: new Date().toISOString().slice(0, 10),
    acquisition_cost: "",
  });

  const branchesQuery = useQuery({
    queryKey: ["branches"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/branches");
      const status = response.status;
      if (error) throw new ApiRequestError("Failed to load branches.", status);
      return data;
    },
  });

  const modelsQuery = useQuery({
    queryKey: ["vehicle-models"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/vehicle-models");
      const status = response.status;
      if (error) throw new ApiRequestError("Failed to load vehicle models.", status);
      return data;
    },
  });

  const unitsQuery = useQuery({
    queryKey: ["vehicle-units", branchFilter, statusFilter],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/vehicle-units", {
        params: {
          query: {
            ...(branchFilter ? { branch_id: branchFilter } : {}),
            ...(statusFilter ? { status: statusFilter as "in_stock" } : {}),
          },
        },
      });
      if (error) throw new ApiRequestError("Failed to load vehicle units.", response.status);
      return data;
    },
  });

  const createBranch = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/branches", { body: newBranch });
      if (error) throw new Error("Failed to create branch.");
    },
    onSuccess: () => {
      setNewBranch({ name: "", city: "" });
      queryClient.invalidateQueries({ queryKey: ["branches"] });
    },
  });

  const createModel = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/vehicle-models", {
        body: {
          make: newModel.make,
          model: newModel.model,
          segment: newModel.segment,
          list_price: Number(newModel.list_price),
        },
      });
      if (error) throw new Error("Failed to create vehicle model.");
    },
    onSuccess: () => {
      setNewModel({ make: "", model: "", segment: "", list_price: "" });
      queryClient.invalidateQueries({ queryKey: ["vehicle-models"] });
    },
  });

  const createUnit = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/vehicle-units", {
        body: {
          vin: newUnit.vin,
          model_id: newUnit.model_id,
          branch_id: newUnit.branch_id,
          acquisition_date: newUnit.acquisition_date,
          acquisition_cost: Number(newUnit.acquisition_cost),
        },
      });
      if (error) throw new Error("Failed to receive vehicle unit.");
    },
    onSuccess: () => {
      setNewUnit({
        vin: "",
        model_id: "",
        branch_id: "",
        acquisition_date: new Date().toISOString().slice(0, 10),
        acquisition_cost: "",
      });
      queryClient.invalidateQueries({ queryKey: ["vehicle-units"] });
    },
  });

  const adjustUnit = useMutation({
    mutationFn: async (vars: { id: string; new_status: string; reason: string }) => {
      const { error } = await api.POST("/api/v1/vehicle-units/{unit_id}/adjust", {
        params: { path: { unit_id: vars.id } },
        body: { new_status: vars.new_status as "in_stock", reason: vars.reason },
      });
      if (error) throw new Error("Failed to adjust unit.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["vehicle-units"] }),
  });

  if (unitsQuery.error instanceof ApiRequestError && unitsQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view inventory (requires{" "}
        <code className="font-mono">inventory:view</code>).
      </Card>
    );
  }

  const modelById = new Map((modelsQuery.data ?? []).map((m: VehicleModel) => [m.id, m]));
  const branchById = new Map((branchesQuery.data ?? []).map((b: Branch) => [b.id, b]));

  function handleCreateBranch(e: FormEvent) {
    e.preventDefault();
    createBranch.mutate();
  }
  function handleCreateModel(e: FormEvent) {
    e.preventDefault();
    createModel.mutate();
  }
  function handleCreateUnit(e: FormEvent) {
    e.preventDefault();
    createUnit.mutate();
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Inventory</h1>
        <p className="text-sm text-text-secondary">
          Vehicle models, units, and the append-only stock-movement ledger (FR-020..024).
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold text-text-primary">New branch</h2>
          <form onSubmit={handleCreateBranch} className="flex flex-col gap-2">
            <Input
              placeholder="Name"
              value={newBranch.name}
              onChange={(e) => setNewBranch({ ...newBranch, name: e.target.value })}
              required
            />
            <Input
              placeholder="City"
              value={newBranch.city}
              onChange={(e) => setNewBranch({ ...newBranch, city: e.target.value })}
              required
            />
            <Button type="submit" variant="secondary" disabled={createBranch.isPending}>
              Add branch
            </Button>
          </form>
        </Card>

        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold text-text-primary">New vehicle model</h2>
          <form onSubmit={handleCreateModel} className="flex flex-col gap-2">
            <Input
              placeholder="Make"
              value={newModel.make}
              onChange={(e) => setNewModel({ ...newModel, make: e.target.value })}
              required
            />
            <Input
              placeholder="Model"
              value={newModel.model}
              onChange={(e) => setNewModel({ ...newModel, model: e.target.value })}
              required
            />
            <Input
              placeholder="Segment"
              value={newModel.segment}
              onChange={(e) => setNewModel({ ...newModel, segment: e.target.value })}
              required
            />
            <Input
              type="number"
              placeholder="List price"
              value={newModel.list_price}
              onChange={(e) => setNewModel({ ...newModel, list_price: e.target.value })}
              required
            />
            <Button type="submit" variant="secondary" disabled={createModel.isPending}>
              Add model
            </Button>
          </form>
        </Card>

        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold text-text-primary">Receive unit</h2>
          <form onSubmit={handleCreateUnit} className="flex flex-col gap-2">
            <Input
              placeholder="VIN"
              value={newUnit.vin}
              onChange={(e) => setNewUnit({ ...newUnit, vin: e.target.value })}
              required
            />
            <select
              className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
              value={newUnit.model_id}
              onChange={(e) => setNewUnit({ ...newUnit, model_id: e.target.value })}
              required
            >
              <option value="">Model…</option>
              {(modelsQuery.data ?? []).map((m: VehicleModel) => (
                <option key={m.id} value={m.id}>
                  {m.make} {m.model}
                </option>
              ))}
            </select>
            <select
              className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
              value={newUnit.branch_id}
              onChange={(e) => setNewUnit({ ...newUnit, branch_id: e.target.value })}
              required
            >
              <option value="">Branch…</option>
              {(branchesQuery.data ?? []).map((b: Branch) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <Input
              type="date"
              value={newUnit.acquisition_date}
              onChange={(e) => setNewUnit({ ...newUnit, acquisition_date: e.target.value })}
              required
            />
            <Input
              type="number"
              placeholder="Acquisition cost"
              value={newUnit.acquisition_cost}
              onChange={(e) => setNewUnit({ ...newUnit, acquisition_cost: e.target.value })}
              required
            />
            <Button type="submit" variant="secondary" disabled={createUnit.isPending}>
              Receive
            </Button>
          </form>
        </Card>
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
          value={branchFilter}
          onChange={(e) => setBranchFilter(e.target.value)}
        >
          <option value="">All branches</option>
          {(branchesQuery.data ?? []).map((b: Branch) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <select
          className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="in_stock">In stock</option>
          <option value="reserved">Reserved</option>
          <option value="sold">Sold</option>
          <option value="transferred">Transferred</option>
        </select>
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">VIN</th>
              <th className="px-4 py-3">Model</th>
              <th className="px-4 py-3">Branch</th>
              <th className="px-4 py-3">Days on lot</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(unitsQuery.data?.items ?? []).map((u) => (
              <tr key={u.id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3 font-mono text-xs">…{u.vin.slice(-8)}</td>
                <td className="px-4 py-3">
                  {modelById.get(u.model_id)
                    ? `${modelById.get(u.model_id)!.make} ${modelById.get(u.model_id)!.model}`
                    : "—"}
                </td>
                <td className="px-4 py-3">{branchById.get(u.branch_id)?.name ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-xs">{u.days_on_lot}</td>
                <td className="px-4 py-3">
                  <Badge severity={STATUS_SEVERITY[u.status]}>{u.status}</Badge>
                </td>
                <td className="px-4 py-3">
                  {u.status === "in_stock" && (
                    <Button
                      variant="secondary"
                      onClick={() => {
                        const reason = window.prompt("Reason for transfer?");
                        if (reason) {
                          adjustUnit.mutate({ id: u.id, new_status: "transferred", reason });
                        }
                      }}
                    >
                      Transfer
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
