import type { NextConfig } from "next";

const backend = process.env.EDAPTIVE_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // The browser only ever talks to this origin; /api/* is forwarded to the local FastAPI backend.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
