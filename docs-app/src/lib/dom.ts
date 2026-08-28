type Attrs = Record<
  string,
  string | number | boolean | null | undefined | EventListener
>;
type Child = Node | string | number | null | undefined | false;

/**
 * A 30-line element factory instead of a framework.
 *
 * The corpus is 62k words across 29 documents. Reconciling a virtual DOM buys
 * nothing at that scale, and hand-built nodes keep every interaction inside a
 * single frame — which is the difference between an application and a web page.
 */
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs?: Attrs,
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);

  for (const [k, v] of Object.entries(attrs ?? {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") {
      el.addEventListener(k.slice(2).toLowerCase(), v as EventListener);
    } else if (k === "html") {
      el.innerHTML = String(v);
    } else if (k === "class") {
      el.className = String(v);
    } else {
      el.setAttribute(k, v === true ? "" : String(v));
    }
  }

  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export const $ = <T extends Element = HTMLElement>(
  sel: string,
  root: ParentNode = document,
) => root.querySelector<T>(sel);
export const $$ = <T extends Element = HTMLElement>(
  sel: string,
  root: ParentNode = document,
) => [...root.querySelectorAll<T>(sel)];

export const clear = (el: Element): void => {
  while (el.firstChild) el.removeChild(el.firstChild);
};

/** SVG needs its own namespace; progress rings and the graph overlay use it. */
export function svg(
  tag: string,
  attrs: Record<string, string | number>,
): SVGElement {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  return el;
}

export const escapeHtml = (s: string): string =>
  s.replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!,
  );

let toastTimer: number | undefined;
export function toast(message: string): void {
  document.querySelector(".toast")?.remove();
  const el = h("div", { class: "toast", role: "status" }, message);
  document.body.append(el);
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => el.remove(), 1900);
}

export const prefersReducedMotion = (): boolean =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Run a DOM mutation inside a View Transition when the browser has one and the
 * user has not asked for less motion. Falls back to running it immediately.
 */
export function transition(name: string, mutate: () => void): void {
  type Doc = Document & { startViewTransition?: (cb: () => void) => void };
  const doc = document as Doc;
  if (!doc.startViewTransition || prefersReducedMotion()) {
    mutate();
    return;
  }
  document.documentElement.style.setProperty("view-transition-name", name);
  doc.startViewTransition(() => {
    mutate();
  });
}

export const debounce = <A extends unknown[]>(
  fn: (...a: A) => void,
  ms: number,
) => {
  let t: number | undefined;
  return (...a: A): void => {
    clearTimeout(t);
    t = window.setTimeout(() => fn(...a), ms);
  };
};
