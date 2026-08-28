import type { CodeFile, CodePayload } from "../types.js";
import { h } from "./dom.js";

/**
 * The syntax-highlighting payload, loaded on first use.
 *
 * In dev this is a separate chunk Vite fetches on demand. In the packed single
 * file it is already inlined, so the `import()` resolves immediately. Either
 * way the shell boots without paying for 2.7 MB of source it may never show.
 */
let payload: CodePayload | null = null;
let loading: Promise<CodePayload> | null = null;

export async function codePayload(): Promise<CodePayload> {
  if (payload) return payload;
  loading ??= import("../generated/code.json").then((m) => {
    payload = (m.default ?? m) as unknown as CodePayload;
    return payload;
  });
  return loading;
}

export const codeFile = (path: string): CodeFile | undefined =>
  payload?.files[path];

/** Must match `STYLE_ALPHABET` in `scripts/build-index.ts`. */
const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
const RUN = /(\d+)([A-Za-z])/g;

/**
 * Rebuild one highlighted line from `"6A7B1C"` - decimal run length, then a
 * letter indexing the shared palette.
 *
 * Shiki's dual-theme HTML measured 12.3× the source (13.2 MB across 229 files).
 * This encoding is 1.1×, and because the client owns the render it can put a
 * gutter, an annotation marker, and a line anchor around every line - which
 * pre-rendered HTML would have made impossible.
 */
export function renderLine(
  text: string,
  runs: string,
  palette: [string, string][],
): DocumentFragment {
  const frag = document.createDocumentFragment();
  if (!runs) {
    frag.append(text || "\n");
    return frag;
  }

  let at = 0;
  RUN.lastIndex = 0;
  for (let m = RUN.exec(runs); m; m = RUN.exec(runs)) {
    const len = Number(m[1]);
    const idx = ALPHABET.indexOf(m[2]);
    const slice = text.slice(at, at + len);
    at += len;
    if (!slice) continue;

    const style = palette[idx];
    if (!style) {
      frag.append(slice);
      continue;
    }
    const span = h("span", {}, slice);
    span.style.setProperty("--shiki-light", style[0]);
    span.style.setProperty("--shiki-dark", style[1]);
    frag.append(span);
  }

  // A run table that under-covers its line is a bug, but the reader should show
  // the remaining characters rather than silently truncate the code.
  if (at < text.length) frag.append(text.slice(at));
  return frag;
}
