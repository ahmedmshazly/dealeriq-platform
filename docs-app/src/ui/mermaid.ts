import type { MermaidBlock } from "../types.js";
import { $$, h, toast } from "../lib/dom.js";

/**
 * Diagrams.
 *
 * Mermaid is ~2.5 MB - by a wide margin the largest thing this application can
 * load - and only 10 of 29 documents contain a diagram. So it is imported on
 * first sight of a `<figure class="mermaid">` and never before. In the packed
 * single file it is already inlined; the dynamic import simply resolves.
 *
 * Every diagram in this corpus sits beside prose carrying the same information,
 * by the handbook's own rule. So a failure to render is a degradation, not a
 * loss, and it must never take the page down with it.
 */
type MermaidApi = {
  initialize: (cfg: Record<string, unknown>) => void;
  render: (id: string, code: string) => Promise<{ svg: string }>;
};

let api: MermaidApi | null = null;
let loading: Promise<MermaidApi> | null = null;

async function load(): Promise<MermaidApi> {
  loading ??= import("mermaid").then((m) => {
    api = m.default as unknown as MermaidApi;
    return api;
  });
  return loading;
}

const css = (name: string): string =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** Theme mermaid from the live tokens so it re-skins with the rest of the app. */
function themeVars(): Record<string, string | boolean> {
  const dark = document.documentElement.dataset.theme !== "light";
  return {
    // `darkMode` is not cosmetic. Every colour mermaid does *not* receive here
    // is derived from one that it does, and the direction of that derivation is
    // chosen by this flag alone. Leave it false on a dark page and `rowOdd`
    // becomes `lighten(mainBkg, 75)`, near-white, under near-white label text,
    // which is why the ER diagram's odd rows used to render blank.
    darkMode: dark,
    background: css("--surface"),
    primaryColor: css("--raised-2"),
    primaryTextColor: css("--text"),
    primaryBorderColor: css("--border-strong"),
    secondaryColor: css("--panel"),
    tertiaryColor: css("--deep"),
    lineColor: css("--faint"),
    textColor: css("--read"),
    mainBkg: css("--raised-2"),
    nodeBorder: css("--border-strong"),
    nodeTextColor: css("--text"),
    clusterBkg: dark ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.02)",
    clusterBorder: css("--border"),
    titleColor: css("--head"),
    edgeLabelBackground: css("--surface"),
    // erDiagram v11 bands its attribute rows with `rowOdd`/`rowEven`, not the
    // `attributeBackgroundColor*` pair the old renderer read. Both are set: the
    // first is what actually paints, the second keeps any older diagram honest.
    rowOdd: css("--raised-2"),
    rowEven: css("--panel"),
    attributeBackgroundColorOdd: css("--raised-2"),
    attributeBackgroundColorEven: css("--panel"),
    // Sequence-diagram notes default to `#fff5ad` with near-black text, the one
    // hard-coded pair in the base theme that ignores every variable above.
    noteBkgColor: css("--panel"),
    noteTextColor: css("--text"),
    noteBorderColor: css("--border-strong"),
    fontFamily: css("--sans"),
    fontSize: "14px",
  };
}

let seq = 0;

/** One live viewport per figure, so a re-render can tear the old one down. */
const views = new WeakMap<HTMLElement, Viewport>();

export async function renderDiagrams(
  root: HTMLElement,
  blocks: MermaidBlock[],
): Promise<void> {
  const figures = $$<HTMLElement>("figure.mermaid", root);
  if (!figures.length) return;

  const byId = new Map(blocks.map((b) => [b.id, b]));

  let mermaid: MermaidApi;
  try {
    mermaid = await load();
  } catch {
    for (const f of figures)
      fallback(f, byId.get(f.dataset.mermaidId ?? "")?.code ?? "");
    return;
  }

  // `useMaxWidth` everywhere: a diagram must fit its column on arrival, because
  // the corpus's ER diagram is ~2,020 px wide natively and would otherwise open
  // showing its own middle. Zoom and fullscreen are for exploring it after that.
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "base",
    themeVariables: themeVars(),
    flowchart: { curve: "basis", htmlLabels: true, useMaxWidth: true },
    er: { useMaxWidth: true },
    sequence: { useMaxWidth: true },
    class: { useMaxWidth: true },
    state: { useMaxWidth: true },
  });

  for (const fig of figures) {
    const block = byId.get(fig.dataset.mermaidId ?? "");
    const mount = fig.querySelector<HTMLElement>(".mermaid-mount");
    if (!block || !mount) continue;

    // A theme flip re-renders in place. Drop the previous bar or it accretes,
    // and the previous ResizeObserver or it keeps laying out a detached SVG.
    fig.querySelector(".mermaid-bar")?.remove();
    views.get(fig)?.destroy();

    try {
      const { svg } = await mermaid.render(`mmd-svg-${seq++}`, block.code);
      mount.innerHTML = svg;
      const view = viewport(fig, mount);
      views.set(fig, view);
      fig.append(toolbar(fig, block, view));
    } catch (err) {
      fallback(
        fig,
        block.code,
        err instanceof Error ? err.message : String(err),
      );
    }
  }
}

