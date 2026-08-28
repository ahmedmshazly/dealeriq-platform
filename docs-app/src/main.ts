import "katex/dist/katex.min.css";
import "./generated/fonts.css";
import "./styles/tokens.css";
import "./styles/app.css";

import corpusJson from "./generated/corpus.json";
import type { Corpus, Doc } from "./types.js";

import { $, clear, h, toast, transition } from "./lib/dom.js";
import { current, go, href, onRoute, type Route } from "./lib/router.js";
import { Search } from "./lib/search.js";
import { pushRecent, save, setTheme, state, theme } from "./lib/store.js";

import { installSelectionMenu } from "./ui/annotate.js";
import { renderCode } from "./ui/codeview.js";
import { closeFind, findOpen, openFind, stepFind } from "./ui/find.js";
import { renderGraph, stopGraph } from "./ui/graph.js";
import {
  closeFullDiagram,
  fullDiagramOpen,
  renderDiagrams,
  watchTheme,
} from "./ui/mermaid.js";
import {
  closePalette,
  isOpen as paletteOpen,
  openPalette,
  type Command,
} from "./ui/palette.js";
import {
  bookmarkCurrent,
  renderDoc,
  runSpy,
  scrollToAnchor,
} from "./ui/reader.js";
import {
  buildRefIndex,
  hide as hidePopover,
  installReferenceLayer,
  refreshTerms,
} from "./ui/refs.js";
import {
  markActive,
  navOrder,
  refreshRing,
  renderSidebar,
} from "./ui/sidebar.js";
import { closeShortcuts, sheetOpen, toggleShortcuts } from "./ui/shortcuts.js";
import {
  renderAtlas,
  renderCheckpoints,
  renderNotes,
  renderSearch,
  renderStart,
} from "./ui/views.js";

const corpus = corpusJson as unknown as Corpus;
const search = new Search(corpus);
const index = buildRefIndex(corpus);
const byId = new Map(corpus.docs.map((d) => [d.id, d]));

/* ── shell ─────────────────────────────────────────────────────── */

const bar = h("header", { class: "bar" });
const crumb = h("nav", { class: "crumb", "aria-label": "Breadcrumb" });
const progress = h("div", { class: "bar-progress" });
const side = h("nav", { class: "side", "aria-label": "Documents" });
const main = h("main", { class: "main", tabindex: "-1" });
const rail = h("aside", { class: "rail", "aria-label": "Context" });

const app = h("div", { class: "app" }, bar, side, main, rail);

/* ── navigation ────────────────────────────────────────────────── */

const openDoc = (id: string, anchor: string | null = null): void =>
  go(href({ view: "doc", id, anchor }));
const openCode = (path: string, line?: number): void =>
  go(href({ view: "code", id: path, anchor: line ? `L${line}` : null }));
const openSearch = (q: string): void => go(href({ view: "search", query: q }));

function render(route: Route): void {
  hidePopover();
  if (findOpen()) closeFind(main);
  stopGraph();

  // Every view starts at the top. A doc that has been read before immediately
  // overrides this from `restoreScroll`; without the reset, the new view
  // inherits whatever scroll offset the previous one happened to end on.
  main.scrollTop = 0;

  const run = (): void => {
    switch (route.view) {
      case "doc": {
        const doc = byId.get(route.id);
        if (!doc) return renderStart(viewDeps);
        renderDoc(doc, route.anchor, readerDeps);
        installSelectionMenu($(".prose")!, doc.id, () =>
          refreshRing(side, doc.id),
        );
        markActive(side, doc.id);
        setCrumb(doc);
        break;
      }
      case "code":
        void renderCode(route.id, route.anchor, codeDeps);
        markActive(side, "");
        setCrumbText("Source", route.id);
        break;
      case "graph":
        renderGraph({
          corpus,
          main,
          rail,
          openDoc: (id) => openDoc(resolveNum(id)),
        });
        setCrumbText("Graph", `${corpus.stats.links} links`);
        break;
      case "atlas":
        renderAtlas(viewDeps);
        setCrumbText("Code Atlas", `${corpus.files.length} files`);
        break;
      case "notes":
        renderNotes(viewDeps);
        setCrumbText("Notes", `${state.highlights.length} highlights`);
        break;
      case "checkpoints":
        renderCheckpoints(viewDeps);
        setCrumbText("Checkpoints", `${corpus.checkpoints.length} questions`);
        break;
      case "search":
        renderSearch(route.query, viewDeps);
        setCrumbText("Search", route.query);
        break;
      default:
        renderStart(viewDeps);
        markActive(side, "");
        setCrumbText("Handbook", corpus.head);
    }
  };

  transition("doc", run);
  pushRecent(location.hash || "#/start");
  if (route.view !== "doc") progress.style.width = "0";
}

