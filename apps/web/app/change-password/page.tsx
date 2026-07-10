"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

// FR-006: admin-created accounts carry a forced password-change flag; login redirects here
// until it's cleared.
export default function ChangePasswordPage() {
  const { user, isLoading, refreshUser } = useAuth();
  const router = useRouter();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) router.replace("/login");
  }, [isLoading, user, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const { error: apiError } = await api.POST("/api/v1/auth/change-password", {
      body: { current_password: currentPassword, new_password: newPassword },
    });
    setIsSubmitting(false);
    if (apiError) {
      setError("Current password is incorrect, or the new password is too short.");
      return;
    }
    await refreshUser();
    router.push("/dashboard");
  }

  if (isLoading || !user) return null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-canvas px-6">
      <form onSubmit={handleSubmit} className="flex w-full max-w-[360px] flex-col gap-5">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Set a new password</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Your account was created with a temporary password. Choose a new one to continue.
          </p>
        </div>

        <label className="flex flex-col gap-1.5 text-sm font-medium text-text-secondary">
          Current (temporary) password
          <Input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
        </label>

        <label className="flex flex-col gap-1.5 text-sm font-medium text-text-secondary">
          New password
          <Input
            type="password"
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            error={error ?? undefined}
          />
        </label>

        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Saving…" : "Save and continue"}
        </Button>
      </form>
    </div>
  );
}
