// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { applyHighlights, captureSelection, proseText } from "./annotate.js";
import { state } from "../lib/store.js";

const build = (html: string): HTMLElement => {
  document.body.innerHTML = `<div class="prose">${html}</div>`;
  return document.querySelector<HTMLElement>(".prose")!;
};

/** Select `text` inside `prose` using an *element* boundary — the hard case. */
function selectContents(el: Element): void {
  const range = document.createRange();
  range.selectNodeContents(el);
  const sel = window.getSelection()!;
  sel.removeAllRanges();
  sel.addRange(range);
}

beforeEach(() => {
  state.highlights = [];
});

describe("proseText", () => {
  /**
   * Mermaid injects a `<style>` element into every rendered figure. `textContent`
   * happily returns its CSS, which then lands in an annotation's prefix.
   */
  it("ignores style, script and svg content", () => {
    const prose = build(
      `<p>Alpha</p><figure><style>.x{fill:rgb(16,40,26)!important}</style><svg><text>Browser</text></svg></figure><p>Beta</p>`,
    );
    expect(proseText(prose)).toBe("AlphaBeta");
    expect(proseText(prose)).not.toContain("important");
  });
});

describe("captureSelection", () => {
  it("records the text that precedes the quote, not the end of the document", () => {
    const prose = build(
      `<p>First paragraph.</p><p>Second paragraph here.</p><p>Third.</p>`,
    );
    selectContents(prose.children[1]);

    const hl = captureSelection(prose, "07");
    expect(hl).not.toBeNull();
    expect(hl!.quote).toBe("Second paragraph here.");
    expect(hl!.prefix).toBe("First paragraph.");
    expect(hl!.suffix).toBe("Third.");
  });

  /**
   * A `TreeWalker` rooted at a text node returns null from `nextNode()` — it only
   * descends. Resolving an element boundary must handle the root before walking.
   */
  it("resolves an element boundary whose first child is a text node", () => {
    const prose = build(`<p>Only paragraph text.</p>`);
    selectContents(prose.children[0]);
    expect(captureSelection(prose, "07")?.quote).toBe("Only paragraph text.");
  });

  /** Refusing beats anchoring the note to the document title. */
  it("refuses a selection that has no offset in prose space", () => {
    const prose = build(
      `<p>Alpha</p><figure><svg><text>Browser</text></svg></figure>`,
    );
    selectContents(prose.querySelector("text")!);
    expect(captureSelection(prose, "07")).toBeNull();
  });

  it("ignores a collapsed selection", () => {
    const prose = build(`<p>Alpha</p>`);
    window.getSelection()!.removeAllRanges();
    expect(captureSelection(prose, "07")).toBeNull();
  });
});

describe("text-quote re-anchoring", () => {
  const HTML = `<h2 id="s">S</h2><p>The read path never authenticates.</p><p>Tail.</p>`;

  it("survives an edit that shifts every character offset", () => {
    const prose = build(HTML);
    selectContents(prose.children[1]);
    const hl = {
      ...captureSelection(prose, "07")!,
      color: 1 as const,
      note: "",
    };
    state.highlights = [hl];

    // Insert a paragraph *above* it. Any offset-based anchor now points at the
    // wrong sentence; a quote-based one still finds its text.
    const edited = build(
      `<p>A brand new opening paragraph was added.</p>${HTML}`,
    );
    applyHighlights(edited, "07");

    const marks = edited.querySelectorAll(".hl");
    expect(marks.length).toBeGreaterThan(0);
    expect([...marks].map((m) => m.textContent).join("")).toBe(
      "The read path never authenticates.",
    );
  });

  it("paints nothing when the quote is gone, rather than guessing", () => {
    const prose = build(HTML);
    selectContents(prose.children[1]);
    state.highlights = [
      { ...captureSelection(prose, "07")!, color: 1, note: "" },
    ];

    const rewritten = build(
      `<h2 id="s">S</h2><p>Completely different prose now.</p>`,
    );
    applyHighlights(rewritten, "07");
    expect(rewritten.querySelectorAll(".hl")).toHaveLength(0);
  });

  it("disambiguates repeated quotes using their context", () => {
    const prose = build(`<p>alpha TARGET omega</p><p>beta TARGET omega</p>`);
    const range = document.createRange();
    const second = prose.children[1].firstChild as Text;
    range.setStart(second, 5);
    range.setEnd(second, 11);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);

    const hl = captureSelection(prose, "07")!;
    expect(hl.quote).toBe("TARGET");
    expect(hl.prefix.endsWith("beta ")).toBe(true);

    state.highlights = [{ ...hl, color: 1, note: "" }];
    const again = build(`<p>alpha TARGET omega</p><p>beta TARGET omega</p>`);
    applyHighlights(again, "07");

    // The mark must land in the *second* paragraph.
    expect(again.children[0].querySelector(".hl")).toBeNull();
    expect(again.children[1].querySelector(".hl")?.textContent).toBe("TARGET");
  });
});