/** The graph labels nodes by `num`; routes need the doc id. */
const resolveNum = (num: string): string =>
  corpus.docs.find((d) => (d.num ?? d.id) === num)?.id ?? num;

function setCrumb(doc: Doc): void {
  clear(crumb);
  crumb.append(
    h("span", {}, doc.num ? `${doc.num}` : tierOf(doc)),
    h("span", { class: "crumb-sep" }, "›"),
    h("span", { class: "crumb-cur" }, doc.title),
  );
}
function setCrumbText(label: string, detail: string): void {
  clear(crumb);
  crumb.append(h("span", {}, label));
  if (detail) {
    crumb.append(
      h("span", { class: "crumb-sep" }, "›"),
      h("span", { class: "crumb-cur" }, detail),
    );
  }
}
const tierOf = (d: Doc): string => d.tier[0].toUpperCase() + d.tier.slice(1);

/* ── deps ──────────────────────────────────────────────────────── */

const readerDeps = { corpus, index, main, rail, openDoc, openCode };
const codeDeps = { corpus, main, rail, openDoc, openCode };
const viewDeps = {
  corpus,
  search,
  main,
  rail,
  openDoc,
  openCode,
  openPalette: () => palette(),
};

/* ── commands ──────────────────────────────────────────────────── */

const commands: Command[] = [
  { id: "cmd:start", title: "Go to start", run: () => go("#/start") },
  {
    id: "cmd:path",
    title: "Open the reading path",
    sub: "Three sessions, ~2 hours",
    run: () => openDoc("00"),
  },
  {
    id: "cmd:graph",
    title: "Open the link graph",
    sub: "29 documents, 411 links",
    run: () => go("#/graph"),
  },
  {
    id: "cmd:atlas",
    title: "Open the Code Atlas",
    sub: "Files ranked by citations",
    run: () => go("#/atlas"),
  },
  {
    id: "cmd:notes",
    title: "Open notes",
    sub: "Highlights and bookmarks",
    run: () => go("#/notes"),
  },
  {
    id: "cmd:checks",
    title: "Open checkpoints",
    sub: "Eight self-test questions",
    run: () => go("#/checkpoints"),
  },
  { id: "cmd:theme", title: "Toggle theme", run: () => toggleTheme() },
  { id: "cmd:focus", title: "Toggle focus mode", run: () => toggleFocus() },
  {
    id: "cmd:refs",
    title: "Toggle the reference layer",
    sub: "Dotted term underlines",
    run: () => toggleRefs(),
  },
  { id: "cmd:keys", title: "Keyboard shortcuts", run: () => toggleShortcuts() },
  {
    id: "cmd:export",
    title: "Export notes as markdown",
    run: () => go("#/notes"),
  },
];

const palette = (initial = ""): void =>
  openPalette(
    { corpus, search, commands, openDoc, openCode, openSearch },
    initial,
  );

/* ── chrome ────────────────────────────────────────────────────── */

