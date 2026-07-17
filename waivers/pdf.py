"""Render immutable waiver snapshots; never consult mutable profile/site data."""

from io import BytesIO
from pathlib import Path
import re
import unicodedata
from xml.sax.saxutils import escape

import reportlab
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


FONT_REGULAR = "WaiverVera"
FONT_BOLD = "WaiverVeraBold"


class WaiverPDFValidationError(ValueError):
    """Raised when a rendered or stored waiver PDF is not safely readable."""


def _register_fonts():
    fonts = Path(reportlab.__file__).resolve().parent / "fonts"
    try:
        if FONT_REGULAR not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(fonts / "Vera.ttf")))
        if FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(fonts / "VeraBd.ttf")))
        return FONT_REGULAR, FONT_BOLD
    except (OSError, RuntimeError):
        # ReportLab distributions normally bundle Vera. Keep PDF availability if
        # a downstream minimal package removes it.
        return "Helvetica", "Helvetica-Bold"


def humanize(key):
    return str(key).replace("_", " ").strip().title()


def flatten_snapshot(value, prefix=""):
    rows = []
    if isinstance(value, dict):
        for key, nested in value.items():
            label = f"{prefix} / {humanize(key)}" if prefix else humanize(key)
            if isinstance(nested, (dict, list)):
                rows.extend(flatten_snapshot(nested, label))
            else:
                rows.append((label, nested))
    elif isinstance(value, list):
        for index, nested in enumerate(value, start=1):
            label = f"{prefix} / {index}" if prefix else str(index)
            if isinstance(nested, (dict, list)):
                rows.extend(flatten_snapshot(nested, label))
            else:
                rows.append((label, nested))
    else:
        rows.append((prefix or "Value", value))
    return rows


def _paragraph(value, style):
    rendered = "Not provided" if value in (None, "") else str(value)
    return Paragraph(escape(rendered).replace("\n", "<br/>"), style)


def render_waiver_pdf(waiver):
    regular_font, bold_font = _register_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"Signed waiver {waiver.pk}",
        author="Gyminators Gymnastics & Tumbling, Inc.",
    )
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "WaiverBody",
        parent=sample["BodyText"],
        fontName=regular_font,
        fontSize=8.5,
        leading=11,
        spaceAfter=5,
    )
    label = ParagraphStyle(
        "WaiverLabel",
        parent=body,
        fontName=bold_font,
    )
    heading = ParagraphStyle(
        "WaiverHeading",
        parent=sample["Heading2"],
        fontName=bold_font,
        fontSize=13,
        leading=16,
        spaceBefore=10,
        spaceAfter=6,
    )
    title = ParagraphStyle(
        "WaiverTitle",
        parent=heading,
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#057b78"),
    )

    story = [
        Paragraph("Gyminators Gymnastics &amp; Tumbling, Inc.", title),
        Paragraph("Signed Online Waiver", title),
        Spacer(1, 8),
    ]
    signed_iso = waiver.signed_at.isoformat()
    summary = [
        ("Confirmation ID", waiver.pk),
        ("Enrollment type", waiver.get_enrollment_type_display()),
        ("Gymnast status", waiver.get_participant_status_display()),
        ("Camp activity", waiver.activity_name),
        ("Signed timestamp", signed_iso),
        ("Signer", waiver.typed_signer_name),
        ("Signer capacity", waiver.get_signer_capacity_display()),
        ("Pickup verified", "Yes" if waiver.pickup_verified else "Not applicable"),
        ("Explicit agreement accepted", "Yes" if waiver.agreement_accepted else "No"),
        ("Agreement version", waiver.agreement_version),
        ("Agreement SHA-256", waiver.agreement_sha256),
        ("Signature SHA-256", waiver.signature_sha256),
    ]
    summary_table = Table(
        [[_paragraph(name, label), _paragraph(value, body)] for name, value in summary],
        colWidths=(1.65 * inch, 5.15 * inch),
        repeatRows=0,
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9d5ca")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f6f4ef")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([summary_table, Paragraph("Submitted information", heading)])

    snapshot_table = Table(
        [
            [_paragraph(name, label), _paragraph(value, body)]
            for name, value in flatten_snapshot(waiver.details)
        ],
        colWidths=(2.2 * inch, 4.6 * inch),
        repeatRows=0,
    )
    snapshot_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e7e3da")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.extend([snapshot_table, Paragraph("Clause initials", heading)])
    initials_rows = [
        [_paragraph(f"Clause {number}", label), _paragraph(initials, body)]
        for number, initials in waiver.initials.items()
    ]
    initials_table = Table(initials_rows, colWidths=(1.4 * inch, 1.4 * inch))
    initials_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9d5ca")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([initials_table, Paragraph("Exact agreement snapshot", heading)])
    for paragraph in waiver.legal_text_snapshot.split("\n\n"):
        story.append(_paragraph(paragraph, body))

    signature = Image(BytesIO(bytes(waiver.signature_png)))
    signature._restrictSize(6.2 * inch, 1.8 * inch)
    story.append(
        KeepTogether(
            [
                Paragraph("Signature", heading),
                signature,
                Spacer(1, 4),
                _paragraph(
                    f"Signed by {waiver.typed_signer_name} ({waiver.get_signer_capacity_display()}) at {signed_iso}",
                    body,
                ),
            ]
        )
    )
    document.build(story)
    return buffer.getvalue()


