"use client";

import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

// FR-081: browse/filter the append-only audit log.
export function AuditLogAdminPage() {
  const [actionFilter, setActionFilter] = useState("");

  const auditQuery = useQuery({
    queryKey: ["audit-log", actionFilter],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/audit-log", {
        params: { query: actionFilter ? { action: actionFilter } : {} },
      });
      if (error) throw new ApiRequestError("Failed to load the audit log.", response.status);
      return data;
    },
  });

  if (auditQuery.error) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view this page (requires the{" "}
        <code className="font-mono">audit_log:view</code> permission).
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Audit log</h1>
        <p className="text-sm text-text-secondary">
          Append-only record of auth events, role changes, and account updates (FR-080/081).
        </p>
      </div>

      <label className="flex max-w-xs flex-col gap-1.5 text-sm text-text-secondary">
        Filter by action
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded-control border border-border-strong bg-surface-raised px-3 py-2 text-sm"
        >
          <option value="">All actions</option>
          <option value="auth.login_succeeded">Login succeeded</option>
          <option value="auth.login_failed">Login failed</option>
          <option value="auth.login_blocked_locked">Login blocked (locked)</option>
          <option value="auth.refresh_reuse_detected">Refresh reuse detected</option>
          <option value="auth.logout_all">Logout all</option>
          <option value="auth.password_changed">Password changed</option>
          <option value="user.created">User created</option>
          <option value="user.updated">User updated</option>
        </select>
      </label>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Actor</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Entity</th>
              <th className="px-4 py-3">IP</th>
            </tr>
          </thead>
          <tbody>
            {(auditQuery.data?.items ?? []).map((row) => (
              <tr key={row.id} className="border-b border-border-hairline last:border-0">
                <td className="whitespace-nowrap px-4 py-3 font-mono text-xs">
                  {new Date(row.at).toLocaleString()}
                </td>
                <td className="px-4 py-3">{row.actor_email ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-xs">{row.action}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  {row.entity_type}
                  {row.entity_id ? `:${row.entity_id.slice(0, 8)}` : ""}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{row.ip ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
