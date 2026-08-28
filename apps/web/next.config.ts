import type { NextConfig } from "next";

/**
 * When API_REWRITE_ORIGIN is set (Vercel production), browser calls stay same-origin
 * (`/api/...`) so the httpOnly SameSite=Strict refresh cookie keeps working (FR-001).
 * Vercel proxies those paths to the EC2 API. Locally, leave unset and point
 * NEXT_PUBLIC_API_URL at http://localhost:8000.
 */
const apiRewriteOrigin = process.env.API_REWRITE_ORIGIN?.replace(/\/$/, "");
const apiConnectSrc = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        // Mermaid in the handbook reader needs blob: workers (ADR-028).
        source: "/handbook/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "font-src 'self' data:",
              "worker-src 'self' blob:",
              "connect-src 'self' blob:",
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "font-src 'self' data:",
              `connect-src 'self' ${apiConnectSrc}`,
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
  async rewrites() {
    if (!apiRewriteOrigin) {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: `${apiRewriteOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
