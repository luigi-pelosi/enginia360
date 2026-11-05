import type { NextConfig } from "next";
const config: NextConfig = {
    output: "standalone",
    poweredByHeader: false,
    async headers() {
        return [
            { source: "/documents", headers: [{ key: "Cache-Control", value: "private, no-store" }] },
            { source: "/document-types", headers: [{ key: "Cache-Control", value: "private, no-store" }] },
            { source: "/catalog", headers: [{ key: "Cache-Control", value: "private, no-store" }] },
            { source: "/counterparties", headers: [{ key: "Cache-Control", value: "private, no-store" }] },
            {
                source: "/:path*",
                headers: [
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "X-Frame-Options", value: "DENY" },
                    { key: "Referrer-Policy", value: "no-referrer" },
                    {
                        key: "Permissions-Policy",
                        value: "camera=(), microphone=(), geolocation=()",
                    },
                ],
            },
        ];
    },
};
export default config;
