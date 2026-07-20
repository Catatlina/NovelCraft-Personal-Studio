import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { extname, join, normalize, resolve } from "node:path";
import { URL } from "node:url";

const port = Number(process.env.PORT || 80);
const upstream = new URL(process.env.API_UPSTREAM || "http://api:8000");
const distRoot = resolve(process.cwd(), "dist");
const indexFile = join(distRoot, "index.html");

const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".js", "application/javascript; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".webp", "image/webp"],
  [".ico", "image/x-icon"],
  [".txt", "text/plain; charset=utf-8"],
  [".map", "application/json; charset=utf-8"],
]);

function sendFile(res, filePath, statusCode = 200) {
  const ext = extname(filePath);
  const headers = {
    "Content-Type": mimeTypes.get(ext) || "application/octet-stream",
    "Cache-Control": ext === ".html" ? "no-cache, must-revalidate" : "public, max-age=31536000, immutable",
  };
  res.writeHead(statusCode, headers);
  createReadStream(filePath).pipe(res);
}

function safeStaticPath(pathname) {
  const decoded = decodeURIComponent(pathname.split("?")[0]);
  const normalized = normalize(decoded).replace(/^(\.\.(\/|\\|$))+/, "");
  const candidate = resolve(join(distRoot, normalized));
  if (!candidate.startsWith(distRoot)) return null;
  return candidate;
}

function proxyApi(req, res) {
  const target = new URL(req.url || "/", upstream);
  const transport = target.protocol === "https:" ? httpsRequest : httpRequest;
  const headers = { ...req.headers };
  headers.host = upstream.host;
  headers["x-forwarded-host"] = req.headers.host || "";
  headers["x-forwarded-proto"] = "http";

  const proxyReq = transport({
    protocol: target.protocol,
    hostname: target.hostname,
    port: target.port || (target.protocol === "https:" ? 443 : 80),
    method: req.method,
    path: `${target.pathname}${target.search}`,
    headers,
  }, proxyRes => {
    res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
    proxyRes.pipe(res);
  });

  proxyReq.on("error", error => {
    if (res.headersSent) {
      res.destroy(error);
      return;
    }
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({
      code: "BAD_GATEWAY",
      message: "后端 API 暂不可用",
      detail: error.message,
    }));
  });

  req.pipe(proxyReq);
}

createServer((req, res) => {
  const url = req.url || "/";
  if (url.startsWith("/api/") || url.startsWith("/openapi.json")) {
    proxyApi(req, res);
    return;
  }

  const filePath = safeStaticPath(url);
  if (filePath && existsSync(filePath) && statSync(filePath).isFile()) {
    sendFile(res, filePath);
    return;
  }

  sendFile(res, indexFile);
}).listen(port, "0.0.0.0", () => {
  console.log(`NovelCraft frontend serving ${distRoot} on :${port}, proxying /api to ${upstream.origin}`);
});
