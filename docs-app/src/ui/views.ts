import type { Corpus } from "../types.js";
import { clear, h, toast } from "../lib/dom.js";
import type { Search } from "../lib/search.js";
import { isRead, state, save, READ_AT } from "../lib/store.js";
import { exportMarkdown, removeHighlight } from "./annotate.js";

export interface ViewDeps {
  corpus: Corpus;
  search: Search;
  main: HTMLElement;
  rail: HTMLElement;
  openDoc: (doc: string, anchor?: string | null) => void;
  openCode: (path: string, line?: number) => void;
  openPalette: () => void;
}

const view = (...kids: (Node | string | null)[]): HTMLElement =>
  h("div", { class: "view" }, ...kids);

/* ── start ─────────────────────────────────────────────────────── */

export function renderStart(deps: ViewDeps): void {
  const { corpus, main, rail } = deps;
  clear(main);
  clear(rail);

  const s = corpus.stats;
  const readCount = corpus.docs.filter((d) => isRead(d.id)).length;
  const inProgress = corpus.docs.find((d) => {
    const p = state.progress[d.id] ?? 0;
    return p > 0.02 && p < READ_AT;
  });

  const stats = h(
    "div",
    { class: "cards", style: "margin-bottom:32px" },
    stat(s.docs, "documents"),
    stat(s.words.toLocaleString(), "words"),
    stat(s.headings, "sections"),
    stat(s.links, "cross-links"),
    stat(s.citedFiles, "files cited"),
    stat(s.symbols, "symbols indexed"),
    stat(s.mermaid, "diagrams"),
    stat(`${Math.round(s.readMinutes / 60)}h`, "to read it all"),
  );

  const resume = inProgress
    ? h(
        "button",
        {
          class: "card",
          style: "margin-bottom:26px;display:block;width:100%",
          onclick: () => deps.openDoc(inProgress.id),
        },
        h("div", { class: "stat-l" }, "Continue reading"),
        h(
          "div",
          { style: "font-size:19px;color:var(--head);margin:6px 0 4px" },
          inProgress.title,
        ),
        h(
          "div",
          { style: "color:var(--muted);font-size:13px" },
          `${Math.round((state.progress[inProgress.id] ?? 0) * 100)}% · ${inProgress.readMinutes} min read`,
        ),
      )
    : null;

  const sessions = h("div", { class: "cards" });
  for (const session of corpus.sessions) {
    const done = session.docs.filter(isRead).length;
    sessions.append(
      h(
        "button",
        { class: "card", onclick: () => deps.openDoc(session.docs[0] ?? "00") },
        h(
          "div",
          { class: "stat-l" },
          `Session ${session.n} · ${session.minutes} min`,
        ),
        h(
          "div",
          { style: "font-size:17px;color:var(--head);margin:6px 0" },
          session.title,
        ),
        h(
          "div",
          { style: "color:var(--muted);font-size:12.5px" },
          `${done}/${session.docs.length} read · ${session.docs.join(", ")}`,
        ),
      ),
    );
  }

  const stale = corpus.docs.filter((d) => (d.commitsBehind ?? 0) > 0);

  main.append(
    view(
      h("h2", { class: "start-brand" }, "DealerIQ"),
      h(
        "p",
        { class: "view-sub" },
        `Architecture handbook · ${s.docs} documents, verified against ${corpus.head}. ` +
          `Press ⌘K to jump anywhere, or start with the reading path.`,
      ),
      resume,
      stats,
      h("h2", { style: "font-size:19px;margin-top:34px" }, "Reading path"),
      h(
        "p",
        { class: "view-sub" },
        `Three sessions. ${readCount} of ${s.docs} documents read.`,
      ),
      sessions,
      stale.length
        ? h(
            "p",
            {
              class: "view-sub",
              style: "margin-top:30px;color:var(--accent-3)",
            },
            `${stale.length} document(s) verified against an older commit than HEAD.`,
          )
        : null,
    ),
  );

  rail.append(
    h(
      "section",
      { class: "rail-section" },
      h("h2", { class: "rail-label" }, "Jump to"),
      link("Reading path", () => deps.openDoc("00")),
      link("Master index", () => deps.openDoc("readme")),
      link("Reverse index", () => deps.openDoc("index")),
      link("Glossary", () => deps.openDoc("glossary")),
      link("Known gaps", () => deps.openDoc("12")),
    ),
  );
}

