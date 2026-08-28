/**
 * The contract between the build-time indexer and the runtime client.
 *
 * Everything expensive — markdown parsing, syntax highlighting, math rendering,
 * search-index construction, the doc↔code join — happens once in
 * `scripts/build-index.ts` and lands here. The client only reads.
 */

/**
 * The corpus is not uniform, and pretending otherwise is how you get crashes.
 * Only `handbook` docs carry a nav footer; only 17 of 29 have a `## Contents`;
 * five `background` files have no front-matter at all.
 */
export type Tier = "handbook" | "meta" | "stub" | "background";

export interface Heading {
  depth: number;
  /** Plain text, entities decoded, tags stripped — what GitHub slugged. */
  text: string;
  slug: string;
}

export interface DocLink {
  /** Target doc id, or null for an intra-document link. */
  to: string | null;
  anchor: string | null;
  text: string;
  /** The section of the *source* doc the link was written in. */
  fromAnchor: string | null;
}

/**
 * A backticked reference, tagged with the section it appeared in. This is what
 * lets the code viewer say "documented in 06 § Security rules" against a line,
 * rather than the useless "mentioned somewhere in 06".
 */
export interface Citation {
  kind: "file" | "symbol" | "env" | "route" | "collection";
  value: string;
  anchor: string | null;
}

export interface Backlink {
  from: string;
  fromTitle: string;
  /** Which anchor of the *target* was cited. */
  anchor: string | null;
  /** Which section of the *source* the link was written in — where to land. */
  fromAnchor: string | null;
  /** A human label for that source section, e.g. `06 § Security rules`. */
  context: string;
}

export interface MermaidBlock {
  id: string;
  /** The diagram kind, e.g. `flowchart`, `erDiagram` — used for the caption. */
  kind: string;
  code: string;
}

export interface LastVerified {
  date: string;
  sha: string;
}

export interface Doc {
  /** Route-stable id: `06`, `10b`, `readme`, `glossary`, `bg/vitae-srs`. */
  id: string;
  /** Repo-relative, e.g. `docs/06-data-model.md`. */
  path: string;
  tier: Tier;
  /** Sort order within the tier. */
  order: number;
  /** The `06` / `10b` prefix, or null for unnumbered docs. */
  num: string | null;
  title: string;
  description: string | null;
  keywords: string[];
  lastVerified: LastVerified | null;
  /** Fully rendered: Shiki fences, KaTeX math, mermaid placeholders, ref spans. */
  html: string;
  headings: Heading[];
  words: number;
  readMinutes: number;
  mermaid: MermaidBlock[];
  mathCount: number;
  links: DocLink[];
  backlinks: Backlink[];
  /** Source paths this doc cites in backticks. */
  citedFiles: string[];
  citedSymbols: string[];
  prev: string | null;
  next: string | null;
  hasToc: boolean;
  /** Commits touching `docs/` since this doc's `last-verified` sha. */
  commitsBehind: number | null;
}

export type SymbolKind =
  | "function"
  | "const"
  | "class"
  | "type"
  | "interface"
  | "default";

export interface SourceSymbol {
  name: string;
  kind: SymbolKind;
  /** 1-indexed. */
  line: number;
  /** The declaration line, trimmed — enough to show in a popover. */
  signature: string;
  file: string;
  /** Doc ids whose prose mentions this symbol in backticks. */
  citedBy: string[];
}

export interface SourceFile {
  path: string;
  lang: string;
  loc: number;
  bytes: number;
  symbols: SourceSymbol[];
  /** Doc ids that cite this path in backticks. */
  citedBy: string[];
  /** Total number of backtick mentions across the corpus — the Atlas ranking. */
  mentions: number;
}

/**
 * Syntax-highlighting payload, kept out of the main corpus and loaded on demand.
 *
 * Dual-theme Shiki HTML measured 12.3× the source (13.2 MB). Instead we ship the
 * raw lines plus a run-length style encoding against a 17-entry palette: each
 * line becomes `"6A7B1C"` — decimal run length followed by a single letter that
 * indexes `palette`. Roughly 1.7 MB for all 212 files, and it leaves the client
 * owning the render, which is what makes per-line gutter annotations possible.
 */
export interface CodePayload {
  /** `[lightColor, darkColor]` pairs; index is the letter's position in A..Z. */
  palette: [string, string][];
  files: Record<string, CodeFile>;
}

export interface CodeFile {
  lines: string[];
  /** One run-string per line, parallel to `lines`. */
  runs: string[];
  /** Line number (1-indexed) → doc anchors like `06#security-rules`. */
  annotations: Record<string, string[]>;
}

export interface GlossaryTerm {
  term: string;
  slug: string;
  /** Rendered definition, for the popover body. */
  html: string;
  /** Plain text, for search. */
  text: string;
}

/** A searchable unit: one heading section, not one file. */
export interface Section {
  id: string;
  doc: string;
  docTitle: string;
  anchor: string;
  /** e.g. `Collections › comments`. */
  path: string;
  title: string;
  depth: number;
  tier: Tier;
}

/** Everything the palette can jump to, beyond docs and headings. */
export interface Entity {
  kind: "route" | "collection" | "env" | "page" | "script";
  name: string;
  detail: string;
  doc: string;
  anchor: string | null;
}

export interface Checkpoint {
  n: number;
  question: string;
  answerDoc: string;
  answerAnchor: string | null;
  answerLabel: string;
}

export interface ReadingSession {
  n: number;
  title: string;
  anchor: string;
  docs: string[];
  minutes: number;
}

export interface CorpusStats {
  docs: number;
  words: number;
  headings: number;
  links: number;
  mermaid: number;
  math: number;
  sourceFiles: number;
  citedFiles: number;
  symbols: number;
  glossaryTerms: number;
  readMinutes: number;
}

export interface Corpus {
  generatedAt: string;
  /** `git rev-parse --short HEAD` at index time. */
  head: string;
  docs: Doc[];
  glossary: GlossaryTerm[];
  files: SourceFile[];
  sections: Section[];
  entities: Entity[];
  checkpoints: Checkpoint[];
  sessions: ReadingSession[];
  /** Serialized MiniSearch index over `sections`. */
  search: unknown;
  stats: CorpusStats;
}
