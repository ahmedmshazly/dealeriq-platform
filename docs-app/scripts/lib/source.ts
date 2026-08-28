import { readFileSync, existsSync, statSync, readdirSync } from "node:fs";
import { execSync } from "node:child_process";
import { join } from "node:path";
import type { SourceFile, SourceSymbol, SymbolKind } from "../../src/types.js";

/**
 * Source directories walked wholesale for the DealerIQ monorepo (ADR-001 / ADR-028).
 */
const DIRS = ["apps", "packages", "infra", "scripts", "deploy"];

const ROOT_FILES = [
  "README.md",
  "CONTRIBUTING.md",
  "CHANGELOG.md",
  "SECURITY.md",
  "LICENSE",
  "Makefile",
  "pyproject.toml",
  "package.json",
  ".env.example",
  ".github/workflows/ci.yml",
  "infra/docker-compose.yml",
  "infra/docker-compose.prod.yml",
  "infra/Dockerfile",
];

const EXT_LANG: Record<string, string> = {
  ts: "ts",
  tsx: "tsx",
  css: "css",
  json: "json",
  mjs: "js",
  js: "js",
  yml: "yaml",
  yaml: "yaml",
  md: "markdown",
  py: "python",
  toml: "toml",
  sh: "bash",
  ini: "ini",
};

/** Skip generated / vendor trees even if git-tracked. */
const SKIP_PARTS = [
  "/node_modules/",
  "/__pycache__/",
  "/.venv/",
  "/dist/",
  "/coverage/",
  "/test-results/",
  "/playwright-report/",
  "/src/generated/",
  "/public/handbook/",
];

export function langOf(path: string): string {
  const ext = path.split(".").pop() ?? "";
  return EXT_LANG[ext] ?? "plaintext";
}

function candidateFiles(root: string): string[] {
  try {
    return execSync(`git -C ${JSON.stringify(root)} ls-files -z`, {
      encoding: "utf8",
      maxBuffer: 32 * 1024 * 1024,
    })
      .split("\0")
      .filter(Boolean);
  } catch {
    const out: string[] = [];
    for (const dir of DIRS) walkDir(root, dir, out);
    return out;
  }
}

function walkDir(root: string, rel: string, out: string[]): void {
  const abs = join(root, rel);
  if (!existsSync(abs)) return;
  for (const entry of readdirSync(abs, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    if (entry.name === "__pycache__" || entry.name === "dist") continue;
    const childRel = `${rel}/${entry.name}`;
    if (entry.isDirectory()) walkDir(root, childRel, out);
    else if (entry.isFile()) out.push(childRel);
  }
}

function skipped(path: string): boolean {
  const p = `/${path}/`;
  return SKIP_PARTS.some((s) => p.includes(s) || path.includes(s.slice(1, -1)));
}

/** Track files via git so we never index build output or `node_modules`. */
export function listSourceFiles(root: string): string[] {
  const tracked = candidateFiles(root);

  const wanted = new Set<string>();
  for (const p of tracked) {
    if (skipped(p)) continue;
    const inDir = DIRS.some((d) => p.startsWith(d + "/"));
    const isRoot = ROOT_FILES.includes(p);
    if (!inDir && !isRoot) continue;
    if (langOf(p) === "plaintext" && !isRoot) continue;
    // Cap: skip huge lockfiles from code viewer
    if (p.endsWith("package-lock.json") || p.endsWith("uv.lock")) continue;
    wanted.add(p);
  }
  for (const p of ROOT_FILES) if (existsSync(join(root, p))) wanted.add(p);

  return [...wanted].sort();
}

const PATTERNS: [RegExp, SymbolKind][] = [
  [/^export\s+default\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/, "default"],
  [/^export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/, "function"],
  [/^export\s+(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)/, "class"],
  [/^export\s+type\s+([A-Za-z_$][\w$]*)/, "type"],
  [/^export\s+interface\s+([A-Za-z_$][\w$]*)/, "interface"],
  [/^export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)/, "const"],
];

