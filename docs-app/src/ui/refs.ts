import type {
  Corpus,
  GlossaryTerm,
  SourceFile,
  SourceSymbol,
} from "../types.js";
import { LEXICON_INDEX, type LexiconEntry } from "../lexicon/lexicon.js";
import { $$, escapeHtml, h } from "../lib/dom.js";
import { state } from "../lib/store.js";

/**
 * The reference layer: everything on screen that can explain itself.
 *
 * Five kinds, one popover. What distinguishes them is provenance — three come
 * from the repository, one from `glossary.md`, and one from a file I wrote. The
 * last is the only one that must never be mistaken for the others, so it alone
 * carries a dashed badge.
 */
export type RefKind =
  | "glossary"
  | "lexicon"
  | "symbol"
  | "file"
  | "doc"
  | "env"
  | "route"
  | "collection";

const KIND_COLOR: Record<RefKind, string> = {
  glossary: "var(--accent)",
  lexicon: "var(--accent-3)",
  symbol: "var(--accent-2)",
  file: "var(--accent-2)",
  doc: "var(--muted)",
  env: "var(--accent-3)",
  route: "var(--accent)",
  collection: "var(--accent)",
};

const KIND_LABEL: Record<RefKind, string> = {
  glossary: "Glossary",
  lexicon: "General term",
  symbol: "Symbol",
  file: "File",
  doc: "Section",
  env: "Env var",
  route: "Route",
  collection: "Collection",
};

export interface RefIndex {
  glossary: Map<string, GlossaryTerm>;
  files: Map<string, SourceFile>;
  symbols: Map<string, SourceSymbol[]>;
  docs: Corpus["docs"];
}

export function buildRefIndex(corpus: Corpus): RefIndex {
  const symbols = new Map<string, SourceSymbol[]>();
  for (const f of corpus.files) {
    for (const s of f.symbols) {
      const list = symbols.get(s.name) ?? [];
      list.push(s);
      symbols.set(s.name, list);
    }
  }
  return {
    glossary: new Map(corpus.glossary.map((g) => [g.term.toLowerCase(), g])),
    files: new Map(corpus.files.map((f) => [f.path, f])),
    symbols,
    docs: corpus.docs,
  };
}

/* ── auto-linking ──────────────────────────────────────────────── */

/**
 * Never inside a heading, a link, code, or an existing term. A term is linked at
 * most once per section, and never on the page that defines it.
 *
 * This restraint is the whole feature. Mark up every occurrence of every term
 * and `05-code-reference.md` — the densest document in the corpus — becomes a
 * field of dotted underlines that nobody can read through.
 */
const SKIP = new Set([
  "A",
  "CODE",
  "PRE",
  "H1",
  "H2",
  "H3",
  "H4",
  "H5",
  "H6",
  "BUTTON",
  "SCRIPT",
  "STYLE",
]);

export function decorateTerms(
  root: HTMLElement,
  index: RefIndex,
  docId: string,
): void {
  if (docId === "glossary") return;

  const seen = new Set<string>();
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      let el = node.parentElement;
      while (el && el !== root) {
        if (SKIP.has(el.tagName) || el.classList.contains("term"))
          return NodeFilter.FILTER_REJECT;
        el = el.parentElement;
      }
      return node.nodeValue && node.nodeValue.trim().length > 3
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT;
    },
  });

  const texts: Text[] = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode())
    texts.push(n as Text);

  for (const node of texts) {
    // Reset once per H2 so a long document can re-introduce a term it used
    // twenty paragraphs ago.
    const section = node.parentElement?.closest("h2")?.id ?? sectionOf(node);
    const match = firstTerm(node.nodeValue ?? "", index, seen, section);
    if (!match) continue;

    const { start, length, kind, key } = match;
    seen.add(`${section}:${key}`);

    const after = node.splitText(start);
    after.splitText(length);
    const span = h("span", {
      class: "term",
      "data-term": kind,
      "data-term-key": key,
      tabindex: "0",
      role: "button",
      "aria-label": `${KIND_LABEL[kind]}: ${after.nodeValue}`,
    });
    after.replaceWith(span);
    span.append(after.nodeValue ?? "");
  }
}

function sectionOf(node: Text): string {
  let el: Element | null = node.parentElement;
  while (el) {
    const prev: Element | null = el.previousElementSibling;
    if (prev?.tagName === "H2") return prev.id;
    el = el.previousElementSibling ?? el.parentElement;
    if (el?.classList.contains("prose")) break;
  }
  return "";
}

interface TermMatch {
  start: number;
  length: number;
  kind: "glossary" | "lexicon";
  key: string;
}