function fallback(fig: HTMLElement, code: string, why?: string): void {
  const mount = fig.querySelector(".mermaid-mount");
  if (!mount) return;
  mount.replaceWith(
    h(
      "div",
      { class: "fence", "data-lang": "mermaid" },
      h("pre", {}, h("code", {}, code)),
      why
        ? h(
            "div",
            { class: "mermaid-kind", style: "padding:8px 14px" },
            `Diagram unavailable: ${why}`,
          )
        : null,
    ),
  );
}

/* ── pan & zoom ────────────────────────────────────────────────── */

const MIN_K = 0.4;
const MAX_K = 12;

interface Viewport {
  zoom: (by: number, at?: { x: number; y: number }) => void;
  reset: () => void;
  scale: () => number;
  onChange: (fn: (k: number) => void) => void;
  destroy: () => void;
}

/**
 * Zoom by re-laying-out the SVG, never by transforming it.
 *
 * `transform: scale()` promotes the element to a composited layer, and the
 * browser rasterises that layer once at its pre-transform size - so scaling up
 * magnifies a bitmap of a ~690 px-wide render of a 2,020 px-wide diagram. It is
 * blurry by construction, and no amount of `will-change` fixes it.
 *
 * Changing `width`/`height` instead is a layout change: the SVG (and the HTML
 * inside its `<foreignObject>` labels) re-renders at the new size, vector-sharp
 * at any magnification. Panning is then just the scroll position of the mount.
 */
function viewport(fig: HTMLElement, mount: HTMLElement): Viewport {
  const svg = mount.querySelector("svg");
  if (!svg) return noopViewport();

  const box = svg.viewBox.baseVal;
  const natural = { w: box.width || 1, h: box.height || 1 };
  const ratio = natural.h / natural.w;

  // Mermaid ships `width="100%"` + `max-width: <natural>px`. Both now fight us.
  svg.removeAttribute("width");
  svg.removeAttribute("height");
  svg.style.maxWidth = "none";
  svg.style.display = "block";

  let k = 1;
  let listener: ((k: number) => void) | null = null;

  /** The width at 100%: fit the column, but never upscale a small diagram. */
  const fitWidth = (): number => {
    const pad = 2 * parseFloat(getComputedStyle(mount).paddingLeft || "0");
    const availW = Math.max(80, mount.clientWidth - pad);
    if (!fig.classList.contains("full")) return Math.min(natural.w, availW);
    const availH = Math.max(80, mount.clientHeight - pad);
    return Math.min(availW, availH / ratio);
  };

  let base = fitWidth();

  const layout = (): void => {
    const w = base * k;
    svg.style.width = `${w}px`;
    svg.style.height = `${w * ratio}px`;
    listener?.(k);
  };

  /** Keep the point under the cursor pinned while the content grows around it. */
  const setScale = (next: number, at?: { x: number; y: number }): void => {
    const clamped = Math.min(MAX_K, Math.max(MIN_K, next));
    if (clamped === k) return;

    const rect = mount.getBoundingClientRect();
    const cx = at ? at.x - rect.left : mount.clientWidth / 2;
    const cy = at ? at.y - rect.top : mount.clientHeight / 2;
    const growth = clamped / k;

    k = clamped;
    layout();

    mount.scrollLeft = (mount.scrollLeft + cx) * growth - cx;
    mount.scrollTop = (mount.scrollTop + cy) * growth - cy;
  };

  // `base` is only meaningful at 100%; re-fitting mid-zoom would fight the user.
  // Entering fullscreen changes what "fit" means, so it re-fits unconditionally.
  const ro = new ResizeObserver(() => {
    const wasFull = fig.classList.contains("full");
    if (k !== 1 && !wasFull) return;
    base = fitWidth();
    layout();
  });
  ro.observe(mount);

  const onWheel = (e: WheelEvent): void => {
    // Only hijack the wheel when the user means to zoom; otherwise the page must
    // keep scrolling under the pointer.
    if (!e.ctrlKey && !e.metaKey && !fig.classList.contains("full")) return;
    e.preventDefault();
    setScale(k * (e.deltaY < 0 ? 1.12 : 1 / 1.12), {
      x: e.clientX,
      y: e.clientY,
    });
  };
  mount.addEventListener("wheel", onWheel, { passive: false });

  let dragging = false;
  let sx = 0;
  let sy = 0;
  let sl = 0;
  let st = 0;

  mount.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    dragging = true;
    sx = e.clientX;
    sy = e.clientY;
    sl = mount.scrollLeft;
    st = mount.scrollTop;
    mount.setPointerCapture(e.pointerId);
  });
  mount.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    mount.scrollLeft = sl - (e.clientX - sx);
    mount.scrollTop = st - (e.clientY - sy);
  });
  const end = (): void => {
    dragging = false;
  };
  mount.addEventListener("pointerup", end);
  mount.addEventListener("pointercancel", end);

  mount.addEventListener("dblclick", (e) => {
    if (k > 1) reset();
    else setScale(2.5, { x: e.clientX, y: e.clientY });
  });

  const reset = (): void => {
    base = fitWidth();
    k = 1;
    layout();
    mount.scrollTo({ left: 0, top: 0 });
  };

  layout();

  return {
    zoom: (by, at) => setScale(k * by, at),
    reset,
    scale: () => k,
    onChange: (fn) => {
      listener = fn;
      fn(k);
    },
    destroy: () => ro.disconnect(),
  };
}

