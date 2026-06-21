from pathlib import Path
import json


def load_trivy_findings(path: str | Path) -> list[dict]:
    """Flatten a Trivy JSON report into vulnerability items."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    findings: list[dict] = []
    for result in data.get("Results", []):
        for vuln in result.get("Vulnerabilities", []) or []:
            findings.append({
                "vulnerability_id": vuln.get("VulnerabilityID"),
                "package": vuln.get("PkgName"),
                "installed_version": vuln.get("InstalledVersion"),
                "fixed_version": vuln.get("FixedVersion"),
                "severity": vuln.get("Severity"),
                "target": result.get("Target"),
            })
    return findings
