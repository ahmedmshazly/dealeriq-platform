/**
 * Hash routing, deliberately.
 *
 * The packed build is a single HTML file opened over `file://`, where there is
 * no server to rewrite paths and the History API cannot push a URL the browser
 * will resolve. A hash route behaves identically under `vite dev` and from the
 * filesystem, so what you test is exactly what you ship.
 *
 *   #/start
 *   #/doc/06#security-rules
 *   #/code/src/middleware.ts#L27
 *   #/graph  #/atlas  #/notes  #/checkpoints  #/search?q=...
 */

export interface Route {
  view:
    | "start"
    | "doc"
    | "code"
    | "graph"
    | "atlas"
    | "notes"
    | "checkpoints"
    | "search";
  /** Doc id, or source path for `code`. */
  id: string;
  /** Heading slug, or `L27` for `code`. */
  anchor: string | null;
  query: string;
}

const START: Route = { view: "start", id: "", anchor: null, query: "" };

export function parse(hash: string): Route {
  const raw = hash.replace(/^#\/?/, "");
  if (!raw) return START;

  const [pathAndQuery, ...rest] = raw.split("#");
  const anchor = rest.length ? decodeURIComponent(rest.join("#")) : null;
  const [path, query = ""] = pathAndQuery.split("?");
  const [view, ...tail] = path.split("/");
  const id = decodeURIComponent(tail.join("/"));

  switch (view) {
    case "doc":
    case "code":
      return id ? { view, id, anchor, query } : START;
    case "graph":
    case "atlas":
    case "notes":
    case "checkpoints":
      return { view, id: "", anchor, query };
    case "search":
      return {
        view: "search",
        id: "",
        anchor: null,
        query: new URLSearchParams(query).get("q") ?? "",
      };
    default:
      return START;
  }
}

export const href = (r: Partial<Route> & { view: Route["view"] }): string => {
  const base = r.id ? `#/${r.view}/${r.id}` : `#/${r.view}`;
  const q = r.query ? `?q=${encodeURIComponent(r.query)}` : "";
  return `${base}${q}${r.anchor ? `#${r.anchor}` : ""}`;
};

export const current = (): Route => parse(location.hash);

export function go(to: string, replace = false): void {
  if (location.hash === to) {
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    return;
  }
  if (replace) history.replaceState(null, "", to);
  else location.hash = to;
}

export const onRoute = (fn: (r: Route) => void): void => {
  window.addEventListener("hashchange", () => fn(current()));
};