function buildBar(): void {
  const themeBtn = h(
    "button",
    {
      class: "btn",
      "aria-label": "Toggle theme",
      title: "Toggle theme (t)",
      onclick: () => toggleTheme(),
    },
    theme() === "dark" ? "☾" : "☀",
  );

  bar.append(
    h(
      "button",
      {
        class: "btn",
        title: "Toggle sidebar (s)",
        "aria-label": "Toggle sidebar",
        onclick: () => toggle("side"),
      },
      "☰",
    ),
    h(
      "a",
      {
        class: "bar-brand",
        href: "#/start",
        title: "DealerIQ handbook home",
        "aria-label": "DealerIQ handbook home",
      },
      h("img", {
        class: "bar-brand-mark bar-brand-mark--light",
        src: "/mark.svg",
        alt: "",
        width: "18",
        height: "18",
      }),
      h("img", {
        class: "bar-brand-mark bar-brand-mark--dark",
        src: "/mark-on-dark.svg",
        alt: "",
        width: "18",
        height: "18",
      }),
      h("span", { class: "bar-brand-name" }, "DealerIQ"),
    ),
    crumb,
    h(
      "button",
      { class: "btn", onclick: () => palette() },
      "Search",
      h("span", { class: "kbd" }, "⌘K"),
    ),
    h(
      "button",
      { class: "btn", title: "Link graph", onclick: () => go("#/graph") },
      "Graph",
    ),
    h(
      "button",
      { class: "btn", title: "Code Atlas", onclick: () => go("#/atlas") },
      "Atlas",
    ),
    h(
      "button",
      { class: "btn", title: "Notes", onclick: () => go("#/notes") },
      "Notes",
    ),
    themeBtn,
    h(
      "button",
      {
        class: "btn",
        title: "Keyboard shortcuts (?)",
        "aria-label": "Keyboard shortcuts",
        onclick: () => toggleShortcuts(),
      },
      "?",
    ),
    progress,
  );

  window.addEventListener("themechange", () => {
    themeBtn.textContent = theme() === "dark" ? "☾" : "☀";
  });
}

function toggleTheme(): void {
  transition("root", () => setTheme(theme() === "dark" ? "light" : "dark"));
}

function toggle(which: "side" | "rail"): void {
  const on =
    which === "side"
      ? (state.sideOn = !state.sideOn)
      : (state.railOn = !state.railOn);
  app.dataset[which] = on ? "on" : "off";
  save();
}

function toggleFocus(): void {
  state.focus = !state.focus;
  app.dataset.focus = state.focus ? "on" : "off";
  save();
  toast(state.focus ? "Focus mode" : "Focus mode off");
}

function toggleRefs(): void {
  state.refs = !state.refs;
  save();
  refreshTerms();
  toast(state.refs ? "Reference layer on" : "Reference layer off");
}

/* ── resizable panes ───────────────────────────────────────────── */

function grips(): void {
  const make = (which: "side" | "rail"): HTMLElement => {
    const grip = h("div", {
      class: "grip",
      role: "separator",
      "aria-orientation": "vertical",
    });
    grip.addEventListener("pointerdown", (e) => {
      grip.classList.add("on");
      grip.setPointerCapture(e.pointerId);
      const move = (ev: PointerEvent): void => {
        const w =
          which === "side" ? ev.clientX : window.innerWidth - ev.clientX;
        const clamped = Math.max(180, Math.min(460, w));
        if (which === "side") state.sideWidth = clamped;
        else state.railWidth = clamped;
        applyWidths();
      };
      const up = (): void => {
        grip.classList.remove("on");
        grip.removeEventListener("pointermove", move);
        save();
      };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", up, { once: true });
    });
    return grip;
  };

  const a = make("side");
  const b = make("rail");
  app.append(a, b);

  const position = (): void => {
    a.style.left = `${state.sideOn ? state.sideWidth - 3 : 0}px`;
    b.style.right = `${state.railOn ? state.railWidth - 3 : 0}px`;
  };
  position();
  new ResizeObserver(position).observe(app);
  window.addEventListener("panes", position);
}

function applyWidths(): void {
  app.style.setProperty("--w-side", `${state.sideWidth}px`);
  app.style.setProperty("--w-rail", `${state.railWidth}px`);
  window.dispatchEvent(new Event("panes"));
}

/* ── keyboard ──────────────────────────────────────────────────── */

let chord: string | null = null;
let chordTimer: number | undefined;

