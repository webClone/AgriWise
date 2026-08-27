"""Create a review copy of the MESIA/ASMAE patent specification.

The source document is preserved.  This transformer adds only the maturity and
action-authority clarifications requested by the scientific audit, plus an
updateable Word table of contents.
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SOURCE = Path(r"C:\Users\E-C\Desktop\ASMAE_MESIA_Patent_Master_Specification_V1.docx")
OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "deliverables"
    / "ASMAE_MESIA_Patent_Master_Specification_V1_revised.docx"
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML = "http://www.w3.org/XML/1998/namespace"


def qn(local: str) -> str:
    return f"{{{W}}}{local}"


def register_namespaces(xml_bytes: bytes) -> None:
    """Retain the document's namespace prefixes when ElementTree serializes."""

    for _event, item in ET.iterparse(io.BytesIO(xml_bytes), events=("start-ns",)):
        prefix, uri = item
        if prefix not in {"xml", "xmlns"}:
            ET.register_namespace(prefix or "", uri)


def paragraph(text: str, style: str | None = None, *, bold: bool = False) -> ET.Element:
    node = ET.Element(qn("p"))
    if style:
        props = ET.SubElement(node, qn("pPr"))
        ET.SubElement(props, qn("pStyle"), {qn("val"): style})
    run = ET.SubElement(node, qn("r"))
    if bold:
        run_props = ET.SubElement(run, qn("rPr"))
        ET.SubElement(run_props, qn("b"))
    text_node = ET.SubElement(run, qn("t"))
    text_node.set(f"{{{XML}}}space", "preserve")
    text_node.text = text
    return node


def toc_field() -> ET.Element:
    node = ET.Element(qn("p"))
    run = ET.SubElement(node, qn("r"))
    ET.SubElement(run, qn("fldChar"), {qn("fldCharType"): "begin", qn("dirty"): "true"})
    instruction_run = ET.SubElement(node, qn("r"))
    instruction = ET.SubElement(instruction_run, qn("instrText"))
    instruction.set(f"{{{XML}}}space", "preserve")
    instruction.text = ' TOC \\o "1-3" \\h \\z \\u '
    separate_run = ET.SubElement(node, qn("r"))
    ET.SubElement(separate_run, qn("fldChar"), {qn("fldCharType"): "separate"})
    fallback_run = ET.SubElement(node, qn("r"))
    fallback = ET.SubElement(fallback_run, qn("t"))
    fallback.text = "Update this field in Word to populate the clickable table of contents."
    end_run = ET.SubElement(node, qn("r"))
    ET.SubElement(end_run, qn("fldChar"), {qn("fldCharType"): "end"})
    return node


def table(rows: list[list[str]]) -> ET.Element:
    node = ET.Element(qn("tbl"))
    props = ET.SubElement(node, qn("tblPr"))
    ET.SubElement(props, qn("tblStyle"), {qn("val"): "TableGrid"})
    ET.SubElement(props, qn("tblW"), {qn("w"): "0", qn("type"): "auto"})
    grid = ET.SubElement(node, qn("tblGrid"))
    for width in (2400, 2400, 4800):
        ET.SubElement(grid, qn("gridCol"), {qn("w"): str(width)})

    for row_index, values in enumerate(rows):
        tr = ET.SubElement(node, qn("tr"))
        if row_index == 0:
            tr_props = ET.SubElement(tr, qn("trPr"))
            ET.SubElement(tr_props, qn("tblHeader"), {qn("val"): "true"})
        for column_index, value in enumerate(values):
            cell = ET.SubElement(tr, qn("tc"))
            cell_props = ET.SubElement(cell, qn("tcPr"))
            width = (2400, 2400, 4800)[column_index]
            ET.SubElement(
                cell_props,
                qn("tcW"),
                {qn("w"): str(width), qn("type"): "dxa"},
            )
            cell.append(paragraph(value, bold=row_index == 0))
    return node


def text_of(node: ET.Element) -> str:
    return "".join(part.text or "" for part in node.findall(f".//{qn('t')}"))


def insert_after(body: ET.Element, anchor_prefix: str, nodes: list[ET.Element]) -> None:
    children = list(body)
    for index, child in enumerate(children):
        if child.tag == qn("p") and text_of(child).startswith(anchor_prefix):
            for offset, node in enumerate(nodes, start=1):
                body.insert(index + offset, node)
            return
    raise ValueError(f"document anchor not found: {anchor_prefix}")


def insert_before(body: ET.Element, anchor_prefix: str, nodes: list[ET.Element]) -> None:
    children = list(body)
    for index, child in enumerate(children):
        if child.tag == qn("p") and text_of(child).startswith(anchor_prefix):
            for offset, node in enumerate(nodes):
                body.insert(index + offset, node)
            return
    raise ValueError(f"document anchor not found: {anchor_prefix}")


