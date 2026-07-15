import type { NextConfig } from "next";

/**
 * When API_REWRITE_ORIGIN is set (Vercel production), browser calls stay same-origin
 * (`/api/...`) so the httpOnly SameSite=Strict refresh cookie keeps working (FR-001).
 * Vercel proxies those paths to the EC2 API. Locally, leave unset and point
 * NEXT_PUBLIC_API_URL at http://localhost:8000.
 */
const apiRewriteOrigin = process.env.API_REWRITE_ORIGIN?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
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
