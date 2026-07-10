"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

export default function LoginPage() {
  const { login } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const { mustChangePassword } = await login(email, password);
      router.push(mustChangePassword ? "/change-password" : "/dashboard");
    } catch {
      setError("Invalid email or password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="relative hidden w-[44%] flex-col justify-between overflow-hidden bg-neutral-900 p-12 text-white lg:flex">
        {/* eslint-disable-next-line @next/next/no-img-element -- ambient brand art, not an optimizable photo */}
        <img
          src="/dealeriq-mark.svg"
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute -right-32 -top-32 h-[720px] w-[720px] opacity-[0.12]"
        />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/dealeriq-lockup-h-dark.svg" alt="DealerIQ" width={180} height={44} className="relative" />
        <div className="relative flex flex-col gap-4">
          <h1 className="text-3xl font-semibold leading-snug">
            From system of record to system of intelligence.
          </h1>
          <p className="text-sm text-neutral-400">
            Automated demand forecasting, inventory optimization, and alerting for automotive
            dealerships.
          </p>
        </div>
        <p className="relative font-mono text-xs text-neutral-500">© 2026 DealerIQ</p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center bg-surface-canvas px-6">
        <button
          type="button"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          className="absolute right-6 top-6 flex items-center gap-2 rounded-full border border-border-hairline bg-surface-raised px-3 py-1.5 text-xs text-text-secondary"
        >
          {resolvedTheme === "dark" ? <Sun size={14} strokeWidth={1.5} /> : <Moon size={14} strokeWidth={1.5} />}
          {resolvedTheme === "dark" ? "Light" : "Dark"}
        </button>

        <form onSubmit={handleSubmit} className="flex w-full max-w-[360px] flex-col gap-5">
          <div>
            <h2 className="text-2xl font-bold text-text-primary">Sign in</h2>
            <p className="mt-1 text-sm text-text-secondary">
              Use the account your administrator created for you.
            </p>
          </div>

          <label className="flex flex-col gap-1.5 text-sm font-medium text-text-secondary">
            Email
            <Input
              type="email"
              autoComplete="username"
              placeholder="you@dealership.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="flex flex-col gap-1.5 text-sm font-medium text-text-secondary">
            Password
            <Input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              error={error ?? undefined}
            />
          </label>

          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>

          <p className="text-center text-xs text-text-muted">
            Need access? Contact your administrator.
          </p>
        </form>
      </div>
    </div>
  );
}
