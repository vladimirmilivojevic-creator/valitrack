"""Validation summary report as a PDF (ReportLab).

The function gets plain data and returns bytes. It knows nothing about the database,
so it is easy to test: the tests build the PDF and read the text back.
"""

import io
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#14171A")
GREY = colors.HexColor("#4D4D4D")
RULE = colors.HexColor("#DAD6D0")
SOFT = colors.HexColor("#F3F1EE")
RED = colors.HexColor("#C60C30")

_base = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=_base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10.5, textColor=GREY)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8, leading=10)
CELL_HEAD = ParagraphStyle("cellhead", parent=CELL, fontName="Helvetica-Bold", textColor=INK)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=13, leading=17, spaceBefore=14, spaceAfter=6)
TITLE = ParagraphStyle("title", parent=BODY, fontName="Helvetica-Bold", fontSize=24, leading=28, spaceAfter=4)
SUBTITLE = ParagraphStyle("subtitle", parent=BODY, fontSize=12, leading=16, textColor=GREY)


def _p(text, style=BODY) -> Paragraph:
    return Paragraph(escape("" if text is None else str(text)), style)


def _table(header: list[str], rows: list[list], widths: list[float]) -> Table:
    data = [[_p(h, CELL_HEAD) for h in header]]
    for row in rows:
        data.append([_p(c, CELL) for c in row])
    table = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), SOFT),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    table.setStyle(TableStyle(style))
    return table


def _key_value(rows: list[tuple[str, str]], widths=(45 * mm, 125 * mm)) -> Table:
    table = Table([[_p(k, CELL_HEAD), _p(v, CELL)] for k, v in rows], colWidths=list(widths))
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


class _NumberedCanvas(canvas.Canvas):
    """Canvas that knows the total number of pages, for the footer "Page x of y"."""

    footer_text = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages: list[dict] = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._draw_chrome(total)
            super().showPage()
        super().save()

    def _draw_chrome(self, total: int) -> None:
        width, height = A4
        self.setStrokeColor(RED)
        self.setLineWidth(2)
        self.line(20 * mm, height - 14 * mm, 40 * mm, height - 14 * mm)
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(INK)
        self.drawString(20 * mm, height - 11 * mm, "ValiTrack")
        self.setFont("Helvetica", 8)
        self.setFillColor(GREY)
        self.drawRightString(width - 20 * mm, height - 11 * mm, self.footer_text.split("|")[0])
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(20 * mm, 14 * mm, width - 20 * mm, 14 * mm)
        self.drawString(20 * mm, 9 * mm, self.footer_text.split("|")[-1])
        self.drawRightString(width - 20 * mm, 9 * mm, f"Page {self._pageNumber} of {total}")


def _canvas_with(footer: str):
    class Canvas(_NumberedCanvas):
        footer_text = footer

    return Canvas


