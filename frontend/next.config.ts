import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  cacheComponents: true,
  // On, warm-cache pages embed a second ~1.5 MB copy of the chart payload.
  partialPrefetching: false,
  allowedDevOrigins: ["192.168.4.22"],
};

export default nextConfig;
