/**
 * GitHub-compatible heading slugs.
 *
 * This is the single most load-bearing function in the indexer: the corpus has
 * 411 internal links, almost all of them anchored, and every one of them was
 * authored against GitHub's slugging rules. Get this wrong and the app silently
 * 404s on links that work fine on github.com.
 *
 * The rule GitHub actually applies (see `github-slugger`) is:
 *
 *   1. lowercase
 *   2. delete punctuation and symbols - but NOT letters, digits, marks,
 *      underscores, hyphens or spaces
 *   3. replace each remaining space with a hyphen
 *
 * Two consequences that trip people up, both present in this corpus:
 *
 *   - Consecutive hyphens are NOT collapsed. `A — B` becomes `a--b`, because
 *     deleting the em-dash leaves the two spaces that surrounded it.
 *   - The rule is Unicode-aware, not ASCII. `Bézier` becomes `bézier`, not
 *     `bzier`. `docs/11b-math-foundation.md` links to `#timeline--the-bézier-fork-curve`.
 *
 * Using `\w` here (as an ASCII shorthand) breaks the second case.
 */
const STRIP = /[^\p{L}\p{N}\p{M}\p{Pc}\- ]+/gu;

export function slugify(text: string): string {
  return text.toLowerCase().replace(STRIP, "").replace(/ /g, "-");
}

/**
 * GitHub disambiguates repeated headings with `-1`, `-2`, ... in document order.
 * One slugger instance per document; never share across files.
 */
export class Slugger {
  private seen = new Map<string, number>();

  slug(text: string): string {
    const base = slugify(text);
    const n = this.seen.get(base);
    if (n === undefined) {
      this.seen.set(base, 0);
      return base;
    }
    const next = n + 1;
    this.seen.set(base, next);
    return `${base}-${next}`;
  }

  reset(): void {
    this.seen.clear();
  }
}

const ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
  hellip: "…",
  mdash: "—",
  ndash: "–",
  laquo: "«",
  raquo: "»",
};

/**
 * Reduce rendered inline HTML back to the text GitHub would have slugged.
 *
 * Marked hands the heading renderer *already-rendered* inline HTML, so
 * `` ### `POST /api/contact` `` arrives as `<code>POST /api/contact</code>` and
 * `Design decisions & trade-offs` arrives with `&amp;`. Slugging either of those
 * verbatim produces the wrong anchor - hence tags out, entities decoded.
 */
export function plainText(html: string): string {
  return html
    .replace(/<[^>]*>/g, "")
    .replace(/&#(\d+);/g, (_, d: string) => String.fromCodePoint(Number(d)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h: string) =>
      String.fromCodePoint(parseInt(h, 16)),
    )
    .replace(/&([a-z]+);/gi, (m, name: string) => ENTITIES[name] ?? m);
}
