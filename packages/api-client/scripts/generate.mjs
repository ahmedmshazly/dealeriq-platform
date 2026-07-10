#!/usr/bin/env node
// Generates src/schema.d.ts from the running API's OpenAPI 3.1 schema (C-05, ADR-012).
// Requires `make dev` (or at least the API container) to be running first.
import { execSync } from "node:child_process";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const schemaUrl = `${apiUrl}/api/v1/openapi.json`;
const outFile = new URL("../src/schema.d.ts", import.meta.url).pathname;

console.log(`[api-client] Generating types from ${schemaUrl} -> ${outFile}`);
execSync(`npx openapi-typescript ${schemaUrl} -o ${outFile}`, { stdio: "inherit" });
console.log("[api-client] Done.");