function firstTerm(
  text: string,
  index: RefIndex,
  seen: Set<string>,
  section: string,
): TermMatch | null {
  const lower = text.toLowerCase();

  // Glossary first: it is the repository's own vocabulary and outranks mine.
  for (const [key, term] of index.glossary) {
    if (seen.has(`${section}:${key}`)) continue;
    const at = wordIndex(lower, key);
    if (at >= 0)
      return { start: at, length: term.term.length, kind: "glossary", key };
  }

  for (const { key, entry } of LEXICON_INDEX) {
    const k = key.toLowerCase();
    if (seen.has(`${section}:${entry.term.toLowerCase()}`)) continue;
    const at = wordIndex(lower, k);
    if (at >= 0) {
      return {
        start: at,
        length: key.length,
        kind: "lexicon",
        key: entry.term.toLowerCase(),
      };
    }
  }
  return null;
}

/** Whole-word only: "block" must not match inside "blocking". */
function wordIndex(hay: string, needle: string): number {
  let from = 0;
  for (;;) {
    const at = hay.indexOf(needle, from);
    if (at < 0) return -1;
    const before = at === 0 || !/[\w-]/.test(hay[at - 1]);
    const afterAt = at + needle.length;
    const after = afterAt >= hay.length || !/[\w-]/.test(hay[afterAt]);
    if (before && after) return at;
    from = at + 1;
  }
}

/* ── popover ───────────────────────────────────────────────────── */

let pop: HTMLElement | null = null;
let openTimer: number | undefined;
let closeTimer: number | undefined;

export interface PopoverDeps {
  index: RefIndex;
  openCode: (path: string, line?: number) => void;
  openDoc: (doc: string, anchor?: string | null) => void;
}

export function installReferenceLayer(
  root: HTMLElement,
  deps: PopoverDeps,
): void {
  const arm = (target: HTMLElement): void => {
    clearTimeout(closeTimer);
    clearTimeout(openTimer);
    // 220 ms: long enough that sweeping the pointer across a paragraph of
    // references does not strobe, short enough to feel like a hover, not a wait.
    openTimer = window.setTimeout(() => show(target, deps), 220);
  };

  const disarm = (): void => {
    clearTimeout(openTimer);
    clearTimeout(closeTimer);
    // A grace period so the pointer can travel from the trigger into the popover.
    closeTimer = window.setTimeout(hide, 120);
  };

  const triggers = "[data-ref],[data-term],a.lk-doc";

  root.addEventListener("pointerover", (e) => {
    const t = (e.target as HTMLElement).closest<HTMLElement>(triggers);
    if (!t) return;
    if (t.matches("[data-term]") && !state.refs) return;
    arm(t);
  });
  root.addEventListener("pointerout", (e) => {
    if ((e.target as HTMLElement).closest(triggers)) disarm();
  });
  root.addEventListener("focusin", (e) => {
    const t = (e.target as HTMLElement).closest<HTMLElement>(triggers);
    if (t) show(t, deps);
  });
  root.addEventListener("focusout", disarm);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && pop) {
      hide();
      e.stopPropagation();
    }
  });
}

export function hide(): void {
  pop?.remove();
  pop = null;
}

function show(target: HTMLElement, deps: PopoverDeps): void {
  hide();
  const content = build(target, deps);
  if (!content) return;

  pop = content;
  document.body.append(pop);
  pop.addEventListener("pointerenter", () => clearTimeout(closeTimer));
  pop.addEventListener("pointerleave", hide);
  place(pop, target);
}

/** Never clip: flip above when there is no room below, and clamp horizontally. */
function place(el: HTMLElement, target: HTMLElement): void {
  const t = target.getBoundingClientRect();
  const r = el.getBoundingClientRect();
  const pad = 10;

  let top = t.bottom + 8;
  if (top + r.height > window.innerHeight - pad)
    top = Math.max(pad, t.top - r.height - 8);

  let left = t.left + t.width / 2 - r.width / 2;
  left = Math.max(pad, Math.min(left, window.innerWidth - r.width - pad));

  el.style.top = `${top}px`;
  el.style.left = `${left}px`;
}

function build(target: HTMLElement, deps: PopoverDeps): HTMLElement | null {
  const { index } = deps;

  if (target.dataset.term) {
    const key = target.dataset.termKey ?? "";
    if (target.dataset.term === "glossary") {
      const g = index.glossary.get(key);
      return g
        ? shell("glossary", g.term, [
            h("div", { class: "pop-body", html: g.html }),
          ])
        : null;
    }
    const entry = LEXICON_INDEX.find(
      (x) => x.entry.term.toLowerCase() === key,
    )?.entry;
    return entry ? lexiconPop(entry, deps) : null;
  }

  const kind = target.dataset.ref as RefKind | undefined;
  const value = target.dataset.refValue ?? "";

  if (kind === "file") return filePop(value, deps);
  if (kind === "symbol") return symbolPop(value, deps);
  if (kind === "env" || kind === "route" || kind === "collection") {
    return shell(kind, value, [
      h(
        "div",
        { class: "pop-body" },
        `${KIND_LABEL[kind]} referenced by the handbook.`,
      ),
    ]);
  }

  if (target.matches("a.lk-doc")) return docPop(target, deps);
  return null;
}