const DESTRUCTURED = /^export\s+(?:const|let|var)\s*\{([^}]+)\}/;
const ANON_DEFAULT = /^export\s+default\s+/;

/** Shallow Python defs/classes the handbook may backtick. */
const PY_DEF = /^(?:async\s+)?def\s+([A-Za-z_][\w]*)\s*\(/;
const PY_CLASS = /^class\s+([A-Za-z_][\w]*)\s*[:(]/;

function extractPythonSymbols(path: string, code: string): SourceSymbol[] {
  const out: SourceSymbol[] = [];
  const lines = code.split("\n");
  lines.forEach((raw, i) => {
    const line = raw.trimStart();
    const fn = PY_DEF.exec(line);
    if (fn && !line.startsWith("#")) {
      out.push({
        name: fn[1],
        kind: "function",
        line: i + 1,
        signature: line.replace(/\s*:\s*$/, "").slice(0, 240),
        file: path,
        citedBy: [],
      });
      return;
    }
    const cls = PY_CLASS.exec(line);
    if (cls && !line.startsWith("#")) {
      out.push({
        name: cls[1],
        kind: "class",
        line: i + 1,
        signature: line.replace(/\s*:\s*$/, "").slice(0, 240),
        file: path,
        citedBy: [],
      });
    }
  });
  return out;
}

export function extractSymbols(path: string, code: string): SourceSymbol[] {
  if (path.endsWith(".py")) return extractPythonSymbols(path, code);
  if (!/\.(ts|tsx)$/.test(path)) return [];

  const out: SourceSymbol[] = [];
  const lines = code.split("\n");
  const push = (name: string, kind: SymbolKind, i: number): void => {
    out.push({
      name,
      kind,
      line: i + 1,
      signature: signatureAt(lines, i),
      file: path,
      citedBy: [],
    });
  };

  lines.forEach((raw, i) => {
    const line = raw.trimStart();
    if (!line.startsWith("export")) return;

    const destructured = DESTRUCTURED.exec(line);
    if (destructured) {
      for (const part of destructured[1].split(",")) {
        const name = part
          .trim()
          .split(/\s+as\s+/)
          .pop()
          ?.trim();
        if (name && /^[A-Za-z_$][\w$]*$/.test(name)) push(name, "const", i);
      }
      return;
    }

    for (const [re, kind] of PATTERNS) {
      const m = re.exec(line);
      if (m) {
        push(m[1], kind, i);
        return;
      }
    }

    if (ANON_DEFAULT.test(line)) {
      const base = path
        .split("/")
        .pop()!
        .replace(/\.tsx?$/, "");
      push(base, "default", i);
    }
  });

  return out;
}

function signatureAt(lines: string[], start: number): string {
  const buf: string[] = [];
  for (let i = start; i < Math.min(start + 8, lines.length); i++) {
    const l = lines[i];
    buf.push(l.trim());
    if (/[{;=]\s*$/.test(l) || /\)\s*(:[^{]*)?\s*\{?\s*$/.test(l)) break;
  }
  return buf
    .join(" ")
    .replace(/\s*\{\s*$/, "")
    .replace(/\s+/g, " ")
    .slice(0, 240);
}

export function buildSourceIndex(root: string): {
  files: SourceFile[];
  contents: Map<string, string>;
} {
  const files: SourceFile[] = [];
  const contents = new Map<string, string>();

  for (const path of listSourceFiles(root)) {
    const abs = join(root, path);
    if (!existsSync(abs) || !statSync(abs).isFile()) continue;
    // Skip huge files (> 400 KB) to keep the index usable
    if (statSync(abs).size > 400_000) continue;
    const code = readFileSync(abs, "utf8");
    contents.set(path, code);

    files.push({
      path,
      lang: langOf(path),
      loc: code.split("\n").length,
      bytes: Buffer.byteLength(code),
      symbols: extractSymbols(path, code),
      citedBy: [],
      mentions: 0,
    });
  }

  return { files, contents };
}
