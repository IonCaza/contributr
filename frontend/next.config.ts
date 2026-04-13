import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: process.env.BUILD_STANDALONE === "true" ? "standalone" : undefined,
  experimental: {
    proxyTimeout: 300_000,
  },
};

export default nextConfig;
