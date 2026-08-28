import type { Corpus, Tier } from "../types.js";
import { clear, h, prefersReducedMotion } from "../lib/dom.js";

/**
 * The link graph, as a force-directed map.
 *
 * 29 nodes and ~200 distinct edges. At that size a Barnes-Hut quadtree is
 * ceremony: an O(n²) repulsion pass is 841 comparisons per tick, which a canvas
 * absorbs without noticing. So the whole simulation is forty lines, and every
 * constant in it is legible.
 *
 * Under `prefers-reduced-motion` the simulation is solved to convergence off
 * screen and drawn once, rather than animating into place.
 */
interface Node {
  id: string;
  title: string;
  tier: Tier;
  r: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  degree: number;
}

interface Edge {
  a: Node;
  b: Node;
  weight: number;
}

const TIER_COLOR: Record<Tier, string> = {
  handbook: "--accent",
  meta: "--accent-2",
  stub: "--faint-2",
  background: "--accent-3",
};

const REPULSION = 5200;
const SPRING = 0.0016;
const CENTER = 0.0022;
const DAMPING = 0.86;

export interface GraphDeps {
  corpus: Corpus;
  main: HTMLElement;
  rail: HTMLElement;
  openDoc: (id: string) => void;
}

let stop: (() => void) | null = null;

