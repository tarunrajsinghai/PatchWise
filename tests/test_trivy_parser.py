from pathlib import Path
from patchwise.core.trivy import load_trivy_findings


def test_load_trivy_findings():
    findings = load_trivy_findings(Path("examples/outputs/trivy-results.json"))
    assert len(findings) == 2
    assert findings[0]["vulnerability_id"] == "CVE-2024-1111"
