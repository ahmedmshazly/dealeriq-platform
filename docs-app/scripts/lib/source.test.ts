import { describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { buildSourceIndex, extractSymbols, langOf } from "./source.js";

const ROOT = resolve(import.meta.dirname, "../../..");

describe("langOf", () => {
  it("maps the extensions this corpus actually uses", () => {
    expect(langOf("apps/web/app/page.tsx")).toBe("tsx");
    expect(langOf("apps/api/src/dealeriq_api/main.py")).toBe("python");
    expect(
      langOf("packages/analytics/src/dealeriq_analytics/__init__.py"),
    ).toBe("python");
    expect(langOf(".github/workflows/ci.yml")).toBe("yaml");
    expect(langOf("README.md")).toBe("markdown");
  });

  it("treats unknown extensions as plaintext", () => {
    expect(langOf("firestore.rules")).toBe("plaintext");
  });
});

describe("extractSymbols", () => {
  it("finds the six plain export forms", () => {
    const syms = extractSymbols(
      "a.ts",
      [
        "export const A = 1;",
        "export function f() {}",
        "export async function g(): Promise<void> {}",
        "export class C {}",
        "export type T = string;",
        "export interface I {}",
      ].join("\n"),
    );
    expect(syms.map((s) => [s.name, s.kind, s.line])).toEqual([
      ["A", "const", 1],
      ["f", "function", 2],
      ["g", "function", 3],
      ["C", "class", 4],
      ["T", "type", 5],
      ["I", "interface", 6],
    ]);
  });

  it("unpacks a destructured export", () => {
    const syms = extractSymbols(
      "auth.ts",
      "export const { handlers, auth, signIn, signOut } = NextAuth({",
    );
    expect(syms.map((s) => s.name)).toEqual([
      "handlers",
      "auth",
      "signIn",
      "signOut",
    ]);
  });

  it("resolves `foo as bar` to bar", () => {
    expect(
      extractSymbols("a.ts", "export const { a as b } = x;").map((s) => s.name),
    ).toEqual(["b"]);
  });

  it("names an anonymous default after its module", () => {
    const syms = extractSymbols(
      "src/middleware.ts",
      "export default auth((req) => {\n});",
    );
    expect(syms[0]).toMatchObject({
      name: "middleware",
      kind: "default",
      line: 1,
    });
  });

  it("prefers the named default over the anonymous fallback", () => {
    const syms = extractSymbols(
      "src/x.ts",
      "export default function handler() {}",
    );
    expect(syms[0]).toMatchObject({ name: "handler", kind: "default" });
  });

  it("joins a multi-line signature", () => {
    const syms = extractSymbols(
      "a.ts",
      "export async function POST(\n  req: Request,\n): Promise<Response> {",
    );
    expect(syms[0].signature).toBe(
      "export async function POST( req: Request, ): Promise<Response>",
    );
  });

  it("reads Python defs and classes", () => {
    const syms = extractSymbols(
      "svc.py",
      "def create_app():\n    pass\n\nclass OrderService:\n    pass\n",
    );
    expect(syms.map((s) => [s.name, s.kind])).toEqual([
      ["create_app", "function"],
      ["OrderService", "class"],
    ]);
  });

  it("ignores firestore.rules (not part of DealerIQ)", () => {
    const syms = extractSymbols(
      "firestore.rules",
      "  function isAdmin() {\n    return true;\n  }",
    );
    expect(syms).toEqual([]);
  });
});

describe("the source index", () => {
  const { files } = buildSourceIndex(ROOT);

  it("indexes only tracked source, never build output", () => {
    expect(files.some((f) => f.path.includes("node_modules"))).toBe(false);
    expect(files.some((f) => f.path.includes("__pycache__"))).toBe(false);
    expect(files.some((f) => f.path.includes("public/handbook"))).toBe(false);
  });

  it("includes the FastAPI entrypoint and analytics package", () => {
    expect(
      files.some((f) => f.path === "apps/api/src/dealeriq_api/main.py"),
    ).toBe(true);
    expect(
      files.some((f) =>
        f.path.startsWith("packages/analytics/src/dealeriq_analytics/"),
      ),
    ).toBe(true);
  });

  it("resolves every indexed path on disk", () => {
    const missing = files.filter((f) => !existsSync(join(ROOT, f.path)));
    expect(missing.map((f) => f.path)).toEqual([]);
  });

  it("extracts symbols from Python API modules", () => {
    const main = files.find(
      (f) => f.path === "apps/api/src/dealeriq_api/main.py",
    );
    expect(main).toBeDefined();
    expect(main!.symbols.map((s) => s.name)).toEqual(
      expect.arrayContaining(["create_app"]),
    );
  });
});
