import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { Slugger, plainText, slugify } from "./slug.js";

const DOCS = resolve(import.meta.dirname, "../../../docs");

const walk = (dir: string): string[] =>
  readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory()
      ? walk(join(dir, e.name))
      : e.name.endsWith(".md")
        ? [join(dir, e.name)]
        : [],
  );

/** Same crude inline-markdown stripper the indexer's section splitter uses. */
const inline = (md: string): string =>
  plainText(
    md
      .replace(/`([^`]*)`/g, "$1")
      .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
      .replace(/\*\*([^*]*)\*\*/g, "$1")
      .replace(/\*([^*]*)\*/g, "$1")
      .trim(),
  );

function slugsOf(src: string): Set<string> {
  const sl = new Slugger();
  const out = new Set<string>();
  let inFence = false;
  for (const line of src.split("\n")) {
    if (/^\s*```/.test(line)) inFence = !inFence;
    if (inFence) continue;
    const m = /^#{1,6} (.+?)\s*$/.exec(line);
    if (m) out.add(sl.slug(inline(m[1])));
  }
  return out;
}

describe("slugify", () => {
  // Each of these is a real heading in `docs/`, and each one breaks a different
  // naive implementation.
  it.each([
    ["Rendering strategy", "rendering-strategy"],
    // Consecutive hyphens are NOT collapsed: deleting the em-dash leaves both
    // of the spaces that surrounded it.
    ["C4 level 1 — system context", "c4-level-1--system-context"],
    ["Design decisions & trade-offs", "design-decisions--trade-offs"],
    ["The client/server split", "the-clientserver-split"],
    ["POST /api/contact", "post-apicontact"],
    ["Where do I find…?", "where-do-i-find"],
    ["The `db ↔ github` cycle", "the-db--github-cycle"],
    // The one that `\w` gets wrong. `docs/11b-math-foundation.md` links to
    // `#timeline--the-bézier-fork-curve`, accent intact.
    ["Timeline — the Bézier fork curve", "timeline--the-bézier-fork-curve"],
  ])("%s → %s", (text, expected) => {
    expect(slugify(text)).toBe(expected);
  });

  it("does not use the ASCII \\w shorthand", () => {
    expect(slugify("Bézier")).toBe("bézier");
    expect(slugify("Bézier")).not.toBe("bzier");
  });

  it("disambiguates repeats the way GitHub does", () => {
    const s = new Slugger();
    expect([s.slug("Request"), s.slug("Request"), s.slug("Request")]).toEqual([
      "request",
      "request-1",
      "request-2",
    ]);
  });
});

describe("plainText", () => {
  it("strips tags and decodes entities before slugging", () => {
    expect(plainText("<code>POST /api/contact</code>")).toBe(
      "POST /api/contact",
    );
    expect(plainText("Design decisions &amp; trade-offs")).toBe(
      "Design decisions & trade-offs",
    );
    expect(slugify(plainText("Design decisions &amp; trade-offs"))).toBe(
      "design-decisions--trade-offs",
    );
  });
});

/**
 * The regression test for the bug that shipped in the handbook itself: a wrong
 * slugger silently 404s links that work on github.com.
 */
describe("the whole corpus", () => {
  const files = walk(DOCS);
  const slugs = new Map(
    files.map((f) => [f, slugsOf(readFileSync(f, "utf8"))]),
  );

  it("finds every document", () => {
    expect(files.length).toBeGreaterThanOrEqual(40);
  });

  it("resolves every intra-document anchor", () => {
    const misses: string[] = [];
    for (const [file, src] of files.map(
      (f) => [f, readFileSync(f, "utf8")] as const,
    )) {
      const inCode = maskCode(src);
      for (const m of inCode.matchAll(/\]\(#([^)]+)\)/g)) {
        const anchor = decodeURIComponent(m[1]);
        if (!slugs.get(file)!.has(anchor))
          misses.push(`${rel(file)} → #${anchor}`);
      }
    }
    expect(misses).toEqual([]);
  });

  it("resolves every cross-document anchor", () => {
    const misses: string[] = [];
    for (const [file, src] of files.map(
      (f) => [f, readFileSync(f, "utf8")] as const,
    )) {
      const inCode = maskCode(src);
      for (const m of inCode.matchAll(/\]\((\.\/[^)#]+\.md)#([^)]+)\)/g)) {
        const target = resolve(file, "..", m[1]);
        const anchor = decodeURIComponent(m[2]);
        const set = slugs.get(target);
        if (!set) misses.push(`${rel(file)} → missing file ${m[1]}`);
        else if (!set.has(anchor))
          misses.push(`${rel(file)} → ${m[1]}#${anchor}`);
      }
    }
    expect(misses).toEqual([]);
  });
});

const rel = (f: string): string => f.slice(DOCS.length + 1);

/** `12-gaps.md` documents a link checker, so it *quotes* `](./target.md#anchor)`. */
const maskCode = (src: string): string =>
  src
    .replace(/^(```|~~~)[^\n]*\n[\s\S]*?^\1[ \t]*$/gm, "")
    .replace(/(`+)([^\n]*?)\1(?!`)/g, "");
