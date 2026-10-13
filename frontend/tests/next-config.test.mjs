import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const source = readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "../next.config.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
function config(env = {}) {
  const exports = {};
  runInNewContext(compiled, { exports, process: { env }, URL });
  return exports.default;
}

test("local previews retain direct backend access and isolated build directories", async () => {
  assert.equal(config({ NODE_ENV: "development" }).distDir, ".next-dev");
  assert.equal(config({ NODE_ENV: "production" }).distDir, ".next");
  assert.equal((await config().rewrites()).length, 0);
});

test("Vercel proxy routes the API and OAuth callbacks through the frontend", async () => {
  const routes = await config({ NODE_ENV: "production", API_PROXY_ORIGIN: "https://careerpilot-api.example.com/", NEXT_PUBLIC_API_BASE_URL: "/api/v1" }).rewrites();
  assert.equal(routes.length, 1);
  assert.equal(routes[0].source, "/api/v1/:path*");
  assert.equal(routes[0].destination, "https://careerpilot-api.example.com/api/v1/:path*");
});

test("proxy rejects a browser API URL that would bypass same-origin routing", async () => {
  await assert.rejects(config({ API_PROXY_ORIGIN: "https://api.example.com" }).rewrites());
});

for (const target of ["http://api.example.com", "http://localhost:8000", "https://user:secret@api.example.com", "https://api.example.com/api/v1", "https://api.example.com?token=hidden", "https://api.example.com#fragment"]) {
  test(`production proxy rejects unsafe origin: ${target.split("?")[0].split("#")[0].replace("user:secret@", "[credentials]@")}`, async () => {
    await assert.rejects(config({ NODE_ENV: "production", API_PROXY_ORIGIN: target, NEXT_PUBLIC_API_BASE_URL: "/api/v1" }).rewrites());
  });
}

test("development proxy supports loopback only", async () => {
  const env = { NODE_ENV: "development", NEXT_PUBLIC_API_BASE_URL: "/api/v1" };
  const routes = await config({ ...env, API_PROXY_ORIGIN: "http://127.0.0.1:8000" }).rewrites();
  assert.equal(routes[0].destination, "http://127.0.0.1:8000/api/v1/:path*");
  await assert.rejects(config({ ...env, API_PROXY_ORIGIN: "http://external.example.com" }).rewrites());
});
