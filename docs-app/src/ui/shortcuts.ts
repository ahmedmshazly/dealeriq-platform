import { h } from "../lib/dom.js";

const GROUPS: [string, [string, string][]][] = [
  [
    "Navigate",
    [
      ["⌘K", "Command palette — docs, headings, symbols, files, routes"],
      ["⌘P", "Quick-open a source file"],
      ["/", "Search the handbook"],
      ["n / p", "Next / previous document"],
      ["1 – 9", "Jump to the nth document in the sidebar"],
      ["⌘[ / ⌘]", "Back / forward"],
      ["g then d", "Go to the reading path"],
      ["g then g", "Top of document"],
      ["G", "Bottom of document"],
    ],
  ],
  [
    "Read",
    [
      ["j / k", "Scroll down / up"],
      ["d / u", "Half page down / up"],
      ["⌘F", "Find in page"],
      ["Enter / ⇧Enter", "Next / previous match"],
    ],
  ],
  [
    "Study",
    [
      ["b", "Bookmark the current section"],
      ["h", "Highlight the selection"],
      ["m", "Highlight with a note"],
      ["Select text", "Reveals the annotation toolbar"],
    ],
  ],
  [
    "Views",
    [
      ["s / o", "Toggle the sidebar / outline"],
      ["f", "Focus mode"],
      ["t", "Toggle theme"],
      ["r", "Toggle the reference layer"],
      ["?", "This sheet"],
      ["Esc", "Close the topmost layer"],
    ],
  ],
];

let sheet: HTMLElement | null = null;
let scrim: HTMLElement | null = null;

export const sheetOpen = (): boolean => sheet !== null;

export function toggleShortcuts(): void {
  if (sheet) return closeShortcuts();

  const grid = h("div", { class: "sheet-grid" });
  for (const [group, rows] of GROUPS) {
    grid.append(h("div", { class: "sheet-group" }, group));
    for (const [key, what] of rows) {
      grid.append(
        h(
          "div",
          { class: "sheet-row" },
          h("span", {}, what),
          h("span", { class: "kbd" }, key),
        ),
      );
    }
  }

  sheet = h(
    "div",
    {
      class: "sheet",
      role: "dialog",
      "aria-modal": "true",
      "aria-label": "Keyboard shortcuts",
      tabindex: "-1",
    },
    h("h2", {}, "Keyboard"),
    grid,
  );
  scrim = h("div", { class: "scrim", onclick: closeShortcuts });
  document.body.append(scrim, sheet);
  sheet.focus();
}

export function closeShortcuts(): void {
  sheet?.remove();
  scrim?.remove();
  sheet = null;
  scrim = null;
}
