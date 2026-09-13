"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const root = path.resolve(__dirname, "..");
const port = Number(process.env.FOORYS_PREVIEW_PORT || 8765);
const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".zip": "application/zip",
  ".ipk": "application/octet-stream"
};

function send(res, status, body, headers) {
  res.writeHead(status, Object.assign({ "Cache-Control": "no-store" }, headers || {}));
  res.end(body);
}

const server = http.createServer((req, res) => {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
  } catch (error) {
    send(res, 400, "Bad request\n");
    return;
  }
  if (pathname === "/") {
    res.writeHead(302, { Location: "/preview/", "Cache-Control": "no-store" });
    res.end();
    return;
  }
  if (pathname === "/preview") pathname = "/preview/";
  if (pathname.endsWith("/")) pathname += "index.html";
  const filePath = path.resolve(root, "." + pathname);
  if (filePath !== root && !filePath.startsWith(root + path.sep)) {
    send(res, 403, "Forbidden\n");
    return;
  }
  fs.stat(filePath, (statError, stats) => {
    if (statError || !stats.isFile()) {
      send(res, 404, "Not found\n");
      return;
    }
    const type = mime[path.extname(filePath).toLowerCase()] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": type, "Cache-Control": "no-store" });
    fs.createReadStream(filePath).pipe(res);
  });
});

server.listen(port, "127.0.0.1", () => {
  console.log("E2-Foorys local preview: http://localhost:" + port + "/preview/");
  console.log("Press Ctrl+C to stop.");
});
