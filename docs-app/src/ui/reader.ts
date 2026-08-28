import type { Corpus, Doc } from "../types.js";
import { $, $$, clear, debounce, h, toast } from "../lib/dom.js";
import {
  recordProgress,
  state,
  hasBookmark,
  toggleBookmark,
} from "../lib/store.js";
import { renderDiagrams } from "./mermaid.js";
import { applyHighlights } from "./annotate.js";
import { decorateTerms, type RefIndex } from "./refs.js";

export interface ReaderDeps {
  corpus: Corpus;
  index: RefIndex;
  main: HTMLElement;
  rail: HTMLElement;
  openDoc: (doc: string, anchor?: string | null) => void;
  openCode: (path: string, line?: number) => void;
}

let spy: (() => void) | null = null;

export function renderDoc(
  doc: Doc,
  anchor: string | null,
  deps: ReaderDeps,
): void {
  const { corpus, main, rail } = deps;

  clear(main);
  clear(rail);
  spy = null;

  const prose = h("article", { class: "prose", id: "prose", html: doc.html });
  main.append(h("div", { class: "doc" }, header(doc, corpus), prose));

  // Order matters. Terms are wrapped before highlights so a highlight can span a
  // decorated term; diagrams render last because they are the only async step.
  decorateTerms(prose, deps.index, doc.id);
  applyHighlights(prose, doc.id);
  wireProse(prose, deps);

  rail.append(outline(doc, main));
  if (doc.citedFiles.length) rail.append(citedFiles(doc, deps));
  if (doc.backlinks.length) rail.append(backlinks(doc, deps));

  void renderDiagrams(prose, doc.mermaid);

  restoreScroll(doc, anchor, main);
  installSpy(doc, main, rail);
}

/* ── header ────────────────────────────────────────────────────── */

function header(doc: Doc, corpus: Corpus): HTMLElement {
  const kicker = h(
    "div",
    { class: "doc-kicker" },
    h(
      "span",
      {},
      doc.num ? `${doc.num} · ${tierName(doc.tier)}` : tierName(doc.tier),
    ),
    h("span", {}, "·"),
    h("span", {}, `${doc.readMinutes} min read`),
    h("span", {}, "·"),
    h("span", {}, `${doc.words.toLocaleString()} words`),
    staleness(doc, corpus.head),
  );

  return h(
    "header",
    { class: "doc-head" },
    kicker,
    h("h1", { class: "doc-title" }, doc.title),
    doc.description ? h("p", { class: "doc-desc" }, doc.description) : null,
  );
}

const tierName = (t: Doc["tier"]): string =>
  ({
    handbook: "Architecture",
    meta: "Reference",
    stub: "Superseded",
    background: "Background",
  })[t];

/**
 * `last-verified: 2026-07-09 (4f24c86)` is a promise about a moment. Compare it
 * to HEAD and say plainly whether the promise still holds.
 */
function staleness(doc: Doc, head: string): HTMLElement | null {
  if (!doc.lastVerified) return null;
  const behind = doc.commitsBehind;

  if (behind === 0) {
    return h(
      "span",
      {
        class: "chip chip-ok",
        title: `Verified at ${doc.lastVerified.sha}, which is HEAD (${head})`,
      },
      h("span", { class: "chip-dot" }),
      "current",
    );
  }
  if (behind === null) {
    return h(
      "span",
      { class: "chip", title: "Verification commit not found in history" },
      "unverifiable",
    );
  }
  return h(
    "span",
    {
      class: "chip chip-warn",
      title: `docs/ has changed ${behind} time(s) since ${doc.lastVerified.sha}`,
    },
    h("span", { class: "chip-dot" }),
    `${behind} behind`,
  );
}

/* ── prose wiring ──────────────────────────────────────────────── */