const stat = (n: string | number, label: string): HTMLElement =>
  h(
    "div",
    { class: "card" },
    h("div", { class: "stat-n" }, String(n)),
    h("div", { class: "stat-l" }, label),
  );

const link = (text: string, onclick: () => void): HTMLElement =>
  h("button", { class: "backlink", onclick }, text);

/* ── atlas ─────────────────────────────────────────────────────── */

/**
 * Rank every indexed source file by how many documents cite it. The top of the
 * list is the system's documented spine. The bottom — 117 files nothing
 * references — is the more useful half of the answer.
 */
export function renderAtlas(deps: ViewDeps): void {
  const { corpus, main, rail } = deps;
  clear(main);
  clear(rail);

  const files = [...corpus.files].sort(
    (a, b) =>
      b.citedBy.length - a.citedBy.length || a.path.localeCompare(b.path),
  );
  const max = files[0]?.citedBy.length || 1;
  const undocumented = files.filter((f) => !f.citedBy.length).length;

  const bars = h("div", { class: "bars" });
  for (const f of files) {
    const n = f.citedBy.length;
    bars.append(
      h(
        "button",
        {
          class: "bar-row",
          title: n
            ? `Cited by ${f.citedBy.join(", ")}`
            : "Not documented anywhere",
          onclick: () => deps.openCode(f.path),
        },
        h("span", { class: "bar-path" }, f.path),
        h(
          "span",
          { class: "bar-track" },
          h("span", {
            class: "bar-fill",
            "data-zero": n === 0 ? "" : null,
            style: `width:${n ? (n / max) * 100 : 100}%;opacity:${n ? 1 : 0.28}`,
          }),
        ),
        h("span", { class: "bar-n" }, n ? String(n) : "—"),
      ),
    );
  }

  main.append(
    view(
      h("h2", {}, "Code Atlas"),
      h(
        "p",
        { class: "view-sub" },
        `${corpus.files.length} indexed files ranked by how many documents cite them. ` +
          `${undocumented} are cited by nothing at all — which is the number worth staring at.`,
      ),
      bars,
    ),
  );
}

/* ── notes ─────────────────────────────────────────────────────── */

export function renderNotes(deps: ViewDeps): void {
  const { corpus, main, rail } = deps;
  clear(main);
  clear(rail);

  const titleOf = (id: string): string =>
    corpus.docs.find((d) => d.id === id)?.title ?? id;
  const body = h("div");

  const paint = (): void => {
    clear(body);

    if (!state.highlights.length && !state.bookmarks.length) {
      body.append(
        h(
          "p",
          { class: "view-sub" },
          "Select any passage while reading to highlight it, or press b to bookmark a section.",
        ),
      );
      return;
    }

    for (const hl of state.highlights) {
      body.append(
        h(
          "div",
          { class: "card", style: "margin-bottom:10px;cursor:default" },
          h(
            "div",
            {
              class: "stat-l",
              style: "display:flex;gap:10px;align-items:center",
            },
            h("span", {}, titleOf(hl.doc)),
            hl.anchor
              ? h("span", { style: "color:var(--faint-2)" }, `§ ${hl.anchor}`)
              : null,
            h("span", { style: "flex:1" }),
            h(
              "button",
              {
                class: "pop-open",
                onclick: () => deps.openDoc(hl.doc, hl.anchor),
              },
              "Open →",
            ),
            h(
              "button",
              {
                class: "pop-open",
                style: "color:var(--danger);margin-left:0",
                onclick: () => {
                  removeHighlight(hl.id);
                  paint();
                },
              },
              "Delete",
            ),
          ),
          h(
            "blockquote",
            {
              style: `margin:10px 0 0;border-left:3px solid var(--accent);padding-left:12px;color:var(--read)`,
            },
            hl.quote,
          ),
          hl.note
            ? h(
                "p",
                {
                  style: "margin:10px 0 0;color:var(--accent-3);font-size:13px",
                },
                `✎ ${hl.note}`,
              )
            : null,
        ),
      );
    }

    for (const b of state.bookmarks) {
      body.append(
        h(
          "button",
          { class: "backlink", onclick: () => deps.openDoc(b.doc, b.anchor) },
          `🔖 ${titleOf(b.doc)} § ${b.title}`,
        ),
      );
    }
  };

  paint();

  main.append(
    view(
      h("h2", {}, "Notes"),
      h(
        "p",
        { class: "view-sub" },
        `${state.highlights.length} highlight(s), ${state.bookmarks.length} bookmark(s). ` +
          "Anchored by quoted text, so they survive a rebuild of the documents.",
      ),
      h(
        "div",
        { style: "display:flex;gap:8px;margin-bottom:24px" },
        h(
          "button",
          {
            class: "btn",
            onclick: () => {
              void navigator.clipboard
                .writeText(exportMarkdown(titleOf))
                .then(() => toast("Notes copied as markdown"));
            },
          },
          "Export markdown",
        ),
        h(
          "button",
          {
            class: "btn",
            onclick: () => {
              if (!confirm("Delete every highlight and bookmark?")) return;
              state.highlights = [];
              state.bookmarks = [];
              save();
              paint();
            },
          },
          "Clear all",
        ),
      ),
      body,
    ),
  );
}

