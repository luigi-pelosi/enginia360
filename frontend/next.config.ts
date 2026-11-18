import createNextIntlPlugin from "next-intl/plugin";
import type { NextConfig } from "next";
const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: { cpus: 1 },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL || "http://backend:8080"}/api/:path*`,
      },
    ];
  },
};
export default createNextIntlPlugin("./i18n/request.ts")(config);
