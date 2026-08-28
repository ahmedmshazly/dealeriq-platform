/**
 * Persisted state.
 *
 * A desktop application remembers. Close it mid-paragraph and it reopens there,
 * with the same panes, the same width, the same highlights. Everything here
 * lives in `localStorage` under one namespaced key so it can be inspected,
 * exported, or wiped in one move.
 */

const KEY = "diqdocs:v1";

/** DealerIQ handbook theme — independent of the portfolio `ae-theme` key. */
const THEME_KEY = "diq-theme";

export type Theme = "dark" | "light";

export interface Highlight {
  id: string;
  doc: string;
  /** Anchor of the section the selection began in — where we start searching. */
  anchor: string | null;
  /**
   * Text-quote anchoring, as used by Hypothesis and the W3C annotation model.
   * Character offsets break the moment a paragraph above is edited; a quote plus
   * its surrounding context survives a rebuild, and degrades to "orphaned"
   * rather than to "silently pointing at the wrong sentence".
   */
  quote: string;
  prefix: string;
  suffix: string;
  color: 1 | 2 | 3 | 4;
  note: string;
  created: number;
}

export interface Persisted {
  lastRoute: string;
  /** doc id → deepest scroll fraction ever reached, 0…1. */
  progress: Record<string, number>;
  /** doc id → last scrollTop, so returning restores the exact position. */
  scroll: Record<string, number>;
  bookmarks: { doc: string; anchor: string; title: string; at: number }[];
  highlights: Highlight[];
  /** checkpoint n → known. */
  checkpoints: Record<number, boolean>;
  sideWidth: number;
  railWidth: number;
  sideOn: boolean;
  railOn: boolean;
  focus: boolean;
  /** The reference layer (dotted terms) can be turned off wholesale. */
  refs: boolean;
  recent: string[];
  /** Palette frecency: item id → score. */
  freq: Record<string, number>;
}

const DEFAULTS: Persisted = {
  lastRoute: "#/start",
  progress: {},
  scroll: {},
  bookmarks: [],
  highlights: [],
  checkpoints: {},
  sideWidth: 268,
  railWidth: 260,
  sideOn: true,
  railOn: true,
  focus: false,
  refs: true,
  recent: [],
  freq: {},
};

function load(): Persisted {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Persisted>) };
  } catch {
    // Private mode, corrupted JSON, quota — none of these should stop you
    // reading. Fall back to defaults and keep going.
    return { ...DEFAULTS };
  }
}

export const state: Persisted = load();

let saveTimer: number | undefined;
export function save(): void {
  clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* quota exceeded: the session still works, it just will not persist */
    }
  }, 250);
}

/* ── theme ─────────────────────────────────────────────────────── */

export function theme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function setTheme(next: Theme): void {
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent("themechange", { detail: next }));
}

/* ── progress ──────────────────────────────────────────────────── */

/** A doc counts as read at 90%: the last tenth is nav footers and backlinks. */
export const READ_AT = 0.9;

export function recordProgress(doc: string, fraction: number): void {
  const prev = state.progress[doc] ?? 0;
  const next = Math.min(1, Math.max(prev, fraction));
  if (next - prev < 0.01) return;
  state.progress[doc] = next;
  save();
  // Not `"progress"`: the DOM already defines that name as a `ProgressEvent`.
  window.dispatchEvent(new CustomEvent("docprogress", { detail: doc }));
}

export const isRead = (doc: string): boolean =>
  (state.progress[doc] ?? 0) >= READ_AT;

export function pushRecent(route: string): void {
  state.recent = [route, ...state.recent.filter((r) => r !== route)].slice(
    0,
    12,
  );
  state.lastRoute = route;
  save();
}

export function bumpFreq(id: string): void {
  state.freq[id] = (state.freq[id] ?? 0) + 1;
  save();
}

/* ── bookmarks ─────────────────────────────────────────────────── */

export function toggleBookmark(
  doc: string,
  anchor: string,
  title: string,
): boolean {
  const i = state.bookmarks.findIndex(
    (b) => b.doc === doc && b.anchor === anchor,
  );
  if (i >= 0) {
    state.bookmarks.splice(i, 1);
    save();
    return false;
  }
  state.bookmarks.unshift({ doc, anchor, title, at: Date.now() });
  save();
  return true;
}

export const hasBookmark = (doc: string, anchor: string): boolean =>
  state.bookmarks.some((b) => b.doc === doc && b.anchor === anchor);
