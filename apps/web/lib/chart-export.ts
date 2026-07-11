/** FR-053: export any on-screen chart as PNG, and its underlying data as CSV — both pure
 * client-side (`canvas.toBlob`, `Blob`/`URL.createObjectURL`), no new dependency. Reusable
 * across any Recharts SVG and any tabular data, not coupled to a specific chart. */

function triggerDownload(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function downloadCsv(
  filename: string,
  rows: Array<Record<string, string | number | null>>,
): void {
  if (rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const escape = (value: string | number | null): string => {
    const s = value == null ? "" : String(value);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((h) => escape(row[h])).join(",")),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  triggerDownload(URL.createObjectURL(blob), filename);
}

export async function exportChartAsPng(
  svgElement: SVGSVGElement,
  filename: string,
): Promise<void> {
  const { width, height } = svgElement.getBoundingClientRect();
  const svgString = new XMLSerializer().serializeToString(svgElement);
  const svgUrl = URL.createObjectURL(
    new Blob([svgString], { type: "image/svg+xml;charset=utf-8" }),
  );

  const image = new Image();
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error("Failed to rasterize chart SVG."));
    image.src = svgUrl;
  });
  URL.revokeObjectURL(svgUrl);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D context unavailable.");
  // A white backing fill -- the source SVG has a transparent background, and a PNG dropped into
  // a slide deck or document should never assume a transparent/dark viewer background.
  ctx.fillStyle = "white";
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(image, 0, 0, width, height);

  await new Promise<void>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Failed to encode chart as PNG."));
        return;
      }
      triggerDownload(URL.createObjectURL(blob), filename);
      resolve();
    }, "image/png");
  });
}
