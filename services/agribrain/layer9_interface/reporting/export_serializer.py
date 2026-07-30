import copy
import json
from typing import Dict, Any, List
from layer9_interface.reporting.schemas import InstitutionalReport

def to_dict_normalized(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    elif hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        result = {}
        for field_name in obj.__dataclass_fields__:
            val = getattr(obj, field_name)
            if isinstance(val, list):
                result[field_name] = [to_dict_normalized(x) for x in val]
            elif isinstance(val, dict):
                result[field_name] = {k: to_dict_normalized(v) for k, v in val.items()}
            else:
                result[field_name] = to_dict_normalized(val)
        return result
    return obj

def export_json(report: InstitutionalReport) -> Dict[str, Any]:
    """Returns normalized dictionary representation preserving hashes."""
    # Ensure no mutation of source object
    report_copy = copy.deepcopy(report)
    return to_dict_normalized(report_copy)

def export_markdown(report: InstitutionalReport) -> str:
    """Renders report content into clean Markdown format including disclaimers."""
    lines = [
        f"# {report.report_type.replace('_', ' ').title()} - {report.scope.upper()}",
        f"- **Report Schema Version**: `{report.report_schema_version}`",
        f"- **Report Policy Version**: `{report.report_policy_version}`",
        f"- **Generated At**: `{report.generated_at}`",
        f"- **Report ID**: `{report.report_id}`",
        "",
        "## Performance Metrics & Telemetry",
        f"- **Confidence Score**: `{report.confidence:.2%}`",
        f"- **Uncertainty Range**: `{report.uncertainty:.2%}`",
        f"- **Data Completeness**: `{report.data_completeness:.2%}`",
        "",
        "## Disclaimers & Regulatory Warnings",
    ]
    if report.disclaimers:
        for d in report.disclaimers:
            lines.append(f"- **{d.reason.replace('_', ' ').title()}**: {d.text} (Severity: `{d.severity}`)")
    else:
        lines.append("No active policy warnings or disclaimers.")

    lines.append("")
    lines.append("## Verification Provenance")
    for k, v in report.provenance_hashes.items():
        lines.append(f"- **{k.replace('_', ' ').title()}**: `{v or 'N/A'}`")
    
    return "\n".join(lines)

def export_html(report: InstitutionalReport) -> str:
    """Returns HTML ready string representation."""
    md = export_markdown(report)
    # Simple markdown to html converter line-by-line
    html_lines = ["<html><body>"]
    for line in md.split("\n"):
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            html_lines.append("<br/>")
        else:
            html_lines.append(f"<p>{line}</p>")
    html_lines.append("</body></html>")
    return "\n".join(html_lines)

def export_pdf_payload(report: InstitutionalReport) -> Dict[str, Any]:
    """Generates PDF-ready structured payload with appendix and provenance."""
    # Ensure no mutation of source report
    report_copy = copy.deepcopy(report)
    
    blocks = []
    for k, v in report_copy.metrics.items():
        blocks.append(f"{k}: {v}")
    
    limitations_blocks = list(report_copy.limitations)
    for d in report_copy.disclaimers:
        limitations_blocks.append(f"DISCLAIMER: {d.text}")
        
    appendices = []
    for k, v in report_copy.provenance_hashes.items():
        appendices.append(f"PROVENANCE_{k.upper()}: {v or 'N/A'}")

    return {
        "title": report_copy.report_type.replace('_', ' ').title(),
        "sections": [
            {"heading": "Evidence Summary", "blocks": blocks},
            {"heading": "Uncertainty & Limitations", "blocks": limitations_blocks}
        ],
        "tables": [],
        "appendices": [{"heading": "Cryptographic Auditing & Provenance", "blocks": appendices}]
    }
