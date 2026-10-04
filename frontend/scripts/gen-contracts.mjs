// Generates TypeScript types from /contracts into one bundled file, so types shared between
// schemas (ids, widgets, ...) are declared once. Called by tools/gen_contracts.sh.
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { glob } from "node:fs/promises";
import { compile } from "json-schema-to-typescript";

const [, , contractsDir, outDir] = process.argv;

const files = [];
for await (const file of glob("**/*.schema.json", { cwd: contractsDir })) files.push(file);
files.sort();

// A root schema that references every contract by its title.
const defs = {};
for (const file of files) {
  const { title } = JSON.parse(await readFile(join(contractsDir, file), "utf8"));
  if (!title || title === "Common identifiers") continue;
  defs[title] = { $ref: `./${file}` };
}

const ts = await compile({ title: "Contracts", $defs: defs }, "Contracts", {
  cwd: contractsDir,
  bannerComment: "/* GENERATED from /contracts by tools/gen_contracts.sh. Do not edit. */",
  additionalProperties: false,
  unreachableDefinitions: true,
  format: true,
});

await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });
await writeFile(join(outDir, "index.ts"), ts.replace(/export interface Contracts \{\}\n?/, ""));
console.log(`generated TypeScript types for ${Object.keys(defs).length} contracts`);
