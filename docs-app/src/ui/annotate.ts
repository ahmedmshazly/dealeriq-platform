import { h, toast } from "../lib/dom.js";
import { state, save, type Highlight } from "../lib/store.js";

/**
 * Highlights and margin notes, anchored by text quote.
 *
 * A character offset is the obvious way to remember "the reader highlighted
 * characters 4,120–4,180 of document 06". It is also wrong the moment anyone
 * edits a paragraph above, because every offset below silently shifts and the
 * highlight reappears in the middle of an unrelated sentence.
 *
 * So we store the quote itself plus ~32 characters of context on each side — the
 * W3C annotation model's `TextQuoteSelector`. Re-anchoring searches for the
 * quote, disambiguating by context. If the sentence is gone, the highlight is
 * reported as orphaned rather than reattached to the wrong place. Being honest
 * about a lost annotation beats being confidently wrong about its location.
 */
const CONTEXT = 32;

const uid = (): string => Math.random().toString(36).slice(2, 10);

/**
 * Prose text nodes only.
 *
 * `element.textContent` is not the text of a document — it is the text of every
 * node inside it, and Mermaid injects a `<style>` block into each rendered
 * figure. Left unfiltered, an anchor's prefix comes back as
 * `(16, 40, 26)!important;}`. Every function that indexes characters must walk
 * with this same filter, or their offsets disagree.
 */
const OPAQUE = new Set(["STYLE", "SCRIPT", "svg"]);

function textWalker(root: Node): TreeWalker {
  return document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      for (let el = node.parentElement; el; el = el.parentElement) {
        if (OPAQUE.has(el.tagName)) return NodeFilter.FILTER_REJECT;
        if (el === root) break;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
}

export function proseText(root: HTMLElement): string {
  const walker = textWalker(root);
  let out = "";
  for (let n = walker.nextNode(); n; n = walker.nextNode())
    out += n.nodeValue ?? "";
  return out;
}

/**
 * The first / last text node at or within `node`.
 *
 * A `TreeWalker` rooted at a text node returns `null` from `nextNode()` — it
 * only ever descends, and a text node has no children. So the root must be
 * handled before the walk, not by it.
 */
function firstTextIn(node: Node): Text | null {
  if (node.nodeType === Node.TEXT_NODE) return node as Text;
  return textWalker(node).nextNode() as Text | null;
}

function lastTextIn(node: Node): Text | null {
  if (node.nodeType === Node.TEXT_NODE) return node as Text;
  const walker = textWalker(node);
  let last: Text | null = null;
  for (let n = walker.nextNode(); n; n = walker.nextNode()) last = n as Text;
  return last;
}

/** Resolve an element boundary point onto the text node it really sits at. */
function toTextPoint(
  node: Node,
  offset: number,
): { node: Text; offset: number } | null {
  if (node.nodeType === Node.TEXT_NODE) return { node: node as Text, offset };

  const child = node.childNodes[offset];
  if (child) {
    const first = firstTextIn(child);
    return first ? { node: first, offset: 0 } : null;
  }

  // End boundary past the last child: take the end of the last text node.
  const last = lastTextIn(node);
  return last ? { node: last, offset: last.length } : null;
}

/* ── capture ───────────────────────────────────────────────────── */

export function captureSelection(
  prose: HTMLElement,
  docId: string,
): Omit<Highlight, "color" | "note"> | null {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || sel.rangeCount === 0) return null;

  const range = sel.getRangeAt(0);
  if (!prose.contains(range.commonAncestorContainer)) return null;

  const quote = range.toString().trim();
  if (quote.length < 3 || quote.length > 600) return null;

  const full = proseText(prose);
  const start = offsetOf(prose, range.startContainer, range.startOffset);

  // A selection inside a Mermaid label lives in a `foreignObject`, which the
  // prose walker rejects — so it has no offset in prose space. Refusing is the
  // only honest answer: offset 0 would anchor the note to the document's title.
  if (start < 0 || full.slice(start, start + quote.length) !== quote)
    return null;

  return {
    id: uid(),
    doc: docId,
    anchor: nearestHeading(range.startContainer),
    quote,
    prefix: full.slice(Math.max(0, start - CONTEXT), start),
    suffix: full.slice(start + quote.length, start + quote.length + CONTEXT),
    created: Date.now(),
  };
}

