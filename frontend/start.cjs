const fs = require("node:fs");
const path = require("node:path");
// La destinazione resta privata e viene applicata all'avvio del container.
const runtime = fs.existsSync(path.join(__dirname, "server.js"))
  ? __dirname
  : path.join(__dirname, ".next/standalone");
if (runtime !== __dirname)
  fs.cpSync(
    path.join(__dirname, ".next/static"),
    path.join(runtime, ".next/static"),
    { recursive: true },
  );
const upstream = new URL(process.env.API_URL || "http://backend:8080");
if (
  !["http:", "https:"].includes(upstream.protocol) ||
  upstream.username ||
  upstream.password ||
  upstream.search ||
  upstream.hash ||
  upstream.pathname !== "/"
)
  throw new Error("Invalid API_URL");
const manifestPath = path.join(runtime, ".next/routes-manifest.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
for (const rules of Object.values(manifest.rewrites))
  for (const rule of rules)
    if (rule.source === "/api/:path*")
      rule.destination = `${upstream.origin}/api/:path*`;
fs.writeFileSync(manifestPath, JSON.stringify(manifest));
require(path.join(runtime, "server.js"));
