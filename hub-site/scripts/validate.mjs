import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [source, manifest] = await Promise.all([
  readFile(new URL("../dist/server/index.js", import.meta.url), "utf8"),
  readFile(new URL("../dist/.openai/hosting.json", import.meta.url), "utf8"),
]);
const config = JSON.parse(manifest);
assert.equal(config.r2, "BUCKET");
assert.ok(config.capabilities.includes("mcp"));
const worker = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
assert.equal(typeof worker.default?.fetch, "function");
const response = await worker.default.fetch(new Request("https://hub.example/"), {});
assert.equal(response.status, 200);
const html = await response.text();
assert.match(html, /Today’s Daily Pulse/);
assert.match(html, /Recovery snapshot/);
assert.match(html, /Trusted source map/);
assert.match(html, /What am I forgetting\?/);
assert.ok(!html.includes('/*APP_STYLES*/') && !html.includes('/*APP_SCRIPT*/'), 'The published page must include its styles and behavior');
new Function(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
console.log("Site Worker artifact validated");
