"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api-error";
import { useQuery } from "@tanstack/react-query";

// FR-013: the permission matrix is DB-stored/migration-seeded; this page just renders it —
// there is no client-side notion of "what a role can do" beyond what the API reports.
export default function PermissionsAdminPage() {
  const matrixQuery = useQuery({
    queryKey: ["permission-matrix"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/permissions/matrix");
      const status = response.status;
      if (error) throw new ApiRequestError("Failed to load the permission matrix.", status);
      return data;
    },
  });

  if (matrixQuery.error) {
    return (
      <Card className="p-6 text-sm text-critical-fg">
        You don&apos;t have permission to view this page (requires the{" "}
        <code className="font-mono">permissions:view</code> permission).
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Permission matrix</h1>
        <p className="text-sm text-text-secondary">
          Read-only view of what each role is granted (FR-013). New permission keys are added
          via migration as new resources ship.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {(matrixQuery.data ?? []).map((row) => (
          <Card key={row.role_key} className="p-5">
            <h2 className="mb-3 text-sm font-semibold text-text-primary">{row.role_name}</h2>
            {row.permissions.length === 0 ? (
              <p className="text-xs text-text-muted">No permissions granted.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {row.permissions.map((perm) => (
                  <Badge key={perm} severity="info">
                    {perm}
                  </Badge>
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
