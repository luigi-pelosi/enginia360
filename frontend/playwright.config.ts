import { defineConfig } from "@playwright/test";
export default defineConfig({
    testDir: "./tests",
    testMatch: "acceptance.spec.ts",
    workers: 1,
    retries: 0,
    timeout: 30000,
    reporter: [["list"]],
    outputDir: "/scratch/results",
    use: {
        baseURL: process.env.MVP01_BASE_URL,
        browserName: "chromium",
        trace: "retain-on-failure",
    },
});
