"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import type { ApiResponse } from "@/lib/api-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

type AlertRule = ApiResponse<"/api/v1/alert-rules", "get">[number];

export function AlertRulesAdminPage() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [paramsDraft, setParamsDraft] = useState<string>("");

  const rulesQuery = useQuery({
    queryKey: ["alert-rules"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/alert-rules");
      if (!response.ok) throw new ApiRequestError("Failed to load alert rules.", response.status);
      return data;
    },
  });

  const toggleEnabled = useMutation({
    mutationFn: async ({ key, enabled }: { key: string; enabled: boolean }) => {
      const { error } = await api.PATCH("/api/v1/alert-rules/{key}", {
        params: { path: { key } },
        body: { enabled },
      });
      if (error) throw new Error("Failed to update rule.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alert-rules"] }),
  });

  const saveParams = useMutation({
    mutationFn: async ({ key, params }: { key: string; params: Record<string, unknown> }) => {
      const { error } = await api.PATCH("/api/v1/alert-rules/{key}", {
        params: { path: { key } },
        body: { params },
      });
      if (error) throw new Error("Failed to update rule parameters.");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
      setEditingKey(null);
    },
  });

  if (rulesQuery.error instanceof ApiRequestError && rulesQuery.error.status === 403) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to manage alert rules (requires{" "}
        <code className="font-mono">alert-rules:manage</code>).
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Alert Rules</h1>
        <p className="text-sm text-text-secondary">
          Configure thresholds, schedules, and subscriptions for the six built-in rules
          (FR-065). Every change is versioned and audit-logged.
        </p>
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-border-hairline bg-surface-sunken text-left font-mono text-[10.5px] uppercase text-text-muted">
            <tr>
              <th className="px-4 py-3">Rule</th>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Params</th>
              <th className="px-4 py-3">Version</th>
              <th className="px-4 py-3">Enabled</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {(rulesQuery.data ?? []).map((rule: AlertRule) => (
              <tr key={rule.key} className="border-b border-border-hairline last:border-0 align-top">
                <td className="px-4 py-3 font-mono text-xs">{rule.key}</td>
                <td className="px-4 py-3">
                  <Badge severity={rule.severity === "critical" ? "critical" : rule.severity === "warning" ? "warning" : "info"}>
                    {rule.severity}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  {editingKey === rule.key ? (
                    <div className="flex flex-col gap-2">
                      <textarea
                        className="w-64 rounded-control border border-border-hairline p-2 font-mono text-xs"
                        rows={4}
                        value={paramsDraft}
                        onChange={(e) => setParamsDraft(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button
                          className="text-xs"
                          onClick={() => {
                            try {
                              const parsed = JSON.parse(paramsDraft);
                              saveParams.mutate({ key: rule.key, params: parsed });
                            } catch {
                              // invalid JSON -- leave editing open, no request sent
                            }
                          }}
                          disabled={saveParams.isPending}
                        >
                          Save
                        </Button>
                        <Button
                          variant="secondary"
                          className="text-xs"
                          onClick={() => setEditingKey(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => {
                        setEditingKey(rule.key);
                        setParamsDraft(JSON.stringify(rule.params, null, 2));
                      }}
                      className="font-mono text-xs text-primary-600 underline"
                    >
                      {JSON.stringify(rule.params)}
                    </button>
                  )}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{rule.version}</td>
                <td className="px-4 py-3">
                  <Badge severity={rule.enabled ? "success" : "neutral"}>
                    {rule.enabled ? "enabled" : "disabled"}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  <Button
                    variant="secondary"
                    className="text-xs"
                    onClick={() =>
                      toggleEnabled.mutate({ key: rule.key, enabled: !rule.enabled })
                    }
                    disabled={toggleEnabled.isPending}
                  >
                    {rule.enabled ? "Disable" : "Enable"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