export function renderGraph(deps: GraphDeps): void {
  const { corpus, main, rail } = deps;
  stop?.();
  clear(main);
  clear(rail);

  const canvas = h("canvas") as HTMLCanvasElement;
  const tip = h("div", { class: "graph-tip", hidden: true });
  const legend = h(
    "div",
    { class: "graph-legend" },
    ...(Object.keys(TIER_COLOR) as Tier[]).map((t) =>
      h("span", {}, h("i", { style: `background:var(${TIER_COLOR[t]})` }), t),
    ),
  );
  const pct = h("button", {
    class: "graph-pct",
    type: "button",
    title: "Reset to 100%",
    onclick: () => resetView(),
  });
  const ctl = h(
    "div",
    { class: "graph-ctl" },
    pct,
    h(
      "button",
      {
        class: "mermaid-btn",
        title: "Zoom out",
        onclick: () => nudge(1 / 1.3),
      },
      "−",
    ),
    h(
      "button",
      { class: "mermaid-btn", title: "Zoom in", onclick: () => nudge(1.3) },
      "+",
    ),
    h(
      "button",
      { class: "mermaid-btn", title: "Reset view", onclick: () => resetView() },
      "↺",
    ),
  );
  const wrap = h("div", { class: "graph-wrap" }, canvas, tip, legend, ctl);
  main.append(wrap);

  const { nodes, edges } = build(corpus);

  rail.append(
    h(
      "section",
      { class: "rail-section" },
      h("h2", { class: "rail-label" }, "Most referenced"),
      ...[...nodes]
        .sort((a, b) => b.degree - a.degree)
        .slice(0, 10)
        .map((n) =>
          h(
            "button",
            { class: "citelink", onclick: () => deps.openDoc(n.id) },
            h("span", { style: "color:var(--read)", title: n.title }, n.title),
            h("span", {}, String(n.degree)),
          ),
        ),
    ),
  );

  const ctx = canvas.getContext("2d")!;
  let hovered: Node | null = null;
  let raf = 0;
  let dpr = 1;

  /**
   * The camera. The simulation runs in a fixed "world" the size of the viewport
   * at 100%; this maps world → screen. Because every frame is redrawn through
   * it rather than scaling a finished bitmap, the graph is sharp at any zoom -
   * the labels re-hint, the circles re-tessellate.
   */
  const view = { x: 0, y: 0, k: 1 };
  const MIN_K = 0.3;
  const MAX_K = 8;
  const reduced = prefersReducedMotion();
  pct.textContent = "100%";

  const resize = (): void => {
    dpr = Math.min(3, devicePixelRatio || 1);
    canvas.width = wrap.clientWidth * dpr;
    canvas.height = wrap.clientHeight * dpr;
  };
  resize();
  const ro = new ResizeObserver(() => {
    resize();
    if (reduced) draw();
  });
  ro.observe(wrap);

  const toWorld = (sx: number, sy: number): [number, number] => [
    (sx - view.x) / view.k,
    (sy - view.y) / view.k,
  ];

  const setScale = (next: number, sx: number, sy: number): void => {
    const k = Math.min(MAX_K, Math.max(MIN_K, next));
    if (k === view.k) return;
    const [wx, wy] = toWorld(sx, sy);
    view.k = k;
    view.x = sx - wx * k;
    view.y = sy - wy * k;
    pct.textContent = `${Math.round(k * 100)}%`;
    if (k === 1) delete pct.dataset.zoomed;
    else pct.dataset.zoomed = "1";
    if (reduced) draw();
  };

  const nudge = (by: number): void =>
    setScale(view.k * by, wrap.clientWidth / 2, wrap.clientHeight / 2);

  const resetView = (): void => {
    setScale(1, wrap.clientWidth / 2, wrap.clientHeight / 2);
    view.x = 0;
    view.y = 0;
    if (reduced) draw();
  };

  const w = (): number => wrap.clientWidth;
  const hgt = (): number => wrap.clientHeight;

  for (const [i, n] of nodes.entries()) {
    const a = (i / nodes.length) * Math.PI * 2;
    n.x = w() / 2 + Math.cos(a) * 200;
    n.y = hgt() / 2 + Math.sin(a) * 200;
  }

  const tick = (): void => {
    for (const a of nodes) {
      for (const b of nodes) {
        if (a === b) continue;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = Math.max(64, dx * dx + dy * dy);
        const f = REPULSION / d2;
        a.vx += (dx / Math.sqrt(d2)) * f;
        a.vy += (dy / Math.sqrt(d2)) * f;
      }
      a.vx += (w() / 2 - a.x) * CENTER;
      a.vy += (hgt() / 2 - a.y) * CENTER;
    }

    for (const e of edges) {
      const dx = e.b.x - e.a.x;
      const dy = e.b.y - e.a.y;
      const f = SPRING * Math.min(4, e.weight);
      e.a.vx += dx * f;
      e.a.vy += dy * f;
      e.b.vx -= dx * f;
      e.b.vy -= dy * f;
    }

    for (const n of nodes) {
      n.vx *= DAMPING;
      n.vy *= DAMPING;
      n.x = Math.max(n.r + 8, Math.min(w() - n.r - 8, n.x + n.vx));
      n.y = Math.max(n.r + 8, Math.min(hgt() - n.r - 8, n.y + n.vy));
    }
  };

  const css = (name: string): string =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const draw = (): void => {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(
      dpr * view.k,
      0,
      0,
      dpr * view.k,
      dpr * view.x,
      dpr * view.y,
    );

    const near = hovered
      ? new Set(
          edges
            .filter((e) => e.a === hovered || e.b === hovered)
            .flatMap((e) => [e.a.id, e.b.id]),
        )
      : null;

    for (const e of edges) {
      const lit = !near || (near.has(e.a.id) && near.has(e.b.id));
      ctx.globalAlpha = lit ? 0.5 : 0.06;
      ctx.strokeStyle = lit && near ? css("--accent") : css("--border-strong");
      ctx.lineWidth = Math.min(2.4, 0.4 + e.weight * 0.22);
      ctx.beginPath();
      ctx.moveTo(e.a.x, e.a.y);
      ctx.lineTo(e.b.x, e.b.y);
      ctx.stroke();
    }

    ctx.globalAlpha = 1;
    for (const n of nodes) {
      const dim = near && !near.has(n.id);
      ctx.globalAlpha = dim ? 0.22 : 1;

      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fillStyle = css(TIER_COLOR[n.tier]);
      ctx.fill();

      if (n === hovered) {
        ctx.lineWidth = 2;
        ctx.strokeStyle = css("--head");
        ctx.stroke();
      }

      ctx.globalAlpha = dim ? 0.2 : 0.92;
      ctx.fillStyle = css("--text");
      ctx.font = `500 11px ${css("--sans")}`;
      ctx.textAlign = "center";
      ctx.fillText(n.id, n.x, n.y + n.r + 13);
    }
    ctx.globalAlpha = 1;
  };

  /** Screen coords in, node out. The 4 px grab margin is screen-sized, so it
      stays a comfortable target instead of shrinking as you zoom in. */
  const at = (sx: number, sy: number): Node | null => {
    const [x, y] = toWorld(sx, sy);
    return (
      nodes.find((n) => Math.hypot(n.x - x, n.y - y) <= n.r + 4 / view.k) ??
      null
    );
  };

  let panning = false;
  let moved = false;
  let px = 0;
  let py = 0;

  canvas.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    panning = true;
    moved = false;
    px = e.clientX;
    py = e.clientY;
    canvas.setPointerCapture(e.pointerId);
  });

  canvas.addEventListener("pointermove", (e) => {
    const r = canvas.getBoundingClientRect();

    if (panning) {
      if (Math.hypot(e.clientX - px, e.clientY - py) > 3) moved = true;
      view.x += e.clientX - px;
      view.y += e.clientY - py;
      px = e.clientX;
      py = e.clientY;
      tip.hidden = true;
      canvas.style.cursor = "grabbing";
      if (reduced) draw();
      return;
    }

    hovered = at(e.clientX - r.left, e.clientY - r.top);
    canvas.style.cursor = hovered ? "pointer" : "grab";

    if (hovered) {
      tip.hidden = false;
      tip.textContent = `${hovered.title} · ${hovered.degree} links`;
      tip.style.left = `${e.clientX - r.left + 14}px`;
      tip.style.top = `${e.clientY - r.top + 10}px`;
    } else tip.hidden = true;

    if (reduced) draw();
  });

  const endPan = (): void => {
    panning = false;
    canvas.style.cursor = "grab";
  };
  canvas.addEventListener("pointerup", endPan);
  canvas.addEventListener("pointercancel", endPan);

  // A drag that happened to start on a node must not also open it.
  canvas.addEventListener("click", (e) => {
    if (moved) return;
    const r = canvas.getBoundingClientRect();
    const n = at(e.clientX - r.left, e.clientY - r.top);
    if (n) deps.openDoc(n.id);
  });

  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const r = canvas.getBoundingClientRect();
      setScale(
        view.k * (e.deltaY < 0 ? 1.1 : 1 / 1.1),
        e.clientX - r.left,
        e.clientY - r.top,
      );
    },
    { passive: false },
  );

  canvas.addEventListener("dblclick", () => resetView());
  canvas.style.cursor = "grab";

  if (reduced) {
    for (let i = 0; i < 400; i++) tick();
    draw();
  } else {
    const loop = (): void => {
      tick();
      draw();
      raf = requestAnimationFrame(loop);
    };
    loop();
  }

  stop = () => {
    cancelAnimationFrame(raf);
    ro.disconnect();
    stop = null;
  };
}

function build(corpus: Corpus): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = corpus.docs.map((d) => ({
    id: d.num ?? d.id,
    title: d.title,
    tier: d.tier,
    // Area ∝ word count, so a node's visual weight tracks its reading weight.
    r: 7 + Math.sqrt(d.words) / 9,
    x: 0,
    y: 0,
    vx: 0,
    vy: 0,
    degree: 0,
  }));

  const byDoc = new Map(corpus.docs.map((d, i) => [d.id, nodes[i]]));
  const weights = new Map<string, Edge>();

  for (const d of corpus.docs) {
    const a = byDoc.get(d.id)!;
    for (const l of d.links) {
      if (!l.to || l.to === d.id) continue;
      const b = byDoc.get(l.to);
      if (!b) continue;
      const key = [d.id, l.to].sort().join("→");
      const existing = weights.get(key);
      if (existing) existing.weight++;
      else weights.set(key, { a, b, weight: 1 });
      a.degree++;
      b.degree++;
    }
  }

  return { nodes, edges: [...weights.values()] };
}

export const stopGraph = (): void => stop?.();
