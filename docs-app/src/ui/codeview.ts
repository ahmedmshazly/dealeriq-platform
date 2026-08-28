import type { Corpus, SourceFile } from "../types.js";
import { $, clear, h, toast } from "../lib/dom.js";
import { codePayload, renderLine } from "../lib/code.js";

export interface CodeDeps {
  corpus: Corpus;
  main: HTMLElement;
  rail: HTMLElement;
  openDoc: (doc: string, anchor?: string | null) => void;
  openCode: (path: string, line?: number) => void;
}

/**
 * The annotated source viewer.
 *
 * The handbook cites 112 files but never a line number, so "open the file" on
 * its own would drop you at line 1 of a 400-line module and call it navigation.
 * The symbol join fixes that: every exported symbol the prose names in backticks
 * gets a marker in the right gutter, and clicking it opens the paragraph that
 * documents it.
 */
export async function renderCode(
  path: string,
  anchor: string | null,
  deps: CodeDeps,
): Promise<void> {
  const { corpus, main, rail } = deps;
  clear(main);
  clear(rail);

  const meta = corpus.files.find((f) => f.path === path);
  if (!meta) {
    main.append(
      h(
        "div",
        { class: "view" },
        h("h2", {}, "Not indexed"),
        h("p", { class: "view-sub" }, path),
      ),
    );
    return;
  }

  const body = h("div", { class: "code-body", id: "prose" });
  main.append(h("div", { class: "code" }, head(meta, deps), body));

  body.append(h("div", { class: "pal-empty" }, "Loading source…"));

  const payload = await codePayload();
  const file = payload.files[path];
  clear(body);

  if (!file) {
    body.append(h("div", { class: "pal-empty" }, "No snapshot for this file."));
    return;
  }

  const annotatedLines = new Set(Object.keys(file.annotations).map(Number));
  const label = labeller(corpus);

  file.lines.forEach((text, i) => {
    const n = i + 1;
    const row = h("div", { class: "cl", id: `L${n}`, "data-line": n });

    row.append(h("span", { class: "cl-n" }, String(n)));

    if (annotatedLines.has(n)) {
      const targets = file.annotations[String(n)];
      row.append(
        h(
          "button",
          {
            class: "cl-mark",
            title: `Documented in ${targets.map(label).join(", ")}`,
            "aria-label": `Documented in ${targets.length} place(s). Open.`,
            onclick: () => {
              const [doc, sec] = targets[0].split("#");
              deps.openDoc(doc, sec ?? null);
            },
          },
          "●",
        ),
      );
    } else {
      row.append(h("span", { class: "cl-mark" }));
    }

    const src = h("span", { class: "cl-src" });
    src.append(renderLine(text, file.runs[i] ?? "", payload.palette));
    row.append(src);
    body.append(row);
  });

  rail.append(symbolOutline(meta, deps));
  if (meta.citedBy.length) rail.append(citedBy(meta, deps));

  if (anchor?.startsWith("L")) focusLine(main, Number(anchor.slice(1)));
}

/**
 * `05#srclibdbarticlests--collection-articlesslug` → `05 § src/lib/db/articles.ts`.
 *
 * Annotations store slugs because that is what the router needs. A slug is not a
 * label — GitHub's rules strip the punctuation that made the heading legible —
 * so resolve it back to the heading's own text before showing it to anyone.
 */
function labeller(corpus: Corpus): (target: string) => string {
  const headings = new Map<string, Map<string, string>>();
  for (const d of corpus.docs) {
    headings.set(d.id, new Map(d.headings.map((x) => [x.slug, x.text])));
  }
  return (target) => {
    const [docId, slug] = target.split("#");
    const doc = corpus.docs.find((d) => d.id === docId);
    const name = doc?.num ?? doc?.title ?? docId;
    const heading = slug ? headings.get(docId)?.get(slug) : undefined;
    return heading ? `${name} § ${heading}` : name;
  };
}

function head(meta: SourceFile, deps: CodeDeps): HTMLElement {
  return h(
    "header",
    { class: "code-head" },
    h("span", { class: "code-path" }, meta.path),
    h("span", { class: "chip" }, meta.lang),
    h("span", { class: "chip" }, `${meta.loc} lines`),
    meta.citedBy.length
      ? h("span", { class: "chip chip-ok" }, `cited by ${meta.citedBy.length}`)
      : h("span", { class: "chip chip-warn" }, "undocumented"),
    h("span", { style: "flex:1" }),
    h(
      "button",
      {
        class: "btn",
        onclick: () => {
          const payload = deps.corpus.files.find((f) => f.path === meta.path);
          void navigator.clipboard
            .writeText(payload?.path ?? meta.path)
            .then(() => toast("Path copied"));
        },
      },
      "Copy path",
    ),
  );
}

function symbolOutline(meta: SourceFile, deps: CodeDeps): HTMLElement {
  const section = h(
    "section",
    { class: "rail-section" },
    h("h2", { class: "rail-label" }, `Exports · ${meta.symbols.length}`),
  );

  if (!meta.symbols.length) {
    section.append(
      h(
        "p",
        { style: "color:var(--faint);font-size:12.5px" },
        "No exported symbols.",
      ),
    );
    return section;
  }

  for (const s of meta.symbols) {
    section.append(
      h(
        "button",
        {
          class: "citelink",
          title: s.signature,
          onclick: () => deps.openCode(meta.path, s.line),
        },
        h(
          "span",
          {
            style: s.citedBy.length
              ? "color:var(--accent-2)"
              : "color:var(--read)",
          },
          s.name,
        ),
        h("span", {}, `${s.line}`),
      ),
    );
  }
  return section;
}

function citedBy(meta: SourceFile, deps: CodeDeps): HTMLElement {
  const section = h(
    "section",
    { class: "rail-section" },
    h("h2", { class: "rail-label" }, "Documented in"),
  );
  for (const docId of meta.citedBy) {
    const doc = deps.corpus.docs.find((d) => d.id === docId);
    section.append(
      h(
        "button",
        { class: "backlink", onclick: () => deps.openDoc(docId) },
        doc?.title ?? docId,
      ),
    );
  }
  return section;
}

function focusLine(main: HTMLElement, n: number): void {
  requestAnimationFrame(() => {
    const row = $<HTMLElement>(`[data-line="${n}"]`, main);
    if (!row) return;
    row.classList.add("hit");
    const body = row.parentElement!;
    body.scrollTo({
      top: row.offsetTop - body.clientHeight * 0.3,
      behavior: "auto",
    });
  });
}
