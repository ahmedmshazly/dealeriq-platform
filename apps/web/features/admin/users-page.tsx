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

type Role = ApiResponse<"/api/v1/roles", "get">[number];

export function UsersAdminPage() {
  const queryClient = useQueryClient();
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("sales");
  const [lastTempPassword, setLastTempPassword] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/users");
      if (error) throw new ApiRequestError("Failed to load users.", response.status);
      return data;
    },
  });

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/roles");
      const status = response.status;
      if (error) throw new ApiRequestError("Failed to load roles.", status);
      return data;
    },
  });

  const createUser = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/users", {
        body: { email: newEmail, role_key: newRole },
      });
      if (error) throw new Error("Failed to create user.");
      return data;
    },
    onSuccess: (data) => {
      setLastTempPassword(data.temporary_password);
      setNewEmail("");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const updateUser = useMutation({
    mutationFn: async (vars: {
      id: string;
      is_active?: boolean;
      role_key?: string;
      unlock?: boolean;
    }) => {
      const { id, ...body } = vars;
      const { error } = await api.PATCH("/api/v1/users/{user_id}", {
        params: { path: { user_id: id } },
        body,
      });
      if (error) throw new Error("Failed to update user.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  function handleCreate(e: FormEvent) {
    e.preventDefault();
    setLastTempPassword(null);
    createUser.mutate();
  }

  if (usersQuery.error) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view this page (requires the{" "}
        <code className="font-mono">users:view</code> permission).
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Users</h1>
        <p className="text-sm text-text-secondary">
          Create, deactivate, reactivate, unlock, and reassign roles (FR-004, FR-005).
        </p>
      </div>

      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-text-primary">Create user</h2>
        <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5 text-sm text-text-secondary">
            Email
            <Input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              required
              className="w-64"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm text-text-secondary">
            Role
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
            >
              {(rolesQuery.data ?? []).map((role: Role) => (
                <option key={role.key} value={role.key}>
                  {role.name}
                </option>
              ))}
            </select>
          </label>
          <Button type="submit" disabled={createUser.isPending}>
            {createUser.isPending ? "Creating…" : "Create user"}
          </Button>
        </form>
        {lastTempPassword && (
          <p className="mt-4 rounded-control border border-info-border bg-info-bg p-3 font-mono text-xs text-info-fg">
            Temporary password (shown once): {lastTempPassword}
          </p>
        )}
      </Card>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(usersQuery.data?.items ?? []).map((u) => (
              <tr key={u.id} className="border-b border-border-hairline last:border-0">
                <td className="px-4 py-3">{u.email}</td>
                <td className="px-4 py-3">
                  <select
                    value={u.role_key}
                    onChange={(e) => updateUser.mutate({ id: u.id, role_key: e.target.value })}
                    className="rounded-sm border border-border-hairline bg-transparent px-2 py-1 text-xs"
                  >
                    {(rolesQuery.data ?? []).map((role: Role) => (
                      <option key={role.key} value={role.key}>
                        {role.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3">
                  {!u.is_active ? (
                    <Badge severity="neutral">Deactivated</Badge>
                  ) : u.locked_until ? (
                    <Badge severity="critical">Locked</Badge>
                  ) : u.must_change_password ? (
                    <Badge severity="warning">Pending first login</Badge>
                  ) : (
                    <Badge severity="success">Active</Badge>
                  )}
                </td>
                <td className="flex flex-wrap gap-2 px-4 py-3">
                  <Button
                    variant="secondary"
                    onClick={() => updateUser.mutate({ id: u.id, is_active: !u.is_active })}
                  >
                    {u.is_active ? "Deactivate" : "Reactivate"}
                  </Button>
                  {u.locked_until && (
                    <Button
                      variant="secondary"
                      onClick={() => updateUser.mutate({ id: u.id, unlock: true })}
                    >
                      Unlock
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
