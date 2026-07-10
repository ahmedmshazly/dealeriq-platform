"use client";

import { Card } from "@/components/ui/card";
import { useAuth } from "@/lib/auth-context";

// Real Manager/Sales/Analyst dashboards (FR-050..052) land in Phase 8. This is a placeholder
// authenticated landing page proving the auth/RBAC session actually works end-to-end.
export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Welcome back</h1>
        <p className="text-sm text-text-secondary">
          Signed in as <span className="font-mono">{user?.email}</span> (
          {user?.role_key})
        </p>
      </div>
      <Card className="p-6">
        <p className="text-sm text-text-secondary">
          Manager, Sales, and Analyst dashboards (sales-vs-forecast, inventory health, lead
          scores) land in Phase 8 of the delivery plan. This page confirms your session and
          role are working end-to-end.
        </p>
      </Card>
    </div>
  );
}
