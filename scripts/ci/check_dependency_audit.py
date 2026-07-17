"""QA-007: run pip-audit and npm audit for real, cross-reference every reported finding against
security/dependency-waivers.json, and fail (non-zero exit) on anything not explicitly waived.
Replaces the `pip-audit ... || true` / `npm audit ... || true` no-ops in CI -- those steps ran
but could never actually fail the build; this script is what makes the gate real.

Usage: uv run python scripts/check_dependency_audit.py
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WAIVERS_FILE = REPO_ROOT / "security" / "dependency-waivers.json"

GHSA_RE = re.compile(r"GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}")


def load_waivers() -> dict[str, dict[str, str]]:
    waivers = json.loads(WAIVERS_FILE.read_text())
    return {w["id"]: w for w in waivers}


def run_pip_audit() -> list[dict[str, str]]:
    """Returns a list of {id, package} for every real (non-local, non-empty) finding."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "pip-audit",
            "pip-audit",
            "--format",
            "json",
            "--progress-spinner",
            "off",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # pip-audit exits non-zero when it finds vulnerabilities -- that's expected, not a tool
    # failure; only a missing/unparsable report is a real error.
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("pip-audit did not return parsable JSON:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise

    findings = []
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []) or []:
            findings.append({"id": vuln["id"], "package": dep["name"]})
    return findings


def run_npm_audit() -> list[dict[str, str]]:
    """Returns a list of {id, package} for every real finding, one per GHSA id found in each
    vulnerable package's `via` advisory entries."""
    result = subprocess.run(
        ["npm", "audit", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("npm audit did not return parsable JSON:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise

    findings = []
    for package, info in data.get("vulnerabilities", {}).items():
        for via in info.get("via", []):
            if not isinstance(via, dict):
                continue  # a bare string here just names another affected package, not an advisory
            url = via.get("url", "")
            match = GHSA_RE.search(url)
            if match:
                findings.append({"id": match.group(0), "package": package})
    return findings


def main() -> int:
    waivers = load_waivers()
    findings = run_pip_audit() + run_npm_audit()

    unwaived = [f for f in findings if f["id"] not in waivers]

    print(f"Dependency audit: {len(findings)} finding(s), {len(waivers)} waiver(s) on file.")
    if unwaived:
        print("\nUNWAIVED findings (these block the build):")
        for f in unwaived:
            print(f"  {f['id']}  ({f['package']})")
        print(
            f"\nEither fix the dependency, or add a reviewed entry to "
            f"{WAIVERS_FILE.relative_to(REPO_ROOT)} with a real reason and re-review date."
        )
        return 1

    if findings:
        print("\nAll findings are covered by a reviewed waiver:")
        for f in findings:
            w = waivers[f["id"]]
            print(f"  {f['id']}  ({f['package']}) -- waived until {w['re_review_by']}")
    else:
        print("No vulnerabilities found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
