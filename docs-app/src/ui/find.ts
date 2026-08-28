import { $$, h } from "../lib/dom.js";

/**
 * In-page find (⌘F), reimplemented rather than deferred to the browser.
 *
 * The browser's own find would work - but it cannot tell the outline which
 * match is active, cannot skip the code gutters, and vanishes the moment the
 * pane re-renders. Owning it costs sixty lines and makes `n`/`N` behave the way
 * they do in an editor.
 */
let bar: HTMLElement | null = null;
let marks: HTMLElement[] = [];
let at = -1;

export const findOpen = (): boolean => bar !== null;

export function openFind(main: HTMLElement): void {
  if (bar) {
    bar.querySelector("input")?.focus();
    return;
  }

  const input = h("input", {
    type: "text",
    placeholder: "Find in page",
    "aria-label": "Find in page",
    spellcheck: "false",
  }) as HTMLInputElement;

  const count = h("div", { class: "find-n", role: "status" }, "");

  const step = (by: number): void => {
    if (!marks.length) return;
    marks[at]?.classList.remove("on");
    at = (at + by + marks.length) % marks.length;
    const m = marks[at];
    m.classList.add("on");
    m.scrollIntoView({ block: "center", behavior: "smooth" });
    count.textContent = `${at + 1}/${marks.length}`;
  };

  const run = (): void => {
    clearMarks(main);
    const q = input.value.trim();
    at = -1;
    if (q.length < 2) {
      count.textContent = "";
      return;
    }
    marks = highlight(main, q);
    count.textContent = marks.length ? `0/${marks.length}` : "none";
    if (marks.length) step(1);
  };

  input.addEventListener("input", run);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      step(e.shiftKey ? -1 : 1);
    } else if (e.key === "Escape") {
      e.preventDefault();
      closeFind(main);
    }
  });

  bar = h(
    "div",
    { class: "find", role: "search" },
    input,
    count,
    h(
      "button",
      {
        class: "mermaid-btn",
        "aria-label": "Previous match",
        onclick: () => step(-1),
      },
      "↑",
    ),
    h(
      "button",
      {
        class: "mermaid-btn",
        "aria-label": "Next match",
        onclick: () => step(1),
      },
      "↓",
    ),
    h(
      "button",
      {
        class: "mermaid-btn",
        "aria-label": "Close find",
        onclick: () => closeFind(main),
      },
      "✕",
    ),
  );

  document.body.append(bar);
  input.focus();
}

export function closeFind(main: HTMLElement): void {
  clearMarks(main);
  bar?.remove();
  bar = null;
  marks = [];
  at = -1;
}

export function stepFind(by: number): void {
  bar
    ?.querySelector("input")
    ?.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", shiftKey: by < 0 }),
    );
}

function clearMarks(main: HTMLElement): void {
  for (const m of $$("mark.find-hit", main)) {
    const text = document.createTextNode(m.textContent ?? "");
    m.replaceWith(text);
    text.parentNode?.normalize();
  }
}

const SKIP = new Set(["SCRIPT", "STYLE", "MARK"]);

function highlight(root: HTMLElement, query: string): HTMLElement[] {
  const needle = query.toLowerCase();
  const out: HTMLElement[] = [];

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) =>
      n.parentElement &&
      !SKIP.has(n.parentElement.tagName) &&
      (n.nodeValue ?? "").toLowerCase().includes(needle)
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT,
  });

  const targets: Text[] = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode())
    targets.push(n as Text);

  for (const node of targets) {
    let rest: Text | null = node;
    for (;;) {
      const idx = (rest.nodeValue ?? "").toLowerCase().indexOf(needle);
      if (idx < 0 || !rest.nodeValue) break;
      const hit: Text = rest.splitText(idx);
      rest = hit.splitText(needle.length);
      const mark = h("mark", { class: "find-hit" });
      hit.replaceWith(mark);
      mark.append(hit);
      out.push(mark);
    }
  }
  return out;
}