function wireProse(prose: HTMLElement, deps: ReaderDeps): void {
  prose.addEventListener("click", (e) => {
    const el = e.target as HTMLElement;

    const copy = el.closest<HTMLButtonElement>("[data-copy]");
    if (copy) {
      const code = copy.parentElement?.querySelector("code")?.textContent ?? "";
      void navigator.clipboard.writeText(code).then(() => {
        copy.dataset.done = "";
        copy.textContent = "Copied";
        setTimeout(() => {
          delete copy.dataset.done;
          copy.textContent = "Copy";
        }, 1400);
      });
      return;
    }

    const anchorLink = el.closest<HTMLAnchorElement>("a.hd-anchor");
    if (anchorLink) {
      e.preventDefault();
      const id = anchorLink.getAttribute("href")!.slice(1);
      const url = `${location.href.split("#")[0]}${location.hash.split("#").slice(0, 2).join("#")}#${id}`;
      void navigator.clipboard.writeText(url).then(() => toast("Link copied"));
      return;
    }

    const docLink = el.closest<HTMLAnchorElement>("a.lk-doc");
    if (docLink) {
      e.preventDefault();
      deps.openDoc(docLink.dataset.doc!, docLink.dataset.anchor ?? null);
      return;
    }

    const fileRef = el.closest<HTMLElement>('[data-ref="file"]');
    if (fileRef) {
      e.preventDefault();
      deps.openCode(fileRef.dataset.refValue!);
      return;
    }

    const symbolRef = el.closest<HTMLElement>('[data-ref="symbol"]');
    if (symbolRef) {
      const defs = deps.index.symbols.get(symbolRef.dataset.refValue!);
      if (defs?.length) {
        e.preventDefault();
        deps.openCode(defs[0].file, defs[0].line);
      }
      return;
    }

    const jump = el.closest<HTMLAnchorElement>("a.lk-jump");
    if (jump) {
      e.preventDefault();
      scrollToAnchor(jump.dataset.jump!, deps.main);
    }
  });

  // Keyboard parity: a reference span is `tabindex=0` and must activate.
  prose.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const t = e.target as HTMLElement;
    if (t.matches("[data-ref], [data-term]")) {
      e.preventDefault();
      t.click();
    }
  });
}

/* ── outline + scroll spy ──────────────────────────────────────── */

function outline(doc: Doc, main: HTMLElement): HTMLElement {
  const items = doc.headings.filter((x) => x.depth >= 2 && x.depth <= 4);
  const nav = h("nav", { class: "outline", "aria-label": "On this page" });

  const mark = h("div", { class: "outline-mark" });
  nav.append(mark);

  for (const head of items) {
    nav.append(
      h(
        "a",
        {
          href: `#${head.slug}`,
          "data-depth": head.depth,
          "data-slug": head.slug,
          onclick: (e: Event) => {
            e.preventDefault();
            scrollToAnchor(head.slug, main);
          },
        },
        head.text,
      ),
    );
  }

  return h(
    "section",
    { class: "rail-section" },
    h("h2", { class: "rail-label" }, `On this page · ${items.length}`),
    nav,
  );
}

function installSpy(doc: Doc, main: HTMLElement, rail: HTMLElement): void {
  const links = new Map(
    $$<HTMLAnchorElement>("[data-slug]", rail).map((a) => [a.dataset.slug!, a]),
  );
  const heads = $$<HTMLElement>(".hd", main).filter((el) => links.has(el.id));
  const mark = $<HTMLElement>(".outline-mark", rail);
  if (!heads.length || !mark) return;

  let active = "";

  const update = (): void => {
    const top = main.scrollTop;
    const height = main.scrollHeight - main.clientHeight;
    recordProgress(doc.id, height > 0 ? top / height : 1);

    const bar = $<HTMLElement>(".bar-progress");
    if (bar)
      bar.style.width = `${height > 0 ? Math.min(100, (top / height) * 100) : 100}%`;

    // The active heading is the last one whose top has passed a line a third of
    // the way down the viewport — the place the eye actually reads.
    const line = main.getBoundingClientRect().top + main.clientHeight * 0.32;
    let current = heads[0];
    for (const el of heads) {
      if (el.getBoundingClientRect().top <= line) current = el;
      else break;
    }
    if (current.id === active) return;
    active = current.id;

    for (const a of links.values()) a.classList.remove("on");
    const link = links.get(active);
    if (!link) return;
    link.classList.add("on");
    mark.style.top = `${link.offsetTop}px`;
    mark.style.height = `${link.offsetHeight}px`;
  };

  spy = update;
  main.addEventListener("scroll", update, { passive: true });
  main.addEventListener("scroll", persistScroll(doc, main), { passive: true });
  requestAnimationFrame(update);
}

