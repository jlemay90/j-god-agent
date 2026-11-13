import { readFile, mkdir, rm, writeFile, realpath } from "node:fs/promises";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = resolve(root, "dist");
const rootReal = await realpath(root);
if (!dist.startsWith(rootReal + sep) || relative(rootReal, dist).startsWith("..")) {
  throw new Error("Build output must stay within the Site checkout.");
}

const [template, styles, script, worker, manifest] = await Promise.all([
  readFile(join(root, "app/index.html"), "utf8"),
  readFile(join(root, "app/style.css"), "utf8"),
  readFile(join(root, "app/app.js"), "utf8"),
  readFile(join(root, "worker/index.js"), "utf8"),
  readFile(join(root, ".openai/hosting.json"), "utf8"),
]);
if (!template.includes('/*APP_STYLES*/') || !template.includes('/*APP_SCRIPT*/')) throw new Error('App embedding markers are missing.');
const zeus = await readFile(join(root, "worker/zeus.js"), "utf8");
const zeusClient = await readFile(join(root, "app/zeus.js"), "utf8");
const planningWorker = await readFile(join(root, "worker/planning.js"), "utf8");
const planningClient = await readFile(join(root, "app/planning.js"), "utf8");
const planningStyles = await readFile(join(root, "app/planning.css"), "utf8");
const icon = (await readFile(join(root, 'app/app-icon.png'))).toString('base64');
const html = template.replace('/*APP_STYLES*/', () => styles + '\n' + planningStyles).replace('/*APP_SCRIPT*/', () => script + '\n' + zeusClient + '\n' + planningClient);
const marker = 'const INDEX_HTML = "";';
if (!worker.includes(marker)) throw new Error("Worker HTML marker is missing.");
JSON.parse(manifest);
await rm(dist, { recursive: true, force: true });
await mkdir(join(dist, "server"), { recursive: true });
await mkdir(join(dist, ".openai"), { recursive: true });
await writeFile(join(dist, "server/index.js"), worker.replace('const APP_ICON_BASE64 = "";', 'const APP_ICON_BASE64 = ' + JSON.stringify(icon) + ';').replace("/*ZEUS_BRIDGE*/", () => zeus).replace("/*PLANNING_WORKER*/", () => planningWorker).replace(marker, "const INDEX_HTML = " + JSON.stringify(html) + ";"));
await writeFile(join(dist, ".openai/hosting.json"), manifest);
console.log("Built Site Worker");