/* ── checkpoints ───────────────────────────────────────────────── */

/**
 * The eight self-test questions from `00-reading-path.md`, as flashcards. The
 * question comes first and the answer's *location* second — because the point is
 * to find out whether you can answer it, not to read the answer.
 */
export function renderCheckpoints(deps: ViewDeps): void {
  const { corpus, main, rail } = deps;
  clear(main);
  clear(rail);

  const known = corpus.checkpoints.filter((c) => state.checkpoints[c.n]).length;
  const body = h("div");

  for (const c of corpus.checkpoints) {
    const revealed = h("div", { hidden: true });
    revealed.append(
      h(
        "button",
        {
          class: "pop-open",
          style: "margin:0",
          onclick: () => deps.openDoc(c.answerDoc, c.answerAnchor),
        },
        `Answer: ${c.answerLabel} →`,
      ),
    );

    const mark = (ok: boolean) => () => {
      state.checkpoints[c.n] = ok;
      save();
      renderCheckpoints(deps);
    };

    body.append(
      h(
        "div",
        { class: "card", style: "margin-bottom:12px;cursor:default" },
        h(
          "div",
          { class: "stat-l" },
          `Checkpoint ${c.n}`,
          state.checkpoints[c.n]
            ? h(
                "span",
                { style: "color:var(--verify);margin-left:8px" },
                "· known",
              )
            : null,
        ),
        h(
          "p",
          { style: "color:var(--head);font-size:15px;margin:8px 0 12px" },
          c.question,
        ),
        revealed,
        h(
          "div",
          { style: "display:flex;gap:8px;margin-top:12px" },
          h(
            "button",
            {
              class: "btn",
              onclick: (e: Event) => {
                revealed.hidden = false;
                (e.currentTarget as HTMLElement).hidden = true;
              },
            },
            "Reveal location",
          ),
          h("button", { class: "btn", onclick: mark(true) }, "I know this"),
          h("button", { class: "btn", onclick: mark(false) }, "Not yet"),
        ),
      ),
    );
  }

  main.append(
    view(
      h("h2", {}, "Checkpoints"),
      h(
        "p",
        { class: "view-sub" },
        `${known} of ${corpus.checkpoints.length} marked as known. ` +
          "Three of these separate someone who has read the docs from someone who understands the system.",
      ),
      body,
    ),
  );
}

/* ── search results ────────────────────────────────────────────── */

export function renderSearch(query: string, deps: ViewDeps): void {
  const { main, rail } = deps;
  clear(main);
  clear(rail);

  const hits = deps.search.query(query, 80);
  const body = h("div");

  for (const { section } of hits) {
    body.append(
      h(
        "button",
        {
          class: "backlink",
          style: "padding:10px 0",
          onclick: () => deps.openDoc(section.doc, section.anchor),
        },
        h("div", { style: "color:var(--head);font-size:14px" }, section.title),
        h(
          "div",
          {
            style:
              "color:var(--faint);font-size:11.6px;font-family:var(--mono)",
          },
          `${section.doc} · ${section.path || section.docTitle}`,
        ),
      ),
    );
  }

  main.append(
    view(
      h("h2", {}, `Search`),
      h(
        "p",
        { class: "view-sub", role: "status" },
        hits.length
          ? `${hits.length} section(s) match “${query}”.`
          : `Nothing matches “${query}”.`,
      ),
      body,
    ),
  );
}