function shell(
  kind: RefKind,
  title: string,
  body: Node[],
  foot?: Node,
): HTMLElement {
  const el = h(
    "div",
    {
      class: "pop",
      role: "dialog",
      "aria-label": `${KIND_LABEL[kind]}: ${title}`,
    },
    h(
      "div",
      { class: "pop-head" },
      h("span", { class: "pop-kind" }, KIND_LABEL[kind]),
      h("span", { class: "pop-title" }, title),
    ),
    ...body,
    foot,
  );
  el.style.setProperty("--kind", KIND_COLOR[kind]);
  return el;
}

function lexiconPop(entry: LexiconEntry, deps: PopoverDeps): HTMLElement {
  const foot = h(
    "div",
    { class: "pop-foot" },
    // The single most important element in this file. A definition I wrote must
    // never be mistaken for one the repository vouches for.
    h("span", { class: "pop-authored" }, "written by the reader"),
    entry.see
      ? h(
          "button",
          {
            class: "pop-open",
            onclick: () => {
              const [doc, anchor] = entry.see!.split("#");
              hide();
              deps.openDoc(doc, anchor ?? null);
            },
          },
          "In the handbook →",
        )
      : null,
  );
  return shell(
    "lexicon",
    entry.term,
    [h("div", { class: "pop-body" }, entry.definition)],
    foot,
  );
}

function filePop(path: string, deps: PopoverDeps): HTMLElement | null {
  const f = deps.index.files.get(path);
  if (!f) return null;

  const body = h(
    "div",
    { class: "pop-body" },
    h(
      "div",
      {},
      `${f.lang} · ${f.loc.toLocaleString()} lines · ${f.symbols.length} exports`,
    ),
  );
  const foot = h(
    "div",
    { class: "pop-foot" },
    h(
      "span",
      {},
      f.citedBy.length
        ? `cited by ${f.citedBy.length} document${f.citedBy.length > 1 ? "s" : ""}`
        : "not documented",
    ),
    h(
      "button",
      { class: "pop-open", onclick: () => (hide(), deps.openCode(path)) },
      "Open source →",
    ),
  );
  return shell("file", path, [body], foot);
}

function symbolPop(name: string, deps: PopoverDeps): HTMLElement | null {
  const defs = deps.index.symbols.get(name);
  if (!defs?.length) return null;
  const s = defs[0];

  const body = h(
    "div",
    { class: "pop-body" },
    h("code", { class: "pop-sig" }, s.signature),
    defs.length > 1
      ? h("div", {}, `Also defined in ${defs.length - 1} other file(s).`)
      : null,
  );
  const foot = h(
    "div",
    { class: "pop-foot" },
    h("span", {}, `${s.file}:${s.line}`),
    h(
      "button",
      {
        class: "pop-open",
        onclick: () => (hide(), deps.openCode(s.file, s.line)),
      },
      "Open source →",
    ),
  );
  return shell("symbol", name, [body], foot);
}

/**
 * Hovering `[06 § Security rules]` shows that section's opening prose. It is the
 * difference between a link you must follow and a link you can evaluate.
 */
function docPop(a: HTMLElement, deps: PopoverDeps): HTMLElement | null {
  const docId = a.dataset.doc ?? "";
  const anchor = a.dataset.anchor ?? null;
  const doc = deps.index.docs.find((d) => d.id === docId);
  if (!doc) return null;

  const title = anchor
    ? (doc.headings.find((x) => x.slug === anchor)?.text ?? doc.title)
    : doc.title;

  const excerpt = firstProse(doc.html, anchor);
  const body = h(
    "div",
    { class: "pop-body" },
    h("div", { html: excerpt || escapeHtml(doc.description ?? "") }),
  );
  const foot = h(
    "div",
    { class: "pop-foot" },
    h("span", {}, `${doc.num ?? doc.id} · ${doc.readMinutes} min read`),
    h(
      "button",
      {
        class: "pop-open",
        onclick: () => (hide(), deps.openDoc(docId, anchor)),
      },
      "Open →",
    ),
  );
  return shell("doc", title, [body], foot);
}

const parser = new DOMParser();

function firstProse(html: string, anchor: string | null): string {
  const doc = parser.parseFromString(html, "text/html");
  let node: Element | null = anchor
    ? doc.getElementById(anchor)
    : doc.body.firstElementChild;
  if (!node) return "";

  for (let i = 0; i < 12 && node; i++) {
    node = node.nextElementSibling;
    if (node?.tagName === "P") {
      const text = node.textContent ?? "";
      return escapeHtml(
        text.length > 260 ? text.slice(0, 258).trimEnd() + "…" : text,
      );
    }
    if (node && /^H[1-4]$/.test(node.tagName)) break;
  }
  return "";
}

/** Rebuild the `.term` markup after the reference layer is toggled. */
export function refreshTerms(): void {
  document.documentElement.dataset.refs = state.refs ? "on" : "off";
  for (const el of $$(".term"))
    el.setAttribute("aria-disabled", String(!state.refs));
}
