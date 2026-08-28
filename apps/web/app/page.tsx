"use client";

import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

// `/` has no content of its own - it routes to the dashboard (which the authenticated layout
// redirects to /login for anyone without a session).
export default function Home() {
  const { isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) router.replace("/dashboard");
  }, [isLoading, router]);

  return null;
}
