import katex from "katex";

export interface MathBlock {
  id: string;
  display: boolean;
  tex: string;
  html: string;
}

/**
 * `$` is a dangerous delimiter in a corpus that also documents shell scripts and
 * quotes prices. Every one of these is a real string in `docs/`, and none of
 * them is math:
 *
 *   `[ -e "$f" ]`                      — shell, inside a fence
 *   `~$5/mo`  `$0–20`  `$0.50`         — currency, in tables
 *   `` `https://${site.domain}` ``     — template literal, inline code
 *   `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`     — a regex, inline code
 *   `` `\write18{rm -rf} & 100% $$` `` — a TeX-injection example, inline code
 *
 * Three rules kill all of them without a single special case:
 *
 *   1. Never look inside a fenced block or an inline code span.
 *   2. Display math (`$$`) must own its line, top and bottom.
 *   3. An inline `$` opener must be followed by a non-space and must close on
 *      the same line — and the closing `$` must not be followed by a digit.
 *
 * That last clause is the whole game, and it is not the obvious one. Rejecting
 * a *digit after the opener* looks like the natural way to exclude currency, and
 * it does exclude all of it — but it also silently swallows five real
 * expressions that legitimately begin with a number (`$2\pi$`, `$2^{32}$`,
 * `$80 + 60 = 140$`). The only string in the corpus that survives every other
 * rule is a price *range*:
 *
 *     **≈$3–10 typical; $45 hard ceiling**
 *
 * There, the closing `$` is followed by `4` — because it is not a closer at all,
 * it is the next price. Real math is always followed by punctuation or a space.
 *
 * Only `docs/11b-math-foundation.md` contains real math (41 expressions), and
 * every `\` command it uses is standard KaTeX, so no custom macros are needed.
 */

/**
 * Both fence patterns are line-anchored and consume neither the leading nor the
 * trailing newline, so a fenced block collapses to a one-line sentinel without
 * disturbing the block structure around it.
 */
const FENCE = /^(```|~~~)[^\n]*\n[\s\S]*?^\1[ \t]*$/gm;
const INLINE_CODE = /(`+)([^\n]*?)\1(?!`)/g;

const DISPLAY = /^\$\$[ \t]*\r?\n([\s\S]*?)\r?\n\$\$[ \t]*$/gm;

/**
 * The lookaround on both sides is what keeps `$$` out of the inline scanner.
 * Without `(?<!\$)`, an inline `$$x$$` is matched starting at its *second*
 * dollar and read as the expression `x`, quietly demoting display maths to
 * inline. Without `(?!\d)` on the closer, `≈$3–10 typical; $45` parses as maths.
 */
const INLINE = /(?<!\$)\$(?!\s)((?:\\.|[^$\n\\])+?)\$(?![\d$])/g;

const ph = (n: number): string => `%%MATH${n}%%`;

const NUL = "\u0000";

/**
 * Hide protected regions behind sentinels while the math regexes run.
 *
 * The sentinel must be a byte sequence that cannot occur in markdown, or
 * restoring it will corrupt prose. NUL is the only safe choice: an earlier draft
 * used space-digits-space, which would have matched the phrase "in 5 minutes"
 * and rewritten it into a code block.
 */
function mask(src: string): { masked: string; restore: (s: string) => string } {
  const holes: string[] = [];
  const stash = (m: string): string => `${NUL}${holes.push(m) - 1}${NUL}`;

  const masked = src.replace(FENCE, stash).replace(INLINE_CODE, stash);

  const restore = (s: string): string =>
    s.replace(
      new RegExp(`${NUL}(\\d+)${NUL}`, "g"),
      (_, i: string) => holes[Number(i)],
    );

  return { masked, restore };
}

export function extractMath(markdown: string): {
  text: string;
  blocks: MathBlock[];
} {
  const blocks: MathBlock[] = [];
  const { masked, restore } = mask(markdown);

  let out = masked.replace(DISPLAY, (_full, tex: string) => {
    const id = ph(blocks.length);
    blocks.push({
      id,
      display: true,
      tex: tex.trim(),
      html: render(tex, true),
    });
    return id;
  });

  out = out.replace(INLINE, (full, tex: string) => {
    if (!tex.trim()) return full;
    const id = ph(blocks.length);
    blocks.push({
      id,
      display: false,
      tex: tex.trim(),
      html: render(tex, false),
    });
    return id;
  });

  return { text: restore(out), blocks };
}

function render(tex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(tex.trim(), {
      displayMode,
      throwOnError: true,
      strict: false,
      trust: false,
      // Keep MathML. It is what lets a screen reader speak the formula, and it
      // is why this reader can meet the a11y bar the portfolio already enforces.
      output: "htmlAndMathml",
    });
  } catch (err) {
    const why = err instanceof Error ? err.message : String(err);
    console.warn(`math · KaTeX failed on ${JSON.stringify(tex)}: ${why}`);
    return `<code class="math-error" title="${escapeAttr(why)}">${escapeHtml(tex)}</code>`;
  }
}

/**
 * Put the rendered math back. Display blocks arrive wrapped in a `<p>` by the
 * markdown renderer; a `<div>` inside a `<p>` is invalid and browsers silently
 * reparent it, so unwrap those first.
 */
export function restoreMath(html: string, blocks: MathBlock[]): string {
  let out = html;
  for (const b of blocks) {
    if (b.display) {
      out = out.replaceAll(
        `<p>${b.id}</p>`,
        `<div class="math-block">${b.html}</div>`,
      );
    }
  }
  for (const b of blocks) out = out.replaceAll(b.id, b.html);
  return out;
}

const escapeHtml = (s: string): string =>
  s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]!);
const escapeAttr = (s: string): string => escapeHtml(s).replace(/"/g, "&quot;");