function keys(): void {
  document.addEventListener("keydown", (e) => {
    const target = e.target as HTMLElement;
    const typing =
      /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) ||
      target.isContentEditable;
    const mod = e.metaKey || e.ctrlKey;

    if (mod && e.key.toLowerCase() === "k") {
      e.preventDefault();
      return palette();
    }
    if (mod && e.key.toLowerCase() === "p") {
      e.preventDefault();
      return palette("/");
    }
    if (mod && e.key.toLowerCase() === "f") {
      e.preventDefault();
      return openFind(main);
    }
    if (mod && e.key === "[") {
      e.preventDefault();
      return history.back();
    }
    if (mod && e.key === "]") {
      e.preventDefault();
      return history.forward();
    }

    if (e.key === "Escape") {
      if (paletteOpen()) return closePalette();
      if (sheetOpen()) return closeShortcuts();
      if (findOpen()) return closeFind(main);
      if (fullDiagramOpen()) return closeFullDiagram();
      return hidePopover();
    }

    if (typing || paletteOpen() || mod || e.altKey) return;

    if (findOpen() && (e.key === "n" || e.key === "N")) {
      e.preventDefault();
      return stepFind(e.key === "N" ? -1 : 1);
    }

    // Chords: `g` then a second key, with a 700 ms window.
    if (chord === "g") {
      clearTimeout(chordTimer);
      chord = null;
      e.preventDefault();
      if (e.key === "g") return main.scrollTo({ top: 0, behavior: "smooth" });
      if (e.key === "d") return openDoc("00");
      if (e.key === "i") return openDoc("index");
      return;
    }

    switch (e.key) {
      case "g":
        chord = "g";
        chordTimer = window.setTimeout(() => (chord = null), 700);
        e.preventDefault();
        break;
      case "G":
        e.preventDefault();
        main.scrollTo({ top: main.scrollHeight, behavior: "smooth" });
        break;
      case "j":
        main.scrollBy({ top: 90, behavior: "smooth" });
        break;
      case "k":
        main.scrollBy({ top: -90, behavior: "smooth" });
        break;
      case "d":
        main.scrollBy({ top: main.clientHeight / 2, behavior: "smooth" });
        break;
      case "u":
        main.scrollBy({ top: -main.clientHeight / 2, behavior: "smooth" });
        break;
      case "/":
        e.preventDefault();
        palette();
        break;
      case "?":
        e.preventDefault();
        toggleShortcuts();
        break;
      case "s":
        toggle("side");
        break;
      case "o":
        toggle("rail");
        break;
      case "f":
        toggleFocus();
        break;
      case "t":
        toggleTheme();
        break;
      case "r":
        toggleRefs();
        break;
      case "n":
        step(1);
        break;
      case "p":
        step(-1);
        break;
      case "b": {
        const r = current();
        if (r.view === "doc") {
          const doc = byId.get(r.id);
          if (doc) bookmarkCurrent(doc, main);
        }
        break;
      }
      default:
        if (/^[1-9]$/.test(e.key)) {
          const id = navOrder[Number(e.key) - 1];
          if (id) openDoc(id);
        }
    }
  });
}

/** `n` / `p` walk the sidebar order — which is also the handbook's own order. */
function step(by: number): void {
  const r = current();
  const at = r.view === "doc" ? navOrder.indexOf(r.id) : -1;
  const next = navOrder[Math.max(0, Math.min(navOrder.length - 1, at + by))];
  if (next && next !== r.id) openDoc(next);
}

/* ── boot ──────────────────────────────────────────────────────── */

function boot(): void {
  document.documentElement.dataset.refs = state.refs ? "on" : "off";

  const root = $("#app")!;
  root.replaceWith(app);
  app.dataset.side = state.sideOn ? "on" : "off";
  app.dataset.rail = state.railOn ? "on" : "off";
  app.dataset.focus = state.focus ? "on" : "off";
  applyWidths();

  buildBar();
  grips();
  keys();

  renderSidebar({ corpus, side, openDoc }, "");
  installReferenceLayer(app, { index, openCode, openDoc });

  window.addEventListener("docprogress", (e) => {
    refreshRing(side, (e as CustomEvent<string>).detail);
  });

  watchTheme(() => {
    const r = current();
    if (r.view === "doc") {
      const doc = byId.get(r.id);
      const prose = $(".prose");
      if (doc && prose) void renderDiagrams(prose as HTMLElement, doc.mermaid);
    }
  });

  onRoute(render);

  if (!location.hash) go(state.lastRoute, true);
  render(current());
  runSpy();

  const bootEl = $(".boot");
  bootEl?.classList.add("out");
  setTimeout(() => bootEl?.remove(), 420);
  app.setAttribute("aria-busy", "false");
}

// Anchors inside prose are plain `#slug` links; the router must not treat them
// as routes. Intercept them before `hashchange` ever fires.
document.addEventListener("click", (e) => {
  const a = (e.target as HTMLElement).closest<HTMLAnchorElement>(
    'a[href^="#"]',
  );
  if (!a || a.classList.contains("hd-anchor")) return;
  const hash = a.getAttribute("href")!;
  if (hash.startsWith("#/")) return;
  e.preventDefault();
  scrollToAnchor(hash.slice(1), main);
});

boot();
