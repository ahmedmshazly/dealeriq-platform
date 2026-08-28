import MiniSearch from "minisearch";
import type { Corpus, Section } from "../types.js";

/**
 * Full-text search over 452 *sections*, not 29 files.
 *
 * The index is built and serialized by `scripts/build-index.ts`; the client
 * deserializes rather than re-indexes, so the first keystroke is instant.
 *
 * Being told a phrase is "somewhere in vitae-srs.md" - a 15,000-word document -
 * is not an answer. "vitae-srs § Cost model" is.
 */
const OPTIONS = {
  idField: "id",
  fields: ["title", "path", "text", "keywords"],
  storeFields: [] as string[],
};

const SEARCH = {
  boost: { title: 4, path: 2, keywords: 2 },
  prefix: true,
  fuzzy: 0.18,
  combineWith: "AND" as const,
};

export interface Hit {
  section: Section;
  score: number;
}

export class Search {
  private mini: MiniSearch;
  private byId: Map<string, Section>;

  constructor(corpus: Corpus) {
    this.mini = MiniSearch.loadJS(corpus.search as never, OPTIONS);
    this.byId = new Map(corpus.sections.map((s) => [s.id, s]));
  }

  query(q: string, limit = 40): Hit[] {
    const text = q.trim();
    if (text.length < 2) return [];
    return this.mini
      .search(text, SEARCH)
      .slice(0, limit)
      .flatMap((r) => {
        const section = this.byId.get(r.id as string);
        return section ? [{ section, score: r.score }] : [];
      });
  }

  suggest(q: string, limit = 5): string[] {
    if (q.trim().length < 2) return [];
    return this.mini
      .autoSuggest(q, { ...SEARCH, fuzzy: 0.2 })
      .slice(0, limit)
      .map((s) => s.suggestion);
  }
}

/**
 * Case-insensitive subsequence match, the scoring every command palette uses.
 * Returns the matched character indices so the caller can bold them, or `null`
 * when the needle is not a subsequence of the haystack at all.
 */
export function fuzzy(
  needle: string,
  haystack: string,
): { score: number; hits: number[] } | null {
  if (!needle) return { score: 0, hits: [] };
  const n = needle.toLowerCase();
  const hay = haystack.toLowerCase();

  const hits: number[] = [];
  let score = 0;
  let at = 0;
  let streak = 0;

  for (const ch of n) {
    const found = hay.indexOf(ch, at);
    if (found === -1) return null;

    // Reward adjacency and word boundaries; penalise distance skipped.
    if (found === at) streak++;
    else streak = 0;
    const boundary = found === 0 || /[\s/_.\-›#§]/.test(hay[found - 1]);
    score +=
      1 + streak * 2 + (boundary ? 3 : 0) - Math.min(3, (found - at) * 0.1);

    hits.push(found);
    at = found + 1;
  }
  // Prefer short haystacks: `06` should beat `06-data-model.md` for "06".
  return { score: score - haystack.length * 0.02, hits };
}

export function markHits(text: string, hits: number[]): DocumentFragment {
  const frag = document.createDocumentFragment();
  const set = new Set(hits);
  let buf = "";
  let bold = false;

  const flush = (): void => {
    if (!buf) return;
    if (bold) {
      const el = document.createElement("b");
      el.className = "pal-hit";
      el.textContent = buf;
      frag.append(el);
    } else frag.append(document.createTextNode(buf));
    buf = "";
  };

  [...text].forEach((ch, i) => {
    const isHit = set.has(i);
    if (isHit !== bold) {
      flush();
      bold = isHit;
    }
    buf += ch;
  });
  flush();
  return frag;
}