def revise_document(document_xml: bytes) -> bytes:
    register_namespaces(document_xml)
    root = ET.fromstring(document_xml)
    body = root.find(qn("body"))
    if body is None:
        raise ValueError("Word document has no body")
    if any("Implementation Status Matrix" in text_of(p) for p in body.findall(qn("p"))):
        raise ValueError("source already contains the audit revision")

    insert_before(
        body,
        "0. Drafting Status and Legal Position",
        [paragraph("Table of Contents", "Heading1"), toc_field()],
    )

    status_rows = [
        ["Capability", "Implementation status", "Boundary represented by this draft"],
        [
            "Current AgriBrain/ASMAE software",
            "TRANSITION FOUNDATION",
            "Diagnostic and shadow-development foundation. It is not certified for unrestricted farmer prescriptions or machine execution.",
        ],
        [
            "Scientific state S[t] = (X, Z, H, M, U)",
            "TRANSITION FOUNDATION",
            "The current system has partial X/H/M/U contracts and shared belief identity; a unified latent Z and complete Agricultural World Model are not implemented.",
        ],
        [
            "MESIA hardware and live electromagnetic acquisition",
            "TARGET — NOT IMPLEMENTED",
            "Claim-development architecture requiring real hardware, geometry, calibration, observations and validation. No simulated MESIA observation is evidence of implementation.",
        ],
        [
            "Agricultural World Model",
            "TARGET R4 — NOT IMPLEMENTED",
            "Optional future capability. Existing worldline and belief stores are foundations, not the completed World Model.",
        ],
        [
            "Counterfactual candidate generation and action selection",
            "TARGET R5 / TRANSITION GATE",
            "L7 candidate generation and L8 sole action selection are the target. Current action-shaped L3–L6 outputs remain internal shadow material unless promoted through exact lineage authorization.",
        ],
        [
            "Omega research architecture",
            "RESEARCH R7 — NOT IMPLEMENTED",
            "Research target only; it is not an operational capability or an implementation certificate.",
        ],
        [
            "Farmer-facing prescriptions and machine execution",
            "NOT VALIDATED OPERATIONAL",
            "Must fail closed unless an exact L8 authorization envelope binds the belief, tribunal verdict, selected manifest entries, policy snapshot and final execution plan.",
        ],
    ]
    insert_after(
        body,
        "The technical substance is grounded primarily",
        [
            paragraph("0.1 Implementation Status Matrix", "Heading2"),
            paragraph(
                "Status terms used below are explicit: CURRENT IMPLEMENTED describes verified present software; TRANSITION FOUNDATION describes migration scaffolding; TARGET describes planned architecture; NOT IMPLEMENTED identifies absent capability; and VALIDATED OPERATIONAL requires separate end-to-end evidence. Patent-claim language is not proof of implementation maturity."
            ),
            table(status_rows),
        ],
    )

    insert_after(
        body,
        "The ASMAE posterior may be supplied to an agricultural world model",
        [
            paragraph("19.1 Target Action-Authority Boundary", "Heading2"),
            paragraph(
                "In the target architecture, Layers 2 through 5 produce state, hypothesis, mechanism, response-parameter and measurement-request evidence. Layer 7 generates counterfactual candidates. Layer 8 alone selects, abstains from, or requests confirmation for an action. Layer 6 supplies feasibility constraints before selection and/or audits execution feasibility after selection; it does not independently create a farmer-facing intervention outside the L8 authorization boundary."
            ),
            paragraph(
                "Any selected action must be bound to the exact input belief, causal-tribunal verdict, selected influence-manifest entries and manifest hash, policy snapshot, L8 output and final execution plan. Diagnostic confidence, a model estimate, a cached language-model interpretation, or an upstream rate cannot substitute for that lineage."
            ),
            paragraph(
                "This allocation is a target and transition-safety boundary, not a statement that the full counterfactual planner, World Model, MESIA system or unrestricted execution path is currently operational. Until separately validated, external prescription and machine-execution surfaces remain fail-closed."
            ),
        ],
    )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def revise_settings(settings_xml: bytes) -> bytes:
    register_namespaces(settings_xml)
    root = ET.fromstring(settings_xml)
    update = root.find(qn("updateFields"))
    if update is None:
        update = ET.SubElement(root, qn("updateFields"))
    update.set(qn("val"), "true")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp.docx")
    shutil.copyfile(SOURCE, temporary)
    with zipfile.ZipFile(SOURCE, "r") as source_zip, zipfile.ZipFile(
        temporary, "w", zipfile.ZIP_DEFLATED
    ) as output_zip:
        for item in source_zip.infolist():
            payload = source_zip.read(item.filename)
            if item.filename == "word/document.xml":
                payload = revise_document(payload)
            elif item.filename == "word/settings.xml":
                payload = revise_settings(payload)
            output_zip.writestr(item, payload)
    temporary.replace(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