def build_report_pdf(data: dict) -> bytes:
    app, version = data["application"], data["version"]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=20 * mm,
        title=f"Validation summary report {data['doc_number']}", author="ValiTrack",
    )
    story: list = []

    # ---- cover
    story += [Spacer(1, 30 * mm), _p("Validation Summary Report", TITLE),
              _p(f"{app['name']}, version {version['version']}", SUBTITLE), Spacer(1, 10 * mm)]
    status_text = ("All release gate checks for testing passed." if data["gate_ready"]
                   else "The release gate is NOT open. This is a draft.")
    story.append(_key_value([
        ("Document number", data["doc_number"]),
        ("Application", f"{app['name']} ({app['code']})"),
        ("Version", f"{version['version']} ({version['status'].replace('_', ' ')})"),
        ("Prepared by", data["generated_by"]),
        ("Generated", data["generated_at"]),
        ("Conclusion", status_text),
        ("State fingerprint", data["state_hash"]),
    ]))
    story += [Spacer(1, 8 * mm), _p(
        "This report was generated from the records in ValiTrack. The fingerprint is a SHA-256 hash of the "
        "approved requirements, the latest test results and the deviations. If any of them changes, the "
        "fingerprint changes and the report is no longer valid.", SMALL), PageBreak()]

    # ---- 1 purpose and scope
    story += [_p("1. Purpose and scope", H1), _p(
        f"This report summarises the validation of {app['name']} version {version['version']} for its intended "
        "use. It shows what was required, how the risk was judged, which tests were executed, what went wrong "
        "and who signed.")]
    if version.get("change"):
        c = version["change"]
        story.append(_p(f"The version is part of change request {c['code']} ({c['title']}), "
                        f"type {c['type'].replace('_', ' ')}, risk {c['risk_level'] or 'not assessed'}."))

    # ---- 2 system description
    story += [_p("2. System description", H1), _key_value([
        ("Vendor", app["vendor"]), ("Business owner", f"{app['owner']} ({app['department']})"),
        ("Intended use", app["intended_use"]),
        ("GAMP 5 category", f"{app['gamp_category']} - {app['gamp_name']}"),
        ("Intended-use risk", app["risk_class"]),
    ])]

    # ---- 3 approach
    story += [_p("3. Validation approach", H1), _p(app["approach"])]

    # ---- 4 requirements and risk
    story += [_p("4. Requirements and risk assessment", H1), _p(
        "Risk = severity x probability x detectability, each rated 1 to 3. RPN 12 or more is high, "
        "6 to 11 medium, below 6 low.", SMALL), Spacer(1, 2 * mm)]
    rows = [[r["code"], r["title"], f"{r['severity']}/{r['probability']}/{r['detectability']}",
             r["rpn"], (r["risk_level"] or "n/a").upper(), r["tests"] or "none"] for r in data["requirements"]]
    story.append(_table(["ID", "Requirement", "S/P/D", "RPN", "Risk", "Tests"], rows,
                        [17 * mm, 77 * mm, 17 * mm, 11 * mm, 15 * mm, 33 * mm]))

    # ---- 5 traceability / execution
    story += [_p("5. Test execution", H1), _p(
        "Latest completed run of each test on this version. IQ checks the installation, OQ the functions, "
        "PQ the real process.", SMALL), Spacer(1, 2 * mm)]
    rows = [[t["code"], t["test_type"], t["title"], t["result_text"], t["executed_by"] or "-",
             t["completed_at"] or "-", t["reviewed_by"] or "-"] for t in data["tests"]]
    story.append(_table(["Test", "Type", "Title", "Result", "Executed by", "Date", "Reviewed by"], rows,
                        [15 * mm, 10 * mm, 52 * mm, 18 * mm, 26 * mm, 22 * mm, 27 * mm]))
    totals = data["totals"]
    story += [Spacer(1, 3 * mm), _p(
        f"{totals['tests']} tests: {totals['passed']} passed, {totals['failed']} failed, "
        f"{totals['blocked']} blocked, {totals['not_run']} not executed. "
        f"Requirements covered by an approved test: {totals['covered']} of {totals['requirements']}.")]

    # ---- 6 deviations
    story.append(_p("6. Deviations and corrective actions", H1))
    if data["deviations"]:
        rows = [[d["code"], d["title"], d["severity"], d["status"], d["root_cause"] or "-",
                 d["corrective_action"] or "-"] for d in data["deviations"]]
        story.append(_table(["ID", "Title", "Severity", "Status", "Root cause", "Corrective action"], rows,
                            [16 * mm, 40 * mm, 15 * mm, 17 * mm, 41 * mm, 41 * mm]))
    else:
        story.append(_p("No deviations were raised for this version."))

    # ---- 7 gate
    story.append(_p("7. Release gate", H1))
    rows = [[("PASS" if c["passed"] else "OPEN"), c["label"], c["detail"]] for c in data["gate"]]
    story.append(_table(["Result", "Check", "Detail"], rows, [15 * mm, 55 * mm, 100 * mm]))
    story += [Spacer(1, 3 * mm), _p(data["conclusion"])]

    # ---- 8 signatures
    story.append(_p("8. Electronic signature register", H1))
    story.append(_p("All signatures on the records that belong to this version, at the time of generation. "
                    "Times are UTC.", SMALL))
    story.append(Spacer(1, 2 * mm))
    if data["signatures"]:
        rows = [[s["when"], s["who"], s["role"], s["meaning"], s["record"], s["hash"]] for s in data["signatures"]]
        story.append(_table(["Time (UTC)", "Signer", "Role", "Meaning", "Record", "Signature hash"], rows,
                            [27 * mm, 26 * mm, 24 * mm, 20 * mm, 45 * mm, 28 * mm]))
    else:
        story.append(_p("No signatures yet."))

    # ---- 9 audit trail
    story.append(_p("9. Audit trail integrity", H1))
    audit = data["audit"]
    story.append(_p(
        f"The audit trail holds {audit['entries']} entries at the time of generation. The hash chain check "
        f"{'passed' if audit['intact'] else 'FAILED'}. Chain head: {audit['head_hash'] or 'empty'}."))

    story.append(Spacer(1, 6 * mm))
    story.append(KeepTogether([_p("Approval", H1), _p(
        "Approval of this report is recorded as an electronic signature in ValiTrack. "
        "The signed copy of this document ends with an approval page.")]))

    footer = f"{data['doc_number']}|{app['name']} {version['version']}  -  fingerprint {data['state_hash'][:16]}"
    doc.build(story, canvasmaker=_canvas_with(footer))
    return buffer.getvalue()


def build_approval_page(info: dict) -> bytes:
    """One page that is added to an approved report: who approved it and the hash of the report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=22 * mm, bottomMargin=20 * mm, title="Approval record", author="ValiTrack")
    story = [_p("Approval record", TITLE), _p(info["doc_number"], SUBTITLE), Spacer(1, 8 * mm),
             _key_value([
                 ("Approved by", f"{info['signer']} ({info['role']})"),
                 ("Meaning", info["meaning"]),
                 ("Signed (UTC)", info["signed_at"]),
                 ("Comment", info.get("comment") or "-"),
                 ("Signature hash", info["signature_hash"]),
                 ("SHA-256 of the report pages", info["document_hash"]),
             ]),
             Spacer(1, 6 * mm),
             _p("The signature was made in ValiTrack after the signer typed the password again. "
                "The hash above identifies the report pages that were approved.", SMALL)]
    doc.build(story, canvasmaker=_canvas_with(f"{info['doc_number']}|Approval record"))
    return buffer.getvalue()


def append_page(pdf: bytes, extra: bytes) -> bytes:
    writer = PdfWriter()
    for source in (pdf, extra):
        for page in PdfReader(io.BytesIO(source)).pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