def _normalized_extracted_text(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "")).strip()


def _reader_contains_image(reader):
    """Return whether any page contains the embedded handwritten signature image."""
    for page in reader.pages:
        resources = page.get("/Resources")
        if not resources:
            continue
        resources = resources.get_object()
        xobjects = resources.get("/XObject")
        if not xobjects:
            continue
        for reference in xobjects.get_object().values():
            if reference.get_object().get("/Subtype") == "/Image":
                return True
    return False


def validate_waiver_pdf(content, waiver):
    """Parse an artifact and prove it contains the immutable signed snapshot."""
    content = bytes(content or b"")
    if not content.startswith(b"%PDF-") or not content.rstrip().endswith(b"%%EOF"):
        raise WaiverPDFValidationError("The stored artifact is not a complete PDF.")

    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted or len(reader.pages) < 1:
            raise WaiverPDFValidationError("The stored PDF has no readable pages.")
        extracted = _normalized_extracted_text(
            "\n".join(page.extract_text() or "" for page in reader.pages)
        )
        if not _reader_contains_image(reader):
            raise WaiverPDFValidationError(
                "The stored PDF does not contain its signature image."
            )
    except WaiverPDFValidationError:
        raise
    except Exception as exc:
        raise WaiverPDFValidationError("The stored PDF could not be parsed.") from exc

    expected_content = (
        ("confirmation ID", str(waiver.pk)),
        ("agreement version", waiver.agreement_version),
        ("signer name", waiver.typed_signer_name),
        ("signing timestamp", waiver.signed_at.isoformat()),
        ("signature hash", waiver.signature_sha256),
        ("legal agreement", waiver.legal_text_snapshot),
    )
    snapshot_content = []
    for field_label, value in flatten_snapshot(waiver.details):
        snapshot_content.append((f"snapshot label {field_label}", field_label))
        if value not in (None, ""):
            snapshot_content.append((f"snapshot value for {field_label}", str(value)))
    for number, initials in waiver.initials.items():
        snapshot_content.extend(
            (
                (f"initials label for clause {number}", f"Clause {number}"),
                (f"initials for clause {number}", str(initials)),
            )
        )

    for label, expected in (*expected_content, *snapshot_content):
        normalized_expected = _normalized_extracted_text(expected)
        if not normalized_expected or normalized_expected not in extracted:
            raise WaiverPDFValidationError(
                f"The stored PDF does not contain its {label}."
            )

    return reader
