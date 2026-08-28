import type { LastVerified } from "../../src/types.js";

export interface FrontMatter {
  title: string | null;
  description: string | null;
  keywords: string[];
  lastVerified: LastVerified | null;
}

const EMPTY: FrontMatter = {
  title: null,
  description: null,
  keywords: [],
  lastVerified: null,
};

/**
 * Parse the handbook's four-key front-matter without taking a YAML dependency.
 *
 * A general YAML parser would be both heavier and *less* correct here, because
 * two of the four values are not really YAML scalars:
 *
 *   - `keywords` is a flow sequence that Prettier reflows across lines once it
 *     exceeds 80 columns, so it must be joined before it can be split.
 *   - `last-verified: 2026-07-09 (4f24c86)` looks like a date but is not one.
 *     A YAML parser hands back a `Date` and silently drops the sha.
 *
 * Five files under `docs/background/` have no front-matter at all. That is not
 * an error; they get `EMPTY` and the caller falls back to the first H1.
 */
export function parseFrontMatter(src: string): {
  data: FrontMatter;
  body: string;
} {
  if (!src.startsWith("---\n")) return { data: EMPTY, body: src };

  const end = src.indexOf("\n---", 4);
  if (end === -1) return { data: EMPTY, body: src };

  const raw = src.slice(4, end);
  const body = src.slice(end + 4).replace(/^\r?\n/, "");

  // Re-join Prettier's wrapped flow arrays before parsing keys, so that
  // `keywords:\n  [\n    a,\n    b,\n  ]` reads as one logical line.
  const lines = raw.split("\n");
  const logical: string[] = [];
  for (const line of lines) {
    if (/^\s/.test(line) && logical.length > 0)
      logical[logical.length - 1] += " " + line.trim();
    else logical.push(line);
  }

  const data: FrontMatter = { ...EMPTY, keywords: [] };

  for (const line of logical) {
    const m = /^([a-z-]+):\s*(.*)$/i.exec(line);
    if (!m) continue;
    const [, key, value] = m;

    switch (key) {
      case "title":
        data.title = unquote(value);
        break;
      case "description":
        data.description = unquote(value);
        break;
      case "keywords":
        data.keywords = parseFlowArray(value);
        break;
      case "last-verified": {
        const lv = /^(\d{4}-\d{2}-\d{2})\s*\(([0-9a-f]+)\)/i.exec(value.trim());
        if (lv) data.lastVerified = { date: lv[1], sha: lv[2] };
        break;
      }
      default:
        break;
    }
  }

  return { data, body };
}

function unquote(s: string): string {
  const t = s.trim();
  if (
    (t.startsWith('"') && t.endsWith('"')) ||
    (t.startsWith("'") && t.endsWith("'"))
  ) {
    return t.slice(1, -1);
  }
  return t;
}

/** `[a, b, c]` → `["a","b","c"]`. Tolerates the trailing comma Prettier adds. */
function parseFlowArray(value: string): string[] {
  const t = value.trim();
  if (!t.startsWith("[")) return t ? [t] : [];
  return t
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .split(",")
    .map((s) => unquote(s))
    .filter(Boolean);
}
