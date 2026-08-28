import { Marked, type Tokens } from "marked";
import type { HighlighterGeneric, BundledLanguage, BundledTheme } from "shiki";
import { Slugger, plainText } from "../../src/lib/slug.js";
import type {
  Citation,
  DocLink,
  Heading,
  MermaidBlock,
} from "../../src/types.js";

export interface RenderContext {
  /** Repo-relative path of the doc being rendered, e.g. `docs/06-data-model.md`. */
  path: string;
  /** `docs/06-data-model.md` → `06`. Resolves internal links to routes. */
  docIdByPath: Map<string, string>;
  /** Every indexable source path, for classifying backticked code spans. */
  files: Set<string>;
  /** Exported symbol name → the files that define it. */
  symbols: Map<string, string[]>;
  envVars: Set<string>;
  collections: Set<string>;
  highlighter: HighlighterGeneric<BundledLanguage, BundledTheme>;
  langs: Set<string>;
}

export interface RenderResult {
  html: string;
  headings: Heading[];
  links: DocLink[];
  mermaid: MermaidBlock[];
  citations: Citation[];
  citedFiles: string[];
  citedSymbols: string[];
}

const ROUTE = /^(?:GET|POST|PUT|PATCH|DELETE)?\s*\/[a-z0-9[\]./_-]*$/i;

/** Placeholder anchor for a citation made inside a heading, before its slug exists. */
export const PENDING = "%%PENDING%%";

export function renderDoc(md: string, ctx: RenderContext): RenderResult {
  const slugger = new Slugger();
  const headings: Heading[] = [];
  const links: DocLink[] = [];
  const mermaid: MermaidBlock[] = [];
  const citations: Citation[] = [];
  const citedFiles = new Set<string>();
  const citedSymbols = new Set<string>();

  // Marked renders strictly in document order, so the most recent heading is
  // always the section the current token belongs to.
  let section: string | null = null;

  // Code spans inside a heading are titles, not references: linking them would
  // put an interactive control inside a heading and inside the ToC.
  //
  // They are still *recorded* as citations, because `05-code-reference.md`
  // names each module only in its `### `src/lib/db/articles.ts`` heading. Drop
  // those and the single most code-adjacent document in the corpus contributes
  // nothing to the doc↔code join.
  let inHeading = false;

  const marked = new Marked({ gfm: true, breaks: false });

  marked.use({
    renderer: {
      heading(
        this: { parser: { parseInline(t: Tokens.Generic[]): string } },
        token: Tokens.Heading,
      ) {
        inHeading = true;
        const inner = this.parser.parseInline(token.tokens);
        inHeading = false;
        const text = plainText(inner);
        const slug = slugger.slug(text);
        headings.push({ depth: token.depth, text, slug });
        for (const c of citations) if (c.anchor === PENDING) c.anchor = slug;
        section = slug;
        const d = token.depth;
        // The anchor sits after the text so it reveals on hover without
        // shifting the heading's baseline, and copies a deep link when clicked.
        return (
          `<h${d} id="${slug}" class="hd hd-${d}" tabindex="-1">${inner}` +
          `<a class="hd-anchor" href="#${slug}" aria-label="Link to “${escapeAttr(text)}”">#</a>` +
          `</h${d}>\n`
        );
      },

      code(token: Tokens.Code) {
        const lang = (token.lang ?? "").trim().toLowerCase();

        if (lang === "mermaid") {
          const id = `mmd-${mermaid.length}`;
          const kind = /^\s*(\w+)/.exec(token.text)?.[1] ?? "diagram";
          mermaid.push({ id, kind, code: token.text });
          // Rendered client-side and lazily: mermaid is 2.5 MB, and only 10 of
          // 29 docs need it. The <figure> keeps the caption adjacent to the
          // diagram for screen readers.
          return (
            `<figure class="mermaid" data-mermaid-id="${id}" data-kind="${escapeAttr(kind)}">` +
            `<div class="mermaid-mount" role="img" aria-label="${escapeAttr(kind)} diagram; an equivalent description appears in the surrounding text"></div>` +
            `</figure>\n`
          );
        }

        const useLang = ctx.langs.has(lang) ? lang : "plaintext";
        const html = ctx.highlighter.codeToHtml(token.text, {
          lang: useLang,
          themes: { light: "vitesse-light", dark: "vitesse-dark" },
          defaultColor: false,
        });
        return (
          `<div class="fence" data-lang="${escapeAttr(lang || "text")}">` +
          `<button class="fence-copy" type="button" data-copy aria-label="Copy code">Copy</button>` +
          `${html}</div>\n`
        );
      },

      codespan(token: Tokens.Codespan) {
        const raw = decodeEntities(token.text);
        const esc = escapeHtml(raw);
        const ref = classify(raw, ctx);
        if (!ref) return `<code>${esc}</code>`;

        if (ref.kind === "file") citedFiles.add(ref.value);
        if (ref.kind === "symbol") citedSymbols.add(ref.value);

        // A heading's own slug is not known until after its children render, so
        // attribute its citations to the section it opens, not the previous one.
        // `build-index.ts` resolves `PENDING` once the slug exists.
        citations.push({ ...ref, anchor: inHeading ? PENDING : section });

        if (inHeading) return `<code>${esc}</code>`;
        return `<code class="ref ref-${ref.kind}" data-ref="${ref.kind}" data-ref-value="${escapeAttr(ref.value)}" tabindex="0">${esc}</code>`;
      },

      link(
        this: { parser: { parseInline(t: Tokens.Generic[]): string } },
        token: Tokens.Link,
      ) {
        const inner = this.parser.parseInline(token.tokens);
        const href = token.href ?? "";
        const title = token.title ? ` title="${escapeAttr(token.title)}"` : "";

        if (href.startsWith("#")) {
          const anchor = decodeURIComponent(href.slice(1));
          links.push({
            to: null,
            anchor,
            text: plainText(inner),
            fromAnchor: section,
          });
          return `<a class="lk lk-jump" href="#${escapeAttr(anchor)}" data-jump="${escapeAttr(anchor)}"${title}>${inner}</a>`;
        }

        if (/^(https?:)?\/\//.test(href) || href.startsWith("mailto:")) {
          return `<a class="lk lk-ext" href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer"${title}>${inner}<span class="lk-ext-mark" aria-hidden="true">↗</span></a>`;
        }

        const [rawPath, rawAnchor] = href.split("#");
        const resolved = resolveRelative(ctx.path, rawPath);
        const anchor = rawAnchor ? decodeURIComponent(rawAnchor) : null;
        const targetId = ctx.docIdByPath.get(resolved);

        if (targetId) {
          links.push({
            to: targetId,
            anchor,
            text: plainText(inner),
            fromAnchor: section,
          });
          const to = `#/doc/${targetId}${anchor ? `#${anchor}` : ""}`;
          return `<a class="lk lk-doc" href="${escapeAttr(to)}" data-doc="${escapeAttr(targetId)}"${anchor ? ` data-anchor="${escapeAttr(anchor)}"` : ""}${title}>${inner}</a>`;
        }

        if (ctx.files.has(resolved)) {
          citedFiles.add(resolved);
          citations.push({ kind: "file", value: resolved, anchor: section });
          return `<a class="lk lk-file" href="#/code/${escapeAttr(resolved)}" data-ref="file" data-ref-value="${escapeAttr(resolved)}"${title}>${inner}</a>`;
        }

        // A relative link that resolves to nothing indexable. Keep the text, drop
        // the href - a dead link that looks alive is worse than plain prose.
        return `<span class="lk lk-dead" title="Unresolved: ${escapeAttr(href)}">${inner}</span>`;
      },

      table(token: Tokens.Table) {
        const head = token.header
          .map(
            (c, i) => `<th${align(token.align[i])}>${inlineOf(this, c)}</th>`,
          )
          .join("");
        const body = token.rows
          .map(
            (row) =>
              `<tr>${row.map((c, i) => `<td${align(token.align[i])}>${inlineOf(this, c)}</td>`).join("")}</tr>`,
          )
          .join("");
        // The widest row in this corpus is ~1,100 characters. `tabindex="0"` is
        // required: a scrollable region must be reachable by keyboard.
        return (
          `<div class="table-wrap" role="region" tabindex="0" aria-label="Table">` +
          `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>` +
          `</div>\n`
        );
      },
    },
  });

  const html = marked.parse(md, { async: false }) as string;

  return {
    html,
    headings,
    links,
    mermaid,
    citations,
    citedFiles: [...citedFiles],
    citedSymbols: [...citedSymbols],
  };
}

