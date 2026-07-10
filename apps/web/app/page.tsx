// Placeholder home page for the Phase 0 skeleton. Once real endpoints exist this direct
// fetch is replaced by the generated OpenAPI client (packages/api-client) per C-05/ADR-014 —
// there is no documented contract to generate against yet beyond /health.
export const dynamic = "force-dynamic";

async function getApiStatus(): Promise<"ok" | "offline"> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/v1/health`, { cache: "no-store" });
    if (!res.ok) return "offline";
    const data = (await res.json()) as { status?: string };
    return data.status === "ok" ? "ok" : "offline";
  } catch {
    return "offline";
  }
}

export default async function Home() {
  const status = await getApiStatus();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-surface-canvas px-6">
      {/* eslint-disable-next-line @next/next/no-img-element -- static brand SVG, not an
          optimizable raster image */}
      <img src="/dealeriq-lockup-h.svg" alt="DealerIQ" width={220} height={54} />
      <p className="max-w-content text-center text-lg text-text-secondary">
        Dealership intelligence platform — forecasting, inventory, and alerting, built on
        DIQ-SRS-001.
      </p>
      <div
        className={`flex items-center gap-2 rounded-full border px-4 py-2 font-mono text-sm ${
          status === "ok"
            ? "border-success-border bg-success-bg text-success-fg"
            : "border-critical-border bg-critical-bg text-critical-fg"
        }`}
      >
        <span
          className={`h-2 w-2 rounded-full ${status === "ok" ? "bg-success-fg" : "bg-critical-fg"}`}
        />
        API status: {status === "ok" ? "online" : "offline"}
      </div>
    </main>
  );
}
