def render_report(report: dict) -> str:
    lines = ["# PatchWise CVE Upgrade Report", ""]
    for item in report.get("recommendations", []):
        lines.append(f"## {item['package']}")
        lines.append(f"- Classification: `{item['classification']}`")
        lines.append(f"- Reason: {item['reason']}")
        lines.append("")
    return "\n".join(lines)
