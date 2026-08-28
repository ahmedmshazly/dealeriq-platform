import type { Corpus } from "../types.js";
import { clear, h } from "../lib/dom.js";
import { fuzzy, markHits, type Search } from "../lib/search.js";
import { bumpFreq, state } from "../lib/store.js";

/**
 * The command palette.
 *
 * One input, seven kinds of destination, and prefix modes borrowed from editors:
 *
 *   >  commands      #  headings (452)    @  symbols
 *   /  files         ?  glossary          :  entities (routes, collections, env)
 *
 * With no prefix it searches everything at once, ranked by fuzzy score and then
 * by how often you have chosen that item before. Typing `contact` surfaces the
 * *route* `POST /api/contact`, not merely prose containing the word — because
 * `docs/index.md` already enumerates every route, and the indexer read it.
 */
export interface Command {
  id: string;
  title: string;
  sub?: string;
  run: () => void;
}

interface Item {
  id: string;
  kind: string;
  title: string;
  sub: string;
  run: () => void;
  /** Static weight so a document outranks a deep heading at equal fuzzy score. */
  weight: number;
}

export interface PaletteDeps {
  corpus: Corpus;
  search: Search;
  commands: Command[];
  openDoc: (doc: string, anchor?: string | null) => void;
  openCode: (path: string, line?: number) => void;
  openSearch: (q: string) => void;
}

const MODES: Record<string, string[]> = {
  ">": ["command"],
  "#": ["heading"],
  "@": ["symbol"],
  "/": ["file"],
  "?": ["glossary"],
  ":": ["route", "collection", "env", "page", "script"],
};

let el: HTMLElement | null = null;
let scrim: HTMLElement | null = null;

export const isOpen = (): boolean => el !== null;

export function openPalette(deps: PaletteDeps, initial = ""): void {
  if (el) return;
  const all = buildItems(deps);

  const input = h("input", {
    class: "pal-input",
    type: "text",
    placeholder:
      "Jump to anything…   > commands   # headings   @ symbols   / files   ? glossary",
    "aria-label": "Search the handbook",
    autocomplete: "off",
    spellcheck: "false",
    value: initial,
  }) as HTMLInputElement;

  const list = h("ul", { class: "pal-list", role: "listbox" });
  const status = h(
    "div",
    { class: "pal-foot" },
    hint("↑↓", "navigate"),
    hint("↵", "open"),
    hint("esc", "close"),
  );

  el = h(
    "div",
    {
      class: "pal",
      role: "dialog",
      "aria-modal": "true",
      "aria-label": "Command palette",
    },
    input,
    list,
    status,
  );
  scrim = h("div", { class: "scrim", onclick: closePalette });
  document.body.append(scrim, el);

  let items: Item[] = [];
  let sel = 0;

  const render = (): void => {
    const q = input.value;
    items = rank(q, all, deps);
    sel = 0;
    clear(list);

    if (!items.length) {
      list.append(
        h(
          "li",
          { class: "pal-empty" },
          q.trim() ? `Nothing matches “${q.trim()}”` : "Type to search",
        ),
      );
      return;
    }

    items.forEach((item, i) => {
      const q2 = stripPrefix(q);
      const hits = fuzzy(q2, item.title)?.hits ?? [];
      list.append(
        h(
          "li",
          {
            class: "pal-item",
            role: "option",
            "aria-selected": i === sel ? "true" : "false",
            onclick: () => choose(item),
            onpointerenter: () => select(i),
          },
          h("span", { class: "pal-kind" }, item.kind),
          h(
            "span",
            { class: "pal-main" },
            h(
              "div",
              { class: "pal-title" },
              q2 ? markHits(item.title, hits) : item.title,
            ),
            item.sub ? h("div", { class: "pal-sub" }, item.sub) : null,
          ),
          h("span", {}),
        ),
      );
    });
  };

  const select = (i: number): void => {
    const nodes = [...list.children];
    nodes[sel]?.setAttribute("aria-selected", "false");
    sel = Math.max(0, Math.min(i, items.length - 1));
    const node = nodes[sel];
    node?.setAttribute("aria-selected", "true");
    node?.scrollIntoView({ block: "nearest" });
  };

  const choose = (item: Item): void => {
    bumpFreq(item.id);
    closePalette();
    item.run();
  };

  input.addEventListener("input", render);
  input.addEventListener("keydown", (e) => {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        select(sel + 1);
        break;
      case "ArrowUp":
        e.preventDefault();
        select(sel - 1);
        break;
      case "Enter":
        e.preventDefault();
        if (items[sel]) choose(items[sel]);
        else if (input.value.trim()) {
          closePalette();
          deps.openSearch(input.value.trim());
        }
        break;
      case "Escape":
        e.preventDefault();
        closePalette();
        break;
      // A focus trap of exactly one element: Tab must not escape the dialog.
      case "Tab":
        e.preventDefault();
        break;
    }
  });

  render();
  input.focus();
  input.select();
}

export function closePalette(): void {
  el?.remove();
  scrim?.remove();
  el = null;
  scrim = null;
}