export const runSpy = (): void => spy?.();

const persistScroll = (doc: Doc, main: HTMLElement) =>
  debounce(() => {
    state.scroll[doc.id] = main.scrollTop;
  }, 400);

function restoreScroll(
  doc: Doc,
  anchor: string | null,
  main: HTMLElement,
): void {
  if (anchor) {
    // Wait a frame: the prose has just been inserted and has no layout yet.
    requestAnimationFrame(() => scrollToAnchor(anchor, main, "auto"));
    return;
  }
  const saved = state.scroll[doc.id];
  if (saved)
    requestAnimationFrame(() =>
      main.scrollTo({ top: saved, behavior: "auto" }),
    );
}

export function scrollToAnchor(
  slug: string,
  main: HTMLElement,
  behavior: ScrollBehavior = "smooth",
): void {
  const el = document.getElementById(slug);
  if (!el) return;
  const top =
    el.getBoundingClientRect().top -
    main.getBoundingClientRect().top +
    main.scrollTop -
    16;
  main.scrollTo({ top, behavior });
  el.focus({ preventScroll: true });
  flash(el);
}

function flash(el: HTMLElement): void {
  el.animate(
    [
      { background: "rgba(var(--accent-rgb), 0.16)" },
      { background: "transparent" },
    ],
    { duration: 900, easing: "cubic-bezier(0.16,1,0.3,1)" },
  );
}

/* ── rail sections ─────────────────────────────────────────────── */

function citedFiles(doc: Doc, deps: ReaderDeps): HTMLElement {
  const section = h(
    "section",
    { class: "rail-section" },
    h("h2", { class: "rail-label" }, `Code cited · ${doc.citedFiles.length}`),
  );

  for (const path of [...doc.citedFiles].sort()) {
    const file = deps.index.files.get(path);
    section.append(
      h(
        "button",
        {
          class: "citelink path",
          title: path,
          onclick: () => deps.openCode(path),
        },
        h("span", { style: "color:var(--read)" }, path),
        h("span", {}, file ? `${file.loc}` : ""),
      ),
    );
  }
  return section;
}

/**
 * "Referenced by" — the direction the corpus could never be read in. 411 links
 * point forward; this is the only place they point back.
 */
function backlinks(doc: Doc, deps: ReaderDeps): HTMLElement {
  const seen = new Set<string>();
  const unique = doc.backlinks.filter((b) => {
    // 00-reading-path links to 06 five times from one table. Show the section
    // once; the count in the label already says how much it leans on this doc.
    const k = `${b.from}:${b.fromAnchor}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });

  const section = h(
    "section",
    { class: "rail-section" },
    h("h2", { class: "rail-label" }, `Referenced by · ${unique.length}`),
  );

  for (const b of unique.slice(0, 24)) {
    section.append(
      h(
        "button",
        {
          class: "backlink",
          title: b.anchor ? `Links to #${b.anchor}` : undefined,
          onclick: () => deps.openDoc(b.from, b.fromAnchor),
        },
        b.context,
      ),
    );
  }
  return section;
}

/* ── bookmarks ─────────────────────────────────────────────────── */

export function bookmarkCurrent(doc: Doc, main: HTMLElement): void {
  const heads = $$<HTMLElement>(".hd", main);
  const line = main.getBoundingClientRect().top + main.clientHeight * 0.32;
  let current = heads[0];
  for (const el of heads) {
    if (el.getBoundingClientRect().top <= line) current = el;
    else break;
  }
  const anchor = current?.id ?? "";
  const title = current?.textContent?.replace(/#$/, "") ?? doc.title;
  const added = toggleBookmark(doc.id, anchor, title);
  toast(
    added ? `Bookmarked ${doc.num ?? doc.id} § ${title}` : "Bookmark removed",
  );
}

export const isBookmarked = hasBookmark;
