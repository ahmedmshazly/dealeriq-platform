"""QA-008: fail the build when personal identity or local environment details reach git.

Two categories, deliberately asymmetric, because they are not the same kind of secret:

* Environment (home directory paths, personal mail addresses, LAN hostnames, private
  IPs) is banned everywhere, attribution files included. These are matched by shape
  rather than by value, so this checker and its policy file never have to contain the
  strings they reject.
* Identity (the maintainer's name) is public by design: it is the copyright holder in
  LICENSE. It is allowed, but only in the attribution files named in the policy, so a
  stray byline in a source comment or a runbook still fails.

Files come from `git ls-files`, so anything gitignored (build output, .venv,
node_modules) is out of scope automatically and needs no exclusion list.

Usage:
    uv run python scripts/ci/check_identity_strings.py            # whole worktree
    uv run python scripts/ci/check_identity_strings.py --staged   # pre-commit
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_FILE = REPO_ROOT / "security" / "identity-policy.json"

# Files whose own content is these patterns. Skipping them is not an allowlist decision,
# it is the checker declining to flag its own source.
SELF = {
    "scripts/ci/check_identity_strings.py",
    "security/identity-policy.json",
}

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".zip",
    ".gz",
    ".parquet",
    ".xlsx",
}


def tracked_files(staged: bool) -> list[str]:
    cmd = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
        if staged
        else ["git", "ls-files"]
    )
    out = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def load_policy() -> dict:
    return json.loads(POLICY_FILE.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="check staged changes only")
    args = parser.parse_args()

    policy = load_policy()
    environment = [
        (rule["id"], re.compile(rule["pattern"]), rule["message"]) for rule in policy["environment"]
    ]
    identity = [
        (rule["id"], re.compile(rule["pattern"]), set(rule["allowed_in"]), rule["message"])
        for rule in policy["identity"]
    ]

    # (rule id, path) pairs with a written, dated justification in the policy. Same shape as
    # security/dependency-waivers.json: an exception you can read, not a silent allowance.
    waived = {(w["rule"], w["path"]) for w in policy.get("waivers", [])}

    violations: list[str] = []

    for rel in tracked_files(args.staged):
        if rel in SELF or Path(rel).suffix.lower() in BINARY_SUFFIXES:
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for lineno, line in enumerate(text.splitlines(), 1):
            for rule_id, pattern, message in environment:
                if (rule_id, rel) in waived:
                    continue
                if pattern.search(line):
                    violations.append(f"{rel}:{lineno}: [{rule_id}] {message}")
            for rule_id, pattern, allowed_in, message in identity:
                if rel in allowed_in or (rule_id, rel) in waived:
                    continue
                if pattern.search(line):
                    violations.append(f"{rel}:{lineno}: [{rule_id}] {message}")

    if violations:
        print("Identity gate failed. Remove these before committing:\n", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(
            f"\n{len(violations)} violation(s). "
            "Attribution belongs in the files listed under `identity.allowed_in` in "
            "security/identity-policy.json; local paths and hostnames belong nowhere.",
            file=sys.stderr,
        )
        return 1

    print("Identity gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