const hint = (key: string, what: string): HTMLElement =>
  h("span", {}, h("span", { class: "kbd" }, key), " ", what);

const stripPrefix = (q: string): string =>
  (MODES[q[0]] ? q.slice(1) : q).trim();

/** `#/doc/06#anchor` → `doc:06`;  `#/code/src/x.ts` → `file:src/x.ts`. */
function routeToItemId(route: string): string {
  const [path] = route.replace(/^#\//, "").split("?");
  const [view, ...tail] = path.split("#")[0].split("/");
  const id = decodeURIComponent(tail.join("/"));
  if (view === "doc") return `doc:${id}`;
  if (view === "code") return `file:${id}`;
  return `cmd:${view}`;
}

/* ── ranking ───────────────────────────────────────────────────── */

function rank(query: string, all: Item[], deps: PaletteDeps): Item[] {
  const mode = MODES[query[0]];
  const q = stripPrefix(query);
  const pool = mode ? all.filter((i) => mode.includes(i.kind)) : all;

  if (!q) {
    // Empty query: offer where you were, then the natural entry points.
    // `state.recent` holds routes (`#/doc/06`); items are keyed `doc:06`.
    const byId = new Map(all.map((i) => [i.id, i]));
    const recent = state.recent
      .flatMap((route) => {
        const item = byId.get(routeToItemId(route));
        return item ? [{ ...item, kind: "recent" }] : [];
      })
      .slice(0, 5);
    return [...recent, ...pool.filter((i) => i.weight >= 8)].slice(0, 30);
  }

  const scored = pool.flatMap((item) => {
    const m = fuzzy(q, item.title) ?? fuzzy(q, item.sub);
    if (!m) return [];
    const freq = state.freq[item.id] ?? 0;
    return [{ item, score: m.score + item.weight + Math.min(6, freq * 1.5) }];
  });

  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, 24).map((s) => s.item);

  // Full-text results fill the tail: they answer questions the titles cannot.
  if (!mode && q.length >= 3) {
    const seen = new Set(top.map((i) => i.id));
    for (const hit of deps.search.query(q, 12)) {
      const id = `sec:${hit.section.id}`;
      if (seen.has(id)) continue;
      top.push({
        id,
        kind: "text",
        title: hit.section.title,
        sub: `${hit.section.doc} · ${hit.section.path || hit.section.docTitle}`,
        weight: 0,
        run: () => deps.openDoc(hit.section.doc, hit.section.anchor),
      });
    }
  }
  return top.slice(0, 40);
}

/* ── the searchable universe ───────────────────────────────────── */

function buildItems(deps: PaletteDeps): Item[] {
  const { corpus } = deps;
  const out: Item[] = [];

  for (const c of deps.commands) {
    out.push({
      id: c.id,
      kind: "command",
      title: c.title,
      sub: c.sub ?? "",
      weight: 6,
      run: c.run,
    });
  }

  for (const doc of corpus.docs) {
    out.push({
      id: `doc:${doc.id}`,
      kind: "doc",
      title: doc.title,
      sub:
        doc.description ??
        `${doc.readMinutes} min · ${doc.words.toLocaleString()} words`,
      weight: doc.tier === "handbook" ? 10 : 7,
      run: () => deps.openDoc(doc.id),
    });

    for (const head of doc.headings) {
      if (head.depth < 2 || head.depth > 3) continue;
      out.push({
        id: `head:${doc.id}#${head.slug}`,
        kind: "heading",
        title: head.text,
        sub: `${doc.num ?? doc.id} · ${doc.title}`,
        weight: head.depth === 2 ? 3 : 1,
        run: () => deps.openDoc(doc.id, head.slug),
      });
    }
  }

  for (const e of corpus.entities) {
    out.push({
      id: `ent:${e.kind}:${e.name}`,
      kind: e.kind,
      title: e.name,
      sub: e.detail,
      // Entities outrank symbols that merely share a name. Searching "contact"
      // should offer the route `/api/contact` before the React component that
      // posts to it — the route is the thing you were looking up.
      weight: e.kind === "route" ? 12 : 9,
      run: () => deps.openDoc(e.doc, e.anchor),
    });
  }

  for (const g of corpus.glossary) {
    out.push({
      id: `glo:${g.slug}`,
      kind: "glossary",
      title: g.term,
      sub: g.text.slice(0, 90),
      weight: 4,
      run: () => deps.openDoc("glossary", g.slug),
    });
  }

  for (const f of corpus.files) {
    out.push({
      id: `file:${f.path}`,
      kind: "file",
      title: f.path,
      sub: `${f.lang} · ${f.loc} lines · ${f.citedBy.length ? `cited by ${f.citedBy.length}` : "undocumented"}`,
      weight: f.citedBy.length ? 5 : 2,
      run: () => deps.openCode(f.path),
    });

    for (const s of f.symbols) {
      out.push({
        id: `sym:${f.path}:${s.name}`,
        kind: "symbol",
        title: s.name,
        sub: `${s.kind} · ${f.path}:${s.line}`,
        weight: s.citedBy.length ? 4 : 1,
        run: () => deps.openCode(f.path, s.line),
      });
    }
  }

  return out;
}