type Ref = {
  kind: "file" | "symbol" | "env" | "route" | "collection";
  value: string;
};

/**
 * Decide what a backticked span *is*. This is what turns inert prose into a
 * navigable graph: the docs cite 107 source paths and hundreds of symbols, but
 * they are just code spans until something classifies them.
 *
 * Order matters. A path is unambiguous, so it wins. A symbol name that collides
 * with an env var or a collection is far less likely than the reverse.
 */
function classify(raw: string, ctx: RenderContext): Ref | null {
  const t = raw.trim();
  if (!t || t.length > 120 || /\s{2,}/.test(t)) return null;

  if (ctx.files.has(t)) return { kind: "file", value: t };

  // `src/lib/db/comments.ts:42` - a path with a line number.
  const withLine = /^([\w./[\]-]+\.\w+):\d+$/.exec(t);
  if (withLine && ctx.files.has(withLine[1]))
    return { kind: "file", value: withLine[1] };

  // Two characters is not a symbol reference, it is a variable in a formula.
  if (t.length >= 3 && ctx.symbols.has(t)) return { kind: "symbol", value: t };

  // `getArticles()` - a call, not a reference.
  const called = /^([A-Za-z_$][\w$]*)\(\)$/.exec(t);
  if (called && called[1].length >= 3 && ctx.symbols.has(called[1]))
    return { kind: "symbol", value: called[1] };

  if (ctx.envVars.has(t)) return { kind: "env", value: t };
  if (ctx.collections.has(t)) return { kind: "collection", value: t };

  if (ROUTE.test(t) && t.includes("/")) return { kind: "route", value: t };

  return null;
}

/** Resolve `./x.md` / `../SECURITY.md` against the doc's own directory. */
function resolveRelative(from: string, rel: string): string {
  const base = from.split("/").slice(0, -1);
  const parts = rel.split("/");
  for (const p of parts) {
    if (p === "." || p === "") continue;
    else if (p === "..") base.pop();
    else base.push(p);
  }
  return base.join("/");
}

function inlineOf(self: unknown, cell: Tokens.TableCell): string {
  const r = self as { parser: { parseInline(t: Tokens.Generic[]): string } };
  return r.parser.parseInline(cell.tokens);
}

const align = (a: string | null): string =>
  a ? ` style="text-align:${a}"` : "";

const escapeHtml = (s: string): string =>
  s.replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!,
  );
const escapeAttr = escapeHtml;

/** Marked hands `codespan` its text already entity-escaped; undo that to classify. */
const decodeEntities = (s: string): string =>
  s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&");
