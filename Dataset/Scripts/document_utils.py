"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Document Utility Functions
=========================================================
"""

import random
import uuid
from datetime import datetime

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

from config import *


# ==========================================================
# CREATE DOCUMENT
# ==========================================================

def create_document(title):

    doc = Document()

    section = doc.sections[0]

    section.left_margin = Inches(PAGE_MARGIN)
    section.right_margin = Inches(PAGE_MARGIN)
    section.top_margin = Inches(PAGE_MARGIN)
    section.bottom_margin = Inches(PAGE_MARGIN)

    style = doc.styles["Normal"]

    style.font.name = DEFAULT_FONT
    style._element.rPr.rFonts.set(qn("w:eastAsia"), DEFAULT_FONT)
    style.font.size = Pt(FONT_SIZE)

    add_company_header(doc, title)

    return doc


# ==========================================================
# COMPANY HEADER
# ==========================================================

def add_company_header(doc, title):

    p = doc.add_paragraph()

    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    run = p.add_run(COMPANY_NAME + "\n")
    run.bold = True
    run.font.size = Pt(TITLE_SIZE)

    run = p.add_run(PLANT_NAME + "\n")
    run.bold = True
    run.font.size = Pt(14)

    run = p.add_run(COMPANY_ADDRESS + "\n\n")
    run.font.size = Pt(10)

    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(16)

    doc.add_paragraph()


# ==========================================================
# DOCUMENT METADATA
# ==========================================================

def add_document_metadata(doc, event, document_number):

    doc.add_heading("Document Information", level=1)

    table = doc.add_table(rows=8, cols=2)

    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    data = [

        ("Document UUID", str(uuid.uuid4())[:8].upper()),

        ("Document Number", document_number),

        ("Event ID", event["Event ID"]),

        ("Chain ID", event["Chain_ID"]),

        ("Equipment ID", event["Equipment ID"]),

        ("Department", event["Department"]),

        ("Generated On",
         datetime.now().strftime("%d-%b-%Y %H:%M")),

        ("Confidentiality",
         CONFIDENTIALITY)

    ]

    for row, item in zip(table.rows, data):

        row.cells[0].text = str(item[0])

        row.cells[1].text = str(item[1])

    doc.add_paragraph()


# ==========================================================
# DOCUMENT CONTROL
# ==========================================================

def add_document_control(
        doc,
        document_number,
        issue_date,
        prepared_by,
        approved_by,
        revision
):

    doc.add_heading("Document Control", level=1)

    table = doc.add_table(rows=6, cols=2)

    table.style = "Table Grid"

    values = [

        ("Document Number", document_number),

        ("Issue Date", str(issue_date)),

        ("Revision", revision),

        ("Prepared By", prepared_by),

        ("Approved By", approved_by),

        ("Status", "Approved")

    ]

    for row, item in zip(table.rows, values):

        row.cells[0].text = item[0]

        row.cells[1].text = str(item[1])

    doc.add_paragraph()


# ==========================================================
# EQUIPMENT DETAILS
# ==========================================================

def add_equipment_details(doc, event):

    doc.add_heading("Equipment Details", level=1)

    table = doc.add_table(rows=9, cols=2)

    table.style = "Table Grid"

    values = [

        ("Equipment ID", event["Equipment ID"]),

        ("Equipment Name", event["Equipment Name"]),

        ("Area", event["Area"]),

        ("Department", event["Department"]),

        ("Shift", event["Shift"]),

        ("Reported From", event["Reported_From"]),

        ("Asset Criticality",
         event["Asset Criticality"]),

        ("Failure Category",
         event["Failure Category"]),

        ("Downtime",
         f"{event['Downtime (hrs)']} Hours")

    ]

    for row, item in zip(table.rows, values):

        row.cells[0].text = item[0]

        row.cells[1].text = str(item[1])

    doc.add_paragraph()


# ==========================================================
# SECTION HEADING
# ==========================================================

def add_section(doc, title):

    doc.add_heading(title, level=1)


# ==========================================================
# PARAGRAPH
# ==========================================================

def add_text(doc, text):

    doc.add_paragraph(str(text))


# ==========================================================
# SUMMARY TABLE
# ==========================================================

def add_summary_table(doc, event):

    doc.add_heading("Maintenance Summary", level=1)

    table = doc.add_table(rows=6, cols=2)

    table.style = "Table Grid"

    values = [

        ("Priority", event["Priority"]),

        ("Severity", event["Severity"]),

        ("Status", event["Status"]),

        ("Downtime",
         f"{event['Downtime (hrs)']} Hours"),

        ("Follow-up Required",
         event["Follow-up Required"]),

        ("Asset Criticality",
         event["Asset Criticality"])

    ]

    for row, item in zip(table.rows, values):

        row.cells[0].text = item[0]

        row.cells[1].text = str(item[1])

    doc.add_paragraph()


# ==========================================================
# SPARE PARTS TABLE
# ==========================================================

def add_spare_parts(doc, event):

    doc.add_heading("Spare Parts Used", level=1)

    table = doc.add_table(rows=4, cols=2)

    table.style = "Table Grid"

    table.rows[0].cells[0].text = "Part Name"
    table.rows[0].cells[1].text = "Quantity"

    category = str(event["Failure Category"]).lower()

    if "mechanical" in category:

        parts = [
            ("Bearing", "1"),
            ("Mechanical Seal", "1"),
            ("Grease Cartridge", "2")
        ]

    elif "electrical" in category:

        parts = [
            ("Fuse", "2"),
            ("Terminal Lug", "4"),
            ("Power Cable", "2 m")
        ]

    elif "instrument" in category:

        parts = [
            ("Pressure Transmitter", "1"),
            ("Signal Cable", "3 m"),
            ("Calibration Kit", "1")
        ]

    else:

        parts = [
            ("Standard Spare", "1"),
            ("Lubricant", "1"),
            ("Fastener Kit", "1")
        ]

    for i, part in enumerate(parts):

        table.rows[i + 1].cells[0].text = part[0]

        table.rows[i + 1].cells[1].text = part[1]

    doc.add_paragraph()


# ==========================================================
# INSPECTION CHECKLIST
# ==========================================================
# allow_variation=True occasionally leaves one item unticked,
# so not every report reads as a 100% flawless outcome.

def add_checklist(doc, allow_variation=True):

    doc.add_heading("Maintenance Checklist", level=1)

    checklist = [
        "Lock Out / Tag Out (LOTO) Followed",
        "PPE Worn",
        "Visual Inspection Completed",
        "Lubrication Checked",
        "Leak Inspection Completed",
        "Alignment Verified",
        "Trial Run Successful"
    ]

    skip_index = None

    if allow_variation and random.random() < 0.15:

        skip_index = random.randrange(len(checklist))

    for i, item in enumerate(checklist):

        if i == skip_index:

            doc.add_paragraph(f"☐ {item} — Pending")

        else:

            doc.add_paragraph(f"☑ {item}")

    doc.add_paragraph()


# ==========================================================
# RECOMMENDATION
# ==========================================================

def add_recommendation(doc, text):

    doc.add_heading("Recommendations", level=1)

    doc.add_paragraph(str(text))

    doc.add_paragraph()


# ==========================================================
# LINKED DOCUMENTS
# ==========================================================

def add_linked_documents(doc, docs):

    doc.add_heading("Linked Documents", level=1)

    if len(docs) == 0:

        doc.add_paragraph("No linked documents for this event.")

        return

    for d in docs:

        doc.add_paragraph(
            d,
            style="List Bullet"
        )

    doc.add_paragraph()


# ==========================================================
# APPROVAL
# ==========================================================

def add_signature_block(doc, prepared_by, approved_by):

    doc.add_heading("Approval", level=1)

    table = doc.add_table(rows=2, cols=2)

    table.style = "Table Grid"

    table.rows[0].cells[0].text = "Prepared By"

    table.rows[0].cells[1].text = str(prepared_by)

    table.rows[1].cells[0].text = "Approved By"

    table.rows[1].cells[1].text = str(approved_by)

    doc.add_paragraph()


# ==========================================================
# FOOTER
# ==========================================================

def add_footer(doc):

    footer = doc.sections[0].footer

    para = footer.paragraphs[0]

    para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    para.text = (
        f"{COMPANY_NAME} | "
        f"{CONFIDENTIALITY} | "
        f"Generated by Industrial Knowledge Intelligence"
    )


# ==========================================================
# SAVE DOCUMENT
# ==========================================================

def save_document(doc, filepath):

    add_footer(doc)

    doc.save(filepath)


# ==========================================================
# SIMPLE KEY-VALUE TABLE
# ==========================================================

def add_key_value_table(doc, heading, values):

    doc.add_heading(heading, level=1)

    table = doc.add_table(
        rows=len(values),
        cols=2
    )

    table.style = "Table Grid"

    for row, item in zip(table.rows, values):

        row.cells[0].text = str(item[0])

        row.cells[1].text = str(item[1])

    doc.add_paragraph()


# ==========================================================
# MAINTENANCE HISTORY
# ==========================================================
# Expects history_df to already be filtered to events on/before
# the current document's date — see utils.equipment_history().

def add_history(doc, history_df):

    doc.add_heading(
        "Previous Equipment History",
        level=1
    )

    if len(history_df) == 0:

        doc.add_paragraph(
            "No previous maintenance history available."
        )

        return

    table = doc.add_table(rows=1, cols=4)

    table.style = "Table Grid"

    hdr = table.rows[0].cells

    hdr[0].text = "Event"
    hdr[1].text = "Date"
    hdr[2].text = "Failure"
    hdr[3].text = "Status"

    for _, row in history_df.iterrows():

        cells = table.add_row().cells

        cells[0].text = str(row["Event ID"])

        cells[1].text = str(row["Date"])

        cells[2].text = str(row["Root Cause"])

        cells[3].text = str(row["Status"])

    doc.add_paragraph()