/**
 * `npm run docs:verify` — mechanical audit of the generated DealerIQ corpus.
 *
 * Soft floors (not portfolio exact counts). Run `npm run index` first.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { CodePayload, Corpus } from "../src/types.js";
import { LEXICON } from "../src/lexicon/lexicon.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "../..");
const GEN = resolve(HERE, "../src/generated");

const corpus: Corpus = JSON.parse(
  readFileSync(join(GEN, "corpus.json"), "utf8"),
);
const code: CodePayload = JSON.parse(
  readFileSync(join(GEN, "code.json"), "utf8"),
);

let failures = 0;

function check(label: string, ok: boolean, detail?: string[]): void {
  const mark = ok ? "✓" : "✗";
  console.log(`${mark} ${label}`);
  if (!ok) {
    failures++;
    for (const d of (detail ?? []).slice(0, 8)) console.log(`    ${d}`);
    if ((detail?.length ?? 0) > 8)
      console.log(`    …and ${detail!.length - 8} more`);
  }
}

const tiers = new Map<string, number>();
for (const d of corpus.docs) tiers.set(d.tier, (tiers.get(d.tier) ?? 0) + 1);
check(
  `${corpus.docs.length} docs indexed across ${tiers.size} tiers ` +
    `(${[...tiers].map(([t, n]) => `${t} ${n}`).join(", ")})`,
  corpus.docs.length >= 15 && tiers.has("handbook") && tiers.has("meta"),
);

const untitled = corpus.docs.filter((d) => !d.title);
check(
  `every document has a title`,
  untitled.length === 0,
  untitled.map((d) => d.path),
);

const anchors = new Map(
  corpus.docs.map((d) => [d.id, new Set(d.headings.map((h) => h.slug))]),
);
const badLinks: string[] = [];
let linkCount = 0;

for (const doc of corpus.docs) {
  for (const link of doc.links) {
    if (!link.to) {
      linkCount++;
      if (link.anchor && !anchors.get(doc.id)!.has(link.anchor)) {
        badLinks.push(`${doc.id} → #${link.anchor}`);
      }
      continue;
    }
    linkCount++;
    const target = anchors.get(link.to);
    if (!target) badLinks.push(`${doc.id} → missing doc ${link.to}`);
    else if (link.anchor && !target.has(link.anchor)) {
      badLinks.push(`${doc.id} → ${link.to}#${link.anchor}`);
    }
  }
}
check(
  `${linkCount - badLinks.length}/${linkCount} links and anchors resolve`,
  badLinks.length === 0,
  badLinks,
);

const orphans = corpus.docs.filter(
  (d) => d.backlinks.length === 0 && d.links.filter((l) => l.to).length === 0,
);
check(`${orphans.length} orphan document(s) in the link graph`, true, []);
if (orphans.length)
  for (const o of orphans) console.log(`    (isolated) ${o.path}`);

check(
  `${corpus.stats.headings} headings → ${corpus.sections.length} searchable sections`,
  corpus.sections.length >= Math.max(0, corpus.stats.headings - 5) &&
    corpus.sections.length > 0,
);

const dupes = corpus.docs.flatMap((d) => {
  const seen = new Set<string>();
  return d.headings.filter((h) =>
    seen.has(h.slug) ? true : (seen.add(h.slug), false),
  );
});
check(
  `no duplicate heading slug within a document`,
  dupes.length === 0,
  dupes.map((h) => h.slug),
);

const missingPaths = corpus.files.filter(
  (f) => !existsSync(join(ROOT, f.path)),
);
check(
  `${corpus.files.length} indexed source files all exist on disk`,
  missingPaths.length === 0,
  missingPaths.map((f) => f.path),
);

const cited = corpus.files.filter((f) => f.citedBy.length);
check(
  `${cited.length}/${corpus.files.length} source files are cited by the handbook`,
  cited.length >= 5,
);

const badAnnotations: string[] = [];
for (const [path, file] of Object.entries(code.files)) {
  for (const [line, targets] of Object.entries(file.annotations)) {
    for (const t of targets) {
      const [docId, slug] = t.split("#");
      if (!anchors.has(docId))
        badAnnotations.push(`${path}:${line} → unknown doc ${docId}`);
      else if (slug && !anchors.get(docId)!.has(slug)) {
        badAnnotations.push(`${path}:${line} → ${docId}#${slug}`);
      }
    }
  }
}
check(
  `every gutter annotation resolves to a real section`,
  badAnnotations.length === 0,
  badAnnotations,
);

check(
  `style palette fits the run alphabet (${code.palette.length}/52)`,
  code.palette.length <= 52,
);

const RUN = /(\d+)([A-Za-z])/g;
const badRuns: string[] = [];
let lines = 0;
for (const [path, file] of Object.entries(code.files)) {
  file.runs.forEach((run, i) => {
    lines++;
    const covered = [...run.matchAll(RUN)].reduce(
      (n, m) => n + Number(m[1]),
      0,
    );
    const len = file.lines[i]?.length ?? 0;
    if (len > 0 && covered !== len)
      badRuns.push(`${path}:${i + 1} runs=${covered} line=${len}`);
  });
}
check(
  `${lines - badRuns.length}/${lines} highlighted lines round-trip exactly`,
  badRuns.length === 0,
  badRuns,
);

const mathErrors = corpus.docs.filter((d) => d.html.includes("math-error"));
check(
  `no KaTeX render errors`,
  mathErrors.length === 0,
  mathErrors.map((d) => d.path),
);

check(
  `${corpus.stats.mermaid} mermaid diagrams extracted`,
  corpus.stats.mermaid >= 10,
);
const emptyDiagrams = corpus.docs.flatMap((d) =>
  d.mermaid.filter((m) => !m.code.trim()),
);
check(`no empty diagram sources`, emptyDiagrams.length === 0);

const undefined_ = corpus.glossary.filter((g) => !g.html.trim());
check(
  `${corpus.glossary.length} glossary terms, all defined`,
  corpus.glossary.length >= 10 && undefined_.length === 0,
  undefined_.map((g) => g.term),
);

check(
  `${LEXICON.length} lexicon terms, all app-authored and badged`,
  LEXICON.every((e) => e.definition),
);

const glossaryTerms = new Set(corpus.glossary.map((g) => g.term.toLowerCase()));
const collisions = LEXICON.filter((e) =>
  glossaryTerms.has(e.term.toLowerCase()),
);
check(
  `lexicon never shadows a glossary term`,
  collisions.length === 0,
  collisions.map((c) => c.term),
);

const badSee = LEXICON.filter((e) => {
  if (!e.see) return false;
  const [docId, slug] = e.see.split("#");
  const set = anchors.get(docId);
  return !set || (slug ? !set.has(slug) : false);
});
check(
  `every lexicon cross-reference resolves`,
  badSee.length === 0,
  badSee.map((e) => `${e.term} → ${e.see}`),
);

const badCheckpoints = corpus.checkpoints.filter((c) => {
  const set = anchors.get(c.answerDoc);
  return !set || (c.answerAnchor ? !set.has(c.answerAnchor) : false);
});
check(
  `${corpus.checkpoints.length} checkpoints, every answer resolves`,
  corpus.checkpoints.length >= 5 && badCheckpoints.length === 0,
  badCheckpoints.map((c) => `${c.n} → ${c.answerDoc}#${c.answerAnchor}`),
);

check(
  `${corpus.sessions.length} reading sessions (${corpus.sessions.map((s) => `${s.minutes}m`).join(", ")})`,
  corpus.sessions.length === 3 &&
    corpus.sessions.every((s) => s.docs.length > 0 && s.minutes > 0),
);

const badEntities = corpus.entities.filter((e) => {
  const set = anchors.get(e.doc);
  return !set || (e.anchor ? !set.has(e.anchor) : false);
});
check(
  `${corpus.entities.length} entities all resolve`,
  badEntities.length === 0,
  badEntities.map((e) => `${e.kind} ${e.name} → ${e.doc}#${e.anchor}`),
);

const docIds = new Set(corpus.docs.map((d) => d.id));
const required = [
  "00-reading-path",
  "glossary",
  "explanation/architecture",
  "explanation/security-model",
  "getting-started/onboarding",
  "diagrams/README",
];
const missingRequired = required.filter((id) => !docIds.has(id));
check(
  `required corpus ids present (${required.length})`,
  missingRequired.length === 0,
  missingRequired,
);

const stale = corpus.docs.filter((d) => (d.commitsBehind ?? 0) > 0);
console.log(
  stale.length
    ? `· ${stale.length} document(s) verified against an older commit than ${corpus.head}`
    : `· every verified document is current at ${corpus.head}`,
);

console.log("");
if (failures) {
  console.error(`${failures} check(s) failed.`);
  process.exit(1);
}
console.log("All checks passed.");
