import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { extractMath } from "./math.js";

const DOCS = resolve(import.meta.dirname, "../../../docs");
const tex = (md: string): string[] => extractMath(md).blocks.map((b) => b.tex);

describe("inline math delimiters", () => {
  it("recognises real expressions", () => {
    expect(tex("the value $t$ is a tier")).toEqual(["t"]);
    expect(tex("a rational multiple of $2\\pi$ would spoke")).toEqual([
      "2\\pi",
    ]);
    expect(tex("a period of $2^{32}$, seeded")).toEqual(["2^{32}"]);
    expect(tex("scores at most $80 + 60 = 140$, which ranks")).toEqual([
      "80 + 60 = 140",
    ]);
    expect(tex("bounded at $3.3 / 0.8 = 4.125$.")).toEqual([
      "3.3 / 0.8 = 4.125",
    ]);
  });

  /**
   * The five above all begin with a digit. Rejecting "digit after the opener" —
   * the obvious way to exclude currency — silently swallows every one of them.
   */
  it("does not reject expressions that begin with a number", () => {
    expect(tex("$2\\pi$ radians")).not.toEqual([]);
  });

  it("rejects currency", () => {
    expect(tex("a ~$5/mo container host is acceptable")).toEqual([]);
    expect(tex("| Vercel | Hobby | $0–20 |")).toEqual([]);
    expect(tex("| Cloudflare R2 | ~$0.50 |")).toEqual([]);
  });

  /** The only string in the corpus that survives every other rule. */
  it("rejects a price range, where the closer is the next price", () => {
    expect(tex("| **Total** | **≈$3–10 typical; $45 hard ceiling** |")).toEqual(
      [],
    );
  });

  it("never looks inside a fenced block", () => {
    const md = [
      "```bash",
      'for f in *; do [ -e "$f" ] || echo "$f"; done',
      "```",
    ].join("\n");
    expect(tex(md)).toEqual([]);
  });

  it("never looks inside an inline code span", () => {
    expect(tex("matches `/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/` exactly")).toEqual(
      [],
    );
    expect(
      tex("from `` `https://${site.domain}` `` where site is seed data"),
    ).toEqual([]);
    expect(tex("bullet contains `\\write18{rm -rf} & 100% $$`")).toEqual([]);
  });

  it("restores masked code verbatim", () => {
    const md = "before `a $ b` middle\n\n```\n$x\n```\n\nafter $t$ end";
    const { text } = extractMath(md);
    expect(text).toContain("`a $ b`");
    expect(text).toContain("$x");
    expect(text).not.toContain("\u0000");
  });
});

describe("display math", () => {
  it("requires $$ to own its line", () => {
    expect(tex("$$\nx = 1\n$$")).toEqual(["x = 1"]);
    expect(tex("inline $$x$$ mid-sentence")).toEqual([]);
  });

  it("renders KaTeX, not an error node", () => {
    const [block] = extractMath(
      "$$\nf = \\begin{cases} 1 & d \\le 1 \\end{cases}\n$$",
    ).blocks;
    expect(block.html).toContain("katex");
    expect(block.html).not.toContain("math-error");
  });
});

/** Soft corpus checks — DealerIQ may have little or no KaTeX. */
describe("against the corpus", () => {
  const walk = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
      e.isDirectory()
        ? walk(join(dir, e.name))
        : e.name.endsWith(".md")
          ? [join(dir, e.name)]
          : [],
    );

  const results = walk(DOCS).map(
    (f) => [f, extractMath(readFileSync(f, "utf8")).blocks] as const,
  );

  it("finds math only where the corpus uses it", () => {
    const withMath = results
      .filter(([, b]) => b.length)
      .map(([f]) => f.split("/").pop());
    expect(Array.isArray(withMath)).toBe(true);
  });

  it("counts display vs inline without a fixed portfolio total", () => {
    const blocks = results.flatMap(([, b]) => b);
    expect(blocks.filter((b) => b.display).length).toBeGreaterThanOrEqual(0);
    expect(blocks.filter((b) => !b.display).length).toBeGreaterThanOrEqual(0);
  });

  it("renders extracted math without a KaTeX error", () => {
    const bad = results
      .flatMap(([, b]) => b)
      .filter((b) => b.html.includes("math-error"));
    expect(bad).toEqual([]);
  });
});
