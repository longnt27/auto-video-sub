import type { NextConfig } from "next";
import path from "node:path";

const workspaceRoot = path.join(process.cwd(), "../..");

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: workspaceRoot,
  poweredByHeader: false,
  turbopack: {
    root: workspaceRoot,
  },
};

export default nextConfig;
