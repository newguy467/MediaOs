#!/usr/bin/env node
/**
 * Ensure React.lazy / lazyNamed imports in ui/src/app.jsx resolve to real exports.
 * Run: node scripts/check_lazy_exports.mjs
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const appPath = path.join(root, "ui/src/app.jsx");
const pagesDir = path.join(root, "ui/src/pages");

if (!fs.existsSync(appPath)) {
  console.error("Missing", appPath);
  process.exit(1);
}

const app = fs.readFileSync(appPath, "utf8");
const errors = [];

function exportsOf(fileRel) {
  const full = path.join(root, "ui/src/pages", fileRel);
  if (!fs.existsSync(full)) return { default: false, named: new Set(), missing: true };
  const t = fs.readFileSync(full, "utf8");
  const named = new Set();
  for (const m of t.matchAll(/export\s+\{([^}]+)\}/g)) {
    for (const part of m[1].split(",")) {
      let name = part.trim();
      if (!name) continue;
      if (name.includes(" as ")) name = name.split(" as ").pop().trim();
      named.add(name);
    }
  }
  for (const m of t.matchAll(/export\s+(?:async\s+)?function\s+(\w+)/g)) named.add(m[1]);
  for (const m of t.matchAll(/export\s+const\s+(\w+)/g)) named.add(m[1]);
  const hasDefault = /export\s+default\b/.test(t);
  return { default: hasDefault, named, missing: false };
}

// React.lazy(() => import("./pages/foo.jsx"))
for (const m of app.matchAll(/React\.lazy\(\(\)\s*=>\s*import\(["']\.\/pages\/([^"']+)["']\)\)/g)) {
  const file = m[1];
  const exp = exportsOf(file);
  if (exp.missing) errors.push(`React.lazy ${file}: file missing`);
  else if (!exp.default) errors.push(`React.lazy ${file}: no default export`);
}

// lazyNamed(() => import("./pages/foo.jsx"), "Name")
for (const m of app.matchAll(/lazyNamed\(\(\)\s*=>\s*import\(["']\.\/pages\/([^"']+)["']\),\s*["'](\w+)["']\)/g)) {
  const file = m[1];
  const name = m[2];
  const exp = exportsOf(file);
  if (exp.missing) errors.push(`lazyNamed ${name} from ${file}: file missing`);
  else if (!exp.named.has(name) && !exp.default) {
    errors.push(`lazyNamed ${name} from ${file}: named export not found (named=[...${[...exp.named].slice(0, 8)}])`);
  } else if (!exp.named.has(name) && exp.default) {
    // allow only if they re-export; still warn as error for strictness
    errors.push(`lazyNamed ${name} from ${file}: expected named export, only default present`);
  }
}

if (errors.length) {
  console.error("Lazy export check FAILED:");
  for (const e of errors) console.error(" -", e);
  process.exit(1);
}
console.log("Lazy export check OK");