/**
 * Character offset of a boundary point within `root`, in filtered-prose space.
 *
 * Matching text nodes on identity looks sufficient and is not: a Range's
 * `startContainer` is an *element* whenever the selection begins at an element
 * boundary — which is exactly what a double-click, a triple-click or
 * `selectNodeContents` produces. The walker then never matches, the function
 * falls through to the total length, and the annotation records the tail of the
 * document as its prefix. So resolve the boundary onto a text node first.
 */
function offsetOf(root: HTMLElement, node: Node, offset: number): number {
  const point = toTextPoint(node, offset);
  if (!point) return -1;

  const walker = textWalker(root);
  let total = 0;
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n === point.node) return total + point.offset;
    total += n.nodeValue?.length ?? 0;
  }
  // Not reachable through the prose walker at all. `-1`, never `0`: a silently
  // wrong offset is far worse than a refused annotation.
  return -1;
}

function nearestHeading(node: Node): string | null {
  let el: Element | null =
    node.nodeType === 1 ? (node as Element) : node.parentElement;
  while (el) {
    const prev = el.previousElementSibling;
    if (prev && /^H[2-4]$/.test(prev.tagName)) return prev.id;
    el = el.previousElementSibling ?? el.parentElement;
    if (el?.classList.contains("prose")) break;
  }
  return null;
}

/* ── re-anchor & paint ─────────────────────────────────────────── */

export function applyHighlights(prose: HTMLElement, docId: string): void {
  const mine = state.highlights.filter((x) => x.doc === docId);
  for (const hl of mine) paint(prose, hl);
}

function paint(prose: HTMLElement, hl: Highlight): boolean {
  const full = proseText(prose);

  // Prefer the occurrence whose surrounding context matches; fall back to the
  // first occurrence of the quote alone.
  let at = full.indexOf(hl.prefix + hl.quote + hl.suffix);
  if (at >= 0) at += hl.prefix.length;
  else at = full.indexOf(hl.quote);
  if (at < 0) return false;

  const range = rangeAt(prose, at, hl.quote.length);
  if (!range) return false;

  try {
    // `surroundContents` throws when the range straddles element boundaries
    // (a highlight spanning a `<strong>`), so wrap each text node separately.
    for (const part of textNodesIn(range)) {
      const mark = h("span", {
        class: `hl hl-${hl.color}${hl.note ? " hl-note" : ""}`,
        "data-hl": hl.id,
        title: hl.note || undefined,
      });
      part.replaceWith(mark);
      mark.append(part);
    }
    return true;
  } catch {
    return false;
  }
}

/** Is this highlight still findable in the current text of its document? */
export const isOrphan = (hl: Highlight, text: string): boolean =>
  !text.includes(hl.quote);

function rangeAt(
  root: HTMLElement,
  start: number,
  length: number,
): Range | null {
  const walker = textWalker(root);
  const range = document.createRange();
  let total = 0;
  let began = false;

  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const len = n.nodeValue?.length ?? 0;
    if (!began && total + len > start) {
      range.setStart(n, start - total);
      began = true;
    }
    if (began && total + len >= start + length) {
      range.setEnd(n, start + length - total);
      return range;
    }
    total += len;
  }
  return null;
}

/**
 * The text nodes a range covers, split so each one is entirely inside it.
 *
 * The offsets must be read *before* the first `splitText`. Splitting a text node
 * mutates any live Range that points into it — Chrome moves the boundaries onto
 * the new node, jsdom leaves them alone — so reading `range.endOffset` after the
 * split gives a different answer in each. That is how a highlight of `TARGET`
 * ends up painting `T`.
 */