const noopViewport = (): Viewport => ({
  zoom: () => {},
  reset: () => {},
  scale: () => 1,
  onChange: () => {},
  destroy: () => {},
});

/* ── toolbar ───────────────────────────────────────────────────── */

function toolbar(
  fig: HTMLElement,
  block: MermaidBlock,
  view: Viewport,
): HTMLElement {
  const btn = (label: string, title: string, onclick: () => void) =>
    h(
      "button",
      {
        class: "mermaid-btn",
        type: "button",
        title,
        "aria-label": title,
        onclick,
      },
      label,
    );

  const pct = h("button", {
    class: "mermaid-pct",
    type: "button",
    title: "Reset to 100%",
    onclick: () => view.reset(),
  });
  view.onChange((k) => {
    pct.textContent = `${Math.round(k * 100)}%`;
    // `dataset.zoomed = ""` still *sets* the attribute, and `[data-zoomed]`
    // matches an empty value. Only removing it turns the highlight off.
    if (k === 1) delete pct.dataset.zoomed;
    else pct.dataset.zoomed = "1";
  });

  return h(
    "figcaption",
    { class: "mermaid-bar" },
    h(
      "span",
      { class: "mermaid-kind" },
      `${block.kind} · described in the text above`,
    ),
    pct,
    btn("−", "Zoom out", () => view.zoom(1 / 1.25)),
    btn("+", "Zoom in", () => view.zoom(1.25)),
    btn("↺", "Reset view", () => view.reset()),
    btn("⧉", "Copy diagram source", () => {
      void navigator.clipboard
        .writeText(block.code)
        .then(() => toast("Diagram source copied"));
    }),
    btn("⤢", "Toggle fullscreen (Esc to exit)", () => toggleFull(fig, view)),
  );
}

function toggleFull(fig: HTMLElement, view: Viewport): void {
  fig.classList.toggle("full");
  // `fit` means something different inside the overlay, and the mount has not
  // been re-measured yet - wait for the layout the class change just scheduled.
  requestAnimationFrame(() => view.reset());
}

/** Esc closes the topmost layer; a fullscreen diagram is one. */
export const fullDiagramOpen = (): boolean =>
  !!document.querySelector("figure.mermaid.full");

export function closeFullDiagram(): void {
  const fig = document.querySelector<HTMLElement>("figure.mermaid.full");
  if (!fig) return;
  fig.classList.remove("full");
  requestAnimationFrame(() => views.get(fig)?.reset());
}

/** Re-render on theme change: mermaid bakes colours into the SVG at render time. */
export function watchTheme(rerender: () => void): void {
  window.addEventListener("themechange", () => {
    if (document.querySelector("figure.mermaid svg")) rerender();
  });
}
