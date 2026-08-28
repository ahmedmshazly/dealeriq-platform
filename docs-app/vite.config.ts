import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

/**
 * Three build targets, one source tree.
 *
 * - default - `dist/`, code-split, for `vite preview` and local checks.
 * - `PACK=1` - `dist/handbook.html`, one self-contained file with every asset,
 *   chunk and font inlined. It must run from `file://` with the network off,
 *   which is why the router is hash-based and nothing is ever `fetch`ed.
 * - `SITE=1` - `../apps/web/public/handbook/`, served at `/handbook/` by Next.js.
 *   Code-split on purpose: the shell stays small and mermaid only loads when needed.
 *
 * `SITE` writes outside its own root, so `emptyOutDir` has to be explicit -
 * and `apps/web/public/handbook/` is gitignored and rebuilt by `npm run docs:site`.
 */
const pack = process.env.PACK === "1";
const site = process.env.SITE === "1";

export default defineConfig({
  base: site ? "/handbook/" : "./",
  publicDir: false,
  plugins: pack ? [viteSingleFile({ removeViteModuleLoader: true })] : [],
  server: {
    port: 5178,
    strictPort: true,
    // The corpus is rebuilt by `npm run index`; watching docs/ from here would
    // race the indexer. Re-run `npm run index` (or restart dev) after editing.
    fs: { allow: [".."] },
  },
  build: {
    outDir: site ? "../apps/web/public/handbook" : "dist",
    emptyOutDir: true,
    target: "es2022",
    // In pack mode every asset becomes a data URI; otherwise keep the defaults
    // so the dev/preview build still code-splits mermaid away from the shell.
    assetsInlineLimit: pack ? Number.MAX_SAFE_INTEGER : 4096,
    cssCodeSplit: !pack,
    chunkSizeWarningLimit: 8000,
    rollupOptions: pack
      ? { output: { inlineDynamicImports: true } }
      : {
          output: {
            manualChunks(id) {
              if (id.includes("node_modules/mermaid")) return "mermaid";
              if (id.includes("generated/code/")) return undefined;
              return undefined;
            },
          },
        },
  },
  define: {
    __PACK__: JSON.stringify(pack),
  },
});
