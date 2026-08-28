import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, relative } from "node:path";
import type { Tier } from "../../src/types.js";

export interface DocFile {
  path: string;
  id: string;
  tier: Tier;
  num: string | null;
  order: number;
  source: string;
}

/** Non-handbook paths under docs/ that should not be indexed as prose. */
const SKIP_PREFIXES = [
  "docs/paper/paper.",
  "docs/paper/results/benchmark",
];

const SKIP_SUFFIXES = [".parquet", ".aux", ".bbl", ".blg", ".log", ".out", ".tex", ".bib", ".pdf"];

const NUMBERED = /^(\d{2})([a-z]?)-/;

/** Preferred handbook reading order. */
const HANDBOOK_ORDER: Record<string, number> = {
  "00-reading-path": 0,
  "getting-started/onboarding": 10,
  "explanation/architecture": 20,
  "explanation/security-model": 21,
  "explanation/domain-lifecycles": 22,
  "explanation/analytics-pipeline": 23,
  "explanation/data-model": 24,
  "diagrams/README": 30,
};

/**
 * Discover and classify the DealerIQ docs corpus (Diataxis + ADR-028).
 *
 * Tiers:
 * - handbook - reading path, explanation, getting-started, diagrams catalog
 * - meta - portal README, how-to, reference, runbooks, ADRs, SRS, glossary, backlog
 * - background - paper markdown
 * - stub - unused (type compatibility)
 */
export function discoverDocs(root: string): DocFile[] {
  const docsDir = join(root, "docs");
  const out: DocFile[] = [];

  const walk = (dir: string): void => {
    for (const e of readdirSync(dir, { withFileTypes: true }).sort((a, b) =>
      a.name.localeCompare(b.name),
    )) {
      const p = join(dir, e.name);
      if (e.isDirectory()) {
        walk(p);
      } else if (e.name.endsWith(".md")) {
        const rel = relative(root, p).split("\\").join("/");
        if (shouldSkip(rel)) continue;
        out.push(describe(root, p));
      }
    }
  };
  walk(docsDir);

  const handbook = out
    .filter((d) => d.tier === "handbook")
    .sort(
      (a, b) =>
        (HANDBOOK_ORDER[a.id] ?? 500) - (HANDBOOK_ORDER[b.id] ?? 500) ||
        a.path.localeCompare(b.path),
    );
  handbook.forEach((d, i) => (d.order = i));

  const metaOrder: Record<string, number> = {
    readme: 0,
    glossary: 1,
    backlog: 2,
  };
  for (const d of out.filter((x) => x.tier === "meta")) {
    d.order = metaOrder[d.id] ?? 50;
  }

  const rank: Record<Tier, number> = {
    handbook: 0,
    meta: 1,
    stub: 2,
    background: 3,
  };
  return out.sort(
    (a, b) =>
      rank[a.tier] - rank[b.tier] ||
      a.order - b.order ||
      a.path.localeCompare(b.path),
  );
}

function shouldSkip(rel: string): boolean {
  if (SKIP_PREFIXES.some((s) => rel.startsWith(s))) return true;
  if (SKIP_SUFFIXES.some((s) => rel.endsWith(s))) return true;
  return false;
}

function describe(root: string, abs: string): DocFile {
  const path = relative(root, abs).split("\\").join("/");
  const name = path.split("/").pop()!;
  const source = readFileSync(abs, "utf8");
  const under = path.replace(/^docs\//, "").replace(/\.md$/, "");

  // Numbered reading-path at docs root (00-reading-path.md)
  const m = NUMBERED.exec(name);
  if (m && !under.includes("/")) {
    return {
      path,
      id: under,
      tier: "handbook",
      num: m[1] + m[2],
      order: 0,
      source,
    };
  }

  if (
    under.startsWith("explanation/") ||
    under.startsWith("getting-started/") ||
    under === "diagrams/README"
  ) {
    return {
      path,
      id: under,
      tier: "handbook",
      num: null,
      order: HANDBOOK_ORDER[under] ?? 100,
      source,
    };
  }

  if (
    under.startsWith("paper/")
  ) {
    return {
      path,
      id: under,
      tier: "background",
      num: null,
      order: 0,
      source,
    };
  }

  // Meta: how-to, reference, runbooks, adr, srs, README, glossary, backlog
  const id = under.includes("/") ? under : under.toLowerCase();
  return {
    path,
    id,
    tier: "meta",
    num: null,
    order: 0,
    source,
  };
}

/** Env var names from `.env.example`. Values are never read. */
export function readEnvNames(root: string): Set<string> {
  const p = join(root, ".env.example");
  if (!existsSync(p)) return new Set();
  const names = new Set<string>();
  for (const line of readFileSync(p, "utf8").split("\n")) {
    const m = /^\s*([A-Z][A-Z0-9_]*)\s*=/.exec(line);
    if (m) names.add(m[1]);
  }
  return names;
}

/** No Firestore collections in DealerIQ - keep empty set for indexer compatibility. */
export function readCollections(_root: string): Set<string> {
  return new Set();
}
