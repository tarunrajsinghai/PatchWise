"""
Dummy feasibility engine.

MVP behavior:
- Reads Trivy JSON.
- Reads constraints YAML.
- Produces a deterministic feasibility.json skeleton.
- Real implementation will patch a temp workspace and run sbt/npm.
"""

from pathlib import Path
import argparse
import json

from patchwise.core.trivy import load_trivy_findings
from patchwise.core.constraints import load_constraints, find_pin, find_upgrade_group


def detect_ecosystem(package: str) -> str:
    if package.startswith("@") or ":" not in package:
        return "npm"
    return "scala"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trivy", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--constraints", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    findings = load_trivy_findings(args.trivy)
    constraints = load_constraints(args.constraints)

    results = []
    for i, f in enumerate(findings, start=1):
        pkg = f["package"]
        fixed = f.get("fixed_version")
        pin = find_pin(constraints, pkg)
        group = find_upgrade_group(constraints, pkg)
        ecosystem = detect_ecosystem(pkg)

        if not fixed:
            status = "no-fixed-version"
            evidence = ["Trivy did not provide a fixed version."]
        elif pin:
            status = "blocked-by-pin"
            evidence = [f"Package is pinned to {pin.get('version')}: {pin.get('reason')}"]
        else:
            status = "needs-implementation"
            evidence = [
                "Dummy project: real implementation should create temp workspace, patch candidate, run strict resolver, build, and tests."
            ]

        results.append({
            "id": f"{ecosystem}-{i:03d}",
            "ecosystem": ecosystem,
            "package": pkg,
            "currentVersion": f.get("installed_version"),
            "candidateVersion": fixed,
            "upgradeGroup": group.get("name") if group else None,
            "status": status,
            "commandsRun": [],
            "evidence": evidence,
            "patchFile": None,
            "logFile": None,
        })

    output = {
        "runId": "dummy-run",
        "source": str(args.trivy),
        "constraints": str(args.constraints),
        "summary": {
            "total": len(results),
            "blocked": sum(1 for r in results if r["status"].startswith("blocked")),
            "needsImplementation": sum(1 for r in results if r["status"] == "needs-implementation"),
        },
        "results": results,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
