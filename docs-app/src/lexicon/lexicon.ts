/**
 * App-authored technical lexicon for the DealerIQ handbook reader.
 *
 * ⚠ EVERY DEFINITION IN THIS FILE WAS WRITTEN BY THE READER APPLICATION.
 * None of it is extracted from the repository. `docs/glossary.md` is
 * authoritative for product vocabulary; this layer covers general computing
 * terms the glossary omits.
 *
 * If a term here ever contradicts the handbook, the handbook is right.
 * **No entry here may share a name with a glossary term** (`docs:verify`).
 */

export interface LexiconEntry {
  term: string;
  aliases?: string[];
  definition: string;
  /** Optional pointer into the handbook, `docId` or `docId#anchor`. */
  see?: string;
}

export const LEXICON: LexiconEntry[] = [
  {
    term: "JWT",
    aliases: ["JSON Web Token"],
    definition:
      "A signed, self-describing access token. DealerIQ access JWTs are short-lived (≤15 min) and sent as Authorization: Bearer.",
    see: "explanation/security-model",
  },
  {
    term: "Argon2id",
    definition:
      "Password hashing algorithm with a memory-hard KDF. DealerIQ parameters meet the SRS floor (ADR-009).",
    see: "explanation/security-model",
  },
  {
    term: "Alembic",
    definition:
      "SQLAlchemy’s migration tool. Schema changes ship as reviewed revisions only — no auto-create in production (ADR-008).",
    see: "explanation/data-model",
  },
  {
    term: "OpenAPI",
    aliases: ["Swagger"],
    definition:
      "Machine-readable API contract served by FastAPI. The TypeScript client is generated from it; CI fails on drift.",
    see: "reference/api",
  },
  {
    term: "TanStack Query",
    aliases: ["React Query"],
    definition:
      "Client-side data fetching and cache layer used by the Next.js app over the generated OpenAPI client (ADR-014).",
    see: "explanation/architecture",
  },
  {
    term: "uv workspace",
    aliases: ["uv"],
    definition:
      "Python packaging and lockfile tool. DealerIQ uses uv workspaces for apps/api and packages/analytics (ADR-015).",
    see: "getting-started/onboarding",
  },
  {
    term: "npm workspaces",
    definition:
      "Node monorepo layout for apps/web and packages/api-client under one root package.json (ADR-016).",
    see: "explanation/architecture",
  },
  {
    term: "slowapi",
    definition:
      "FastAPI rate-limiting middleware. DealerIQ uses an in-memory fixed-window limiter (ADR-020).",
    see: "explanation/security-model",
  },
  {
    term: "statsforecast",
    definition:
      "Classical forecasting library used for champion selection against Seasonal Naive (ADR-005).",
    see: "explanation/analytics-pipeline",
  },
  {
    term: "STL",
    aliases: ["seasonal-trend decomposition"],
    definition:
      "Seasonal-Trend decomposition using Loess. statsmodels is narrowed to STL only (ADR-018).",
    see: "explanation/analytics-pipeline",
  },
  {
    term: "GESD",
    definition:
      "Generalized Extreme Studentized Deviate — outlier test used in anomaly detection (ADR-017).",
    see: "explanation/analytics-pipeline",
  },
  {
    term: "Kaplan-Meier",
    aliases: ["KM", "survival curve"],
    definition:
      "Non-parametric survival estimator used for unit aging / days-to-sale risk via lifelines (ADR-017).",
    see: "explanation/analytics-pipeline",
  },
  {
    term: "C4 model",
    aliases: ["C4"],
    definition:
      "Four-level software diagrams: Context, Container, Component, Code. DealerIQ’s architecture page uses C4-style Mermaid.",
    see: "explanation/architecture",
  },
  {
    term: "Mermaid",
    definition:
      "Text diagram syntax embedded in Markdown. The handbook reader renders fences; GitHub does too.",
    see: "diagrams/README",
  },
  {
    term: "MailHog",
    definition:
      "Local SMTP catcher used in Docker Compose so digest emails never leave the laptop.",
    see: "runbooks/local-dev",
  },
  {
    term: "pg_dump",
    definition:
      "PostgreSQL logical backup tool. Production durability uses scheduled dumps to S3 (ADR-026).",
    see: "runbooks/durability",
  },
  {
    term: "Content Security Policy",
    aliases: ["CSP"],
    definition:
      "Response header controlling which scripts, styles, and frames may load. Handbook paths may need a relaxed policy for Mermaid.",
    see: "explanation/security-model",
  },
  {
    term: "deny by default",
    aliases: ["deny-by-default"],
    definition:
      "Authorization posture where missing an explicit permission means refuse. UI hiding is never the security boundary.",
    see: "explanation/security-model",
  },
  {
    term: "idempotent",
    definition:
      "Running an operation twice has the same effect as running it once — the property that makes safe retries possible.",
  },
  {
    term: "flake",
    aliases: ["flaky"],
    definition:
      "A test that passes and fails on the same code, usually from races, clocks, or shared mutable state.",
  },
];

/** Longest first, so multi-word terms win over shorter overlaps. */
export const LEXICON_INDEX: { key: string; entry: LexiconEntry }[] =
  LEXICON.flatMap((e) => [
    { key: e.term, entry: e },
    ...(e.aliases ?? []).map((a) => ({ key: a, entry: e })),
  ]).sort((a, b) => b.key.length - a.key.length);
