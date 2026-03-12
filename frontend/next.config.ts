import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const backend = process.env.API_URL;
    if (!backend) return [];
    return [
      { source: "/api/:path*", destination: `${backend}/:path*` },
    ];
  },
};

export default nextConfig;
