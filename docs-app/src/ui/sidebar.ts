import type { Corpus, Doc, Tier } from "../types.js";
import { clear, h, svg } from "../lib/dom.js";
import { READ_AT, state } from "../lib/store.js";

const GROUPS: { tier: Tier; label: string }[] = [
  { tier: "handbook", label: "Architecture" },
  { tier: "meta", label: "Reference" },
  { tier: "stub", label: "Superseded" },
  { tier: "background", label: "Background" },
];

export interface SidebarDeps {
  corpus: Corpus;
  side: HTMLElement;
  openDoc: (id: string) => void;
}

/** Doc ids in sidebar order - `1`-`9` jump here, and `n`/`p` walk it. */
export let navOrder: string[] = [];

export function renderSidebar(deps: SidebarDeps, activeId: string): void {
  const { corpus, side } = deps;
  clear(side);
  navOrder = [];

  for (const { tier, label } of GROUPS) {
    const docs = corpus.docs.filter((d) => d.tier === tier);
    if (!docs.length) continue;

    const group = h(
      "div",
      { class: "side-group" },
      h("div", { class: "side-label" }, label),
    );

    for (const doc of docs) {
      navOrder.push(doc.id);
      group.append(item(doc, doc.id === activeId, deps));
    }
    side.append(group);
  }
}

function item(doc: Doc, active: boolean, deps: SidebarDeps): HTMLElement {
  const el = h(
    "button",
    {
      class: "side-item",
      "data-doc": doc.id,
      "aria-current": active ? "page" : null,
      title: doc.description ?? doc.title,
      onclick: () => deps.openDoc(doc.id),
    },
    ring(doc.id),
    h("span", { class: "side-name" }, cleanTitle(doc)),
    h("span", { class: "side-num" }, doc.num ?? `${doc.readMinutes}m`),
  );
  return el;
}

/** Titles already carry their number (`06 · Data Model`); the rail shows it separately. */
const cleanTitle = (doc: Doc): string =>
  doc.title.replace(/^\d{2}[a-z]?\s*·\s*/, "");

/**
 * A progress ring, not a checkbox. It answers "how far in am I" at a glance and
 * turns green only once the document is genuinely finished.
 */
function ring(docId: string): SVGElement {
  const pct = state.progress[docId] ?? 0;
  const r = 5.5;
  const c = 2 * Math.PI * r;

  const el = svg("svg", {
    class: "ring",
    viewBox: "0 0 14 14",
    "data-doc": docId,
    "aria-hidden": "true",
  });
  if (pct >= READ_AT) el.setAttribute("data-done", "1");

  el.append(
    svg("circle", {
      class: "ring-bg",
      cx: 7,
      cy: 7,
      r,
      fill: "none",
      "stroke-width": 1.5,
    }),
    svg("circle", {
      class: "ring-fg",
      cx: 7,
      cy: 7,
      r,
      fill: "none",
      "stroke-width": 1.5,
      "stroke-linecap": "round",
      "stroke-dasharray": c,
      "stroke-dashoffset": c * (1 - Math.min(1, pct)),
    }),
  );
  return el;
}

/** Repaint a single ring without rebuilding the tree - called on every scroll tick. */
export function refreshRing(side: HTMLElement, docId: string): void {
  const el = side.querySelector<SVGElement>(`svg.ring[data-doc="${docId}"]`);
  const fg = el?.querySelector<SVGCircleElement>(".ring-fg");
  if (!el || !fg) return;

  const pct = Math.min(1, state.progress[docId] ?? 0);
  const c = 2 * Math.PI * 5.5;
  fg.setAttribute("stroke-dashoffset", String(c * (1 - pct)));
  if (pct >= READ_AT) el.setAttribute("data-done", "1");
  else el.removeAttribute("data-done");
}

export function markActive(side: HTMLElement, docId: string): void {
  for (const el of side.querySelectorAll<HTMLElement>(".side-item")) {
    if (el.dataset.doc === docId) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  }
  side
    .querySelector<HTMLElement>(`.side-item[data-doc="${docId}"]`)
    ?.scrollIntoView({ block: "nearest" });
}
