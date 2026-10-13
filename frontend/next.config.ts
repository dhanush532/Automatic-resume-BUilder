import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // A dev preview must not replace the files served by a production preview.
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
  async rewrites() {
    const target = process.env.API_PROXY_ORIGIN;
    if (!target) return [];
    if (process.env.NEXT_PUBLIC_API_BASE_URL !== "/api/v1") {
      throw new Error("API_PROXY_ORIGIN requires NEXT_PUBLIC_API_BASE_URL=/api/v1.");
    }
    const origin = new URL(target);
    const localHttp = process.env.NODE_ENV === "development" && origin.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname);
    if ((origin.protocol !== "https:" && !localHttp) || origin.username || origin.password || origin.pathname !== "/" || origin.search || origin.hash) {
      throw new Error("API_PROXY_ORIGIN must be a credential-free HTTPS origin without a path, query, or fragment.");
    }
    // Keep API cookies and OAuth callbacks on the browser's frontend origin.
    return [{ source: "/api/v1/:path*", destination: `${origin.origin}/api/v1/:path*` }];
  },
  experimental: {
    // Keeps builds reliable in constrained Windows environments; this small app
    // does not benefit from a separate webpack worker yet.
    webpackBuildWorker: false,
  },
};

export default nextConfig;
