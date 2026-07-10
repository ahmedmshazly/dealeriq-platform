"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

export default function CustomersPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", phone: "", email: "", city: "", source_channel: "" });
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);

  const customersQuery = useQuery({
    queryKey: ["customers"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/customers");
      if (error) throw new ApiRequestError("Failed to load customers.", response.status);
      return data;
    },
  });

  const createCustomer = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/customers", {
        body: {
          name: form.name,
          phone: form.phone || null,
          email: form.email || null,
          city: form.city || null,
          source_channel: form.source_channel || null,
        },
      });
      if (error) throw new Error("Failed to create customer.");
      return data;
    },
    onSuccess: (data) => {
      setDuplicateWarning(
        data.possible_duplicate_ids.length > 0
          ? `Possible duplicate: ${data.possible_duplicate_ids.length} existing customer(s) share this phone/email.`
          : null,
      );
      setForm({ name: "", phone: "", email: "", city: "", source_channel: "" });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createCustomer.mutate();
  }

  if (customersQuery.error instanceof ApiRequestError && customersQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view customers (requires{" "}
        <code className="font-mono">customers:view</code>).
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Customers</h1>
        <p className="text-sm text-text-secondary">
          A duplicate phone/email warns but never blocks creation (FR-030).
        </p>
      </div>

      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-text-primary">New customer</h2>
        <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Input
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <Input
            placeholder="Phone"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
          <Input
            placeholder="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <Input
            placeholder="City"
            value={form.city}
            onChange={(e) => setForm({ ...form, city: e.target.value })}
          />
          <Input
            placeholder="Source (e.g. walk-in, web)"
            value={form.source_channel}
            onChange={(e) => setForm({ ...form, source_channel: e.target.value })}
          />
          <Button type="submit" disabled={createCustomer.isPending} className="sm:col-span-2 lg:col-span-1">
            Create
          </Button>
        </form>
        {duplicateWarning && (
          <p className="mt-4 rounded-control border border-warning-border bg-warning-bg p-3 text-xs text-warning-fg">
            {duplicateWarning}
          </p>
        )}
      </Card>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">City</th>
              <th className="px-4 py-3">Source</th>
            </tr>
          </thead>
          <tbody>
            {(customersQuery.data?.items ?? []).map((c) => (
              <tr key={c.id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3">{c.name}</td>
                <td className="px-4 py-3 font-mono text-xs">{c.phone ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-xs">{c.email ?? "—"}</td>
                <td className="px-4 py-3">{c.city ?? "—"}</td>
                <td className="px-4 py-3">{c.source_channel ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
