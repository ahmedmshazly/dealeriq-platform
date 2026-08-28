import { Marked } from "marked";
import { slugify, plainText } from "../../src/lib/slug.js";
import type {
  Checkpoint,
  Entity,
  GlossaryTerm,
  ReadingSession,
} from "../../src/types.js";

const inline = new Marked({ gfm: true });
const renderInline = (md: string): string =>
  inline.parseInline(md, { async: false }) as string;

/**
 * `docs/glossary.md` is a flat list of `### term` headings with 1-2 prose
 * paragraphs each.
 */
export function extractGlossary(md: string): GlossaryTerm[] {
  const out: GlossaryTerm[] = [];
  const lines = md.split("\n");
  let current: { term: string; body: string[] } | null = null;
  let inFence = false;

  const flush = (): void => {
    if (!current) return;
    const body = current.body.join("\n").trim();
    out.push({
      term: current.term,
      slug: slugify(current.term),
      html: renderInline(firstParagraph(body)),
      text: plainText(renderInline(body)),
    });
    current = null;
  };

  for (const line of lines) {
    if (/^\s*```/.test(line)) inFence = !inFence;
    const m = !inFence && /^### (.+?)\s*$/.exec(line);
    if (m) {
      flush();
      current = { term: plainText(renderInline(m[1])), body: [] };
    } else if (current) {
      current.body.push(line);
    }
  }
  flush();
  return out;
}

function firstParagraph(body: string): string {
  const para = body.split(/\n\s*\n/)[0] ?? "";
  return para.replace(/\n/g, " ").trim();
}

const ENTITY_SECTIONS: Record<string, Entity["kind"]> = {
  "HTTP routes": "route",
  Pages: "page",
  "Postgres tables": "collection",
  "Firestore collections": "collection",
  "Environment variables": "env",
  "Scripts & config files": "script",
  "Documentation map": "page",
};

/**
 * Resolve markdown links to corpus ids.
 * - `./architecture/overview.md` → `architecture/overview`
 * - `./governance/srs.md#…` → `governance/srs`
 * - `./00-reading-path.md` → `00-reading-path`
 * - `./glossary.md` → `glossary`
 */
const DOC_HREF =
  /\]\((?:\.\.?\/)?((?:[\w.-]+\/)*[\w.-]+)\.md(?:#([^)]+))?\)/i;
const DOC_HREF_G =
  /\]\((?:\.\.?\/)?((?:[\w.-]+\/)*[\w.-]+)\.md(?:#([^)]+))?\)/gi;

function pathToDocId(relPath: string): string {
  const clean = relPath.replace(/\\/g, "/").replace(/^\.\//, "");
  // Drop leading ../ segments - reading-path lives at docs/ root
  const parts = clean.split("/");
  while (parts[0] === "..") parts.shift();
  const joined = parts.join("/").replace(/\.md$/i, "");
  if (!joined.includes("/")) return joined.toLowerCase();
  return joined;
}

function docTarget(
  line: string,
): { doc: string; anchor: string | null } | null {
  const m = DOC_HREF.exec(line);
  if (!m) return null;
  return {
    doc: pathToDocId(m[1]),
    anchor: m[2] ? decodeURIComponent(m[2]) : null,
  };
}

export function extractEntities(md: string): Entity[] {
  const out: Entity[] = [];
  let kind: Entity["kind"] | null = null;

  for (const line of md.split("\n")) {
    const h = /^## (.+?)\s*$/.exec(line);
    if (h) {
      kind = ENTITY_SECTIONS[h[1].trim()] ?? null;
      continue;
    }
    if (!kind || !line.startsWith("|")) continue;

    const cells = splitRow(line);
    if (cells.length < 2) continue;
    const name = stripMd(cells[0]);
    if (!name || /^-+$/.test(name) || /^(route|path|document)$/i.test(name))
      continue;

    const target = docTarget(line);
    if (!target) continue;

    out.push({ kind, name, detail: stripMd(cells[1] ?? ""), ...target });
  }
  return out;
}

/**
 * `docs/00-reading-path.md` - sessions + checkpoints for the study UI.
 */
export function extractReadingPath(md: string): {
  sessions: ReadingSession[];
  checkpoints: Checkpoint[];
} {
  const sessions: ReadingSession[] = [];
  const checkpoints: Checkpoint[] = [];
  const lines = md.split("\n");

  let session: ReadingSession | null = null;
  let inCheckpoints = false;
  let pending: string | null = null;

  for (const line of lines) {
    if (/^## /.test(line)) {
      session = null;
      inCheckpoints = /^## Checkpoints/i.test(line);

      const sh = /^## Session (\d+)\s*[---]\s*(.+?)\s*$/.exec(line);
      if (sh) {
        session = {
          n: Number(sh[1]),
          title: plainText(renderInline(sh[2])),
          anchor: slugify(plainText(renderInline(line.replace(/^## /, "")))),
          docs: [],
          minutes: 0,
        };
        sessions.push(session);
      }
      continue;
    }

    if (session) {
      for (const m of line.matchAll(DOC_HREF_G)) {
        const id = pathToDocId(m[1]);
        if (!session.docs.includes(id)) session.docs.push(id);
      }
      for (const m of line.matchAll(/~\s*(\d+)\s*min/gi)) {
        session.minutes += Number(m[1]);
      }
      continue;
    }

    if (!inCheckpoints) continue;

    const q = /^\s*\d+\.\s+\*\*(.+?)\*\*\s*$/.exec(line);
    if (q) {
      pending = plainText(renderInline(q[1]));
      continue;
    }

    if (pending) {
      const a = docTarget(line);
      const label = /\[([^\]]+)\]\(/.exec(line);
      if (a) {
        checkpoints.push({
          n: checkpoints.length + 1,
          question: pending,
          answerLabel: label ? plainText(renderInline(label[1])) : a.doc,
          answerDoc: a.doc,
          answerAnchor: a.anchor,
        });
        pending = null;
      } else if (line.trim() === "") {
        pending = null;
      }
    }
  }

  return { sessions, checkpoints };
}

const splitRow = (line: string): string[] =>
  line
    .replace(/^\|/, "")
    .replace(/\|\s*$/, "")
    .split(/(?<!\\)\|/)
    .map((c) => c.trim());

const stripMd = (s: string): string => plainText(renderInline(s)).trim();