function textNodesIn(range: Range): Text[] {
  const root = range.commonAncestorContainer;
  const startOffset = range.startOffset;
  const endOffset = range.endOffset;
  const startNode = range.startContainer;
  const endNode = range.endContainer;

  if (root.nodeType === Node.TEXT_NODE) {
    const tail = (root as Text).splitText(startOffset);
    tail.splitText(endOffset - startOffset);
    return [tail];
  }

  const out: Text[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (range.intersectsNode(n)) out.push(n as Text);
  }
  if (!out.length) return out;

  // Trim the tail before the head: splitting the last node cannot disturb the
  // first one's offsets, but the reverse is true when they are the same node.
  const last = out[out.length - 1];
  if (last === endNode && endOffset < last.length) last.splitText(endOffset);

  const first = out[0];
  if (first === startNode && startOffset > 0)
    out[0] = first.splitText(startOffset);

  return out;
}

/* ── selection menu ────────────────────────────────────────────── */

let menu: HTMLElement | null = null;

export function installSelectionMenu(
  prose: HTMLElement,
  docId: string,
  onChange: () => void,
): void {
  const close = (): void => {
    menu?.remove();
    menu = null;
  };

  prose.addEventListener("pointerup", () => {
    setTimeout(() => {
      close();
      const draft = captureSelection(prose, docId);
      if (!draft) return;

      const rect = window.getSelection()?.getRangeAt(0).getBoundingClientRect();
      if (!rect) return;

      menu = h(
        "div",
        {
          class: "sel-menu",
          role: "toolbar",
          "aria-label": "Annotate selection",
        },
        ...([1, 2, 3, 4] as const).map((color) =>
          h("button", {
            class: `swatch hl-${color}`,
            "aria-label": `Highlight, colour ${color}`,
            onclick: () => {
              add({ ...draft, color, note: "" }, prose, onChange);
              close();
            },
          }),
        ),
        h(
          "button",
          {
            class: "swatch",
            style: "display:grid;place-items:center;font-size:11px",
            "aria-label": "Highlight with a note",
            onclick: () => {
              const note = prompt("Note")?.trim();
              if (note) add({ ...draft, color: 3, note }, prose, onChange);
              close();
            },
          },
          "✎",
        ),
      );
      document.body.append(menu);
      menu.style.top = `${Math.max(8, rect.top - 44)}px`;
      menu.style.left = `${Math.max(8, rect.left + rect.width / 2 - 70)}px`;
    }, 10);
  });

  prose.addEventListener("pointerdown", close);
  document.addEventListener("keydown", (e) => e.key === "Escape" && close());
}

function add(hl: Highlight, prose: HTMLElement, onChange: () => void): void {
  state.highlights.unshift(hl);
  save();
  window.getSelection()?.removeAllRanges();
  if (!paint(prose, hl)) toast("Saved, but could not paint the highlight");
  onChange();
}

export function removeHighlight(id: string): void {
  const i = state.highlights.findIndex((x) => x.id === id);
  if (i < 0) return;
  state.highlights.splice(i, 1);
  save();
  for (const el of document.querySelectorAll(`[data-hl="${id}"]`)) {
    el.replaceWith(...el.childNodes);
  }
}

/* ── export ────────────────────────────────────────────────────── */

export function exportMarkdown(titleOf: (doc: string) => string): string {
  const byDoc = new Map<string, Highlight[]>();
  for (const hl of state.highlights) {
    const list = byDoc.get(hl.doc) ?? [];
    list.push(hl);
    byDoc.set(hl.doc, list);
  }

  const lines = [
    "# Handbook notes",
    "",
    `_Exported ${new Date().toISOString().slice(0, 10)}_`,
    "",
  ];

  for (const [doc, items] of byDoc) {
    lines.push(`## ${titleOf(doc)}`, "");
    for (const hl of items.sort((a, b) => a.created - b.created)) {
      lines.push(`> ${hl.quote.replace(/\n+/g, " ")}`);
      if (hl.note) lines.push("", `**Note:** ${hl.note}`);
      if (hl.anchor) lines.push("", `<sub>§ ${hl.anchor}</sub>`);
      lines.push("");
    }
  }

  if (state.bookmarks.length) {
    lines.push("## Bookmarks", "");
    for (const b of state.bookmarks)
      lines.push(`- ${titleOf(b.doc)} § ${b.title}`);
  }
  return lines.join("\n");
}
