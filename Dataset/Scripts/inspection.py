"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Inspection Report Generator
=========================================================
"""

import os

from config import *
from utils import *
from template_manager import inspection_template
from document_utils import *

# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

os.makedirs(INSPECTION_DIR, exist_ok=True)

# ==========================================================
# LOAD EVENTS + EMPLOYEES
# ==========================================================

events = load_events(EVENT_FILE)

employees = load_employees(EMPLOYEE_FILE)

if TEST_MODE:
    events = first_n_events(events, TEST_EVENTS)

log(f"{len(events)} Events Loaded")

# ==========================================================
# GENERATE REPORTS
# ==========================================================

generated = 0

for _, event in events.iterrows():

    template = inspection_template(event)

    document_number = create_document_number(
        DOC_PREFIX["inspection"],
        event
    )

    filename = f"{document_number}.docx"

    filepath = os.path.join(
        INSPECTION_DIR,
        filename
    )

    log(f"Generating {filename}")

    doc = create_document(template["title"])

    # ======================================================
    # DOCUMENT METADATA
    # ======================================================

    add_document_metadata(
        doc,
        event,
        document_number
    )

    approver = get_approver(
        employees,
        event["Department"]
    )

    add_document_control(
        doc,
        document_number=document_number,
        issue_date=format_date(event["Date"]),
        prepared_by=event["Assigned To"],
        approved_by=approver,
        revision=REVISION
    )

    # ======================================================
    # EQUIPMENT DETAILS
    # ======================================================

    add_equipment_details(
        doc,
        event
    )

    # ======================================================
    # INSPECTION OBJECTIVE
    # ======================================================

    add_section(
        doc,
        "Inspection Objective"
    )

    add_text(
        doc,
        template["objective"]
    )

    # ======================================================
    # INSPECTION FINDINGS
    # ======================================================

    add_section(
        doc,
        "Inspection Findings"
    )

    add_text(
        doc,
        template["findings"]
    )

    # ======================================================
    # OBSERVATIONS
    # ======================================================

    add_section(
        doc,
        "Observed Defects"
    )

    add_text(
        doc,
        template["observation"]
    )

    # ======================================================
    # RISK ASSESSMENT
    # ======================================================

    add_section(
        doc,
        "Risk Assessment"
    )

    add_text(
        doc,
        f"Risk Level : {template['risk']}"
    )

    # ======================================================
    # ENGINEER REMARK
    # ======================================================

    add_section(
        doc,
        "Inspector Remarks"
    )

    add_text(
        doc,
        template["engineer_remark"]
    )

    # ======================================================
    # SAFETY
    # ======================================================

    add_section(
        doc,
        "Safety Observation"
    )

    add_text(
        doc,
        template["safety"]
    )

    # ======================================================
    # TOOLS USED
    # ======================================================

    add_section(
        doc,
        "Inspection Tools"
    )

    add_text(
        doc,
        template["tool"]
    )

# ======================================================
# SUMMARY
# ======================================================

    add_summary_table(
        doc,
        event,
        title="Inspection Summary"
    )

# ======================================================
# HISTORY
# ======================================================

    history = equipment_history(
        events,
        event["Equipment ID"],
        as_of_date=event["Date"]
    )

    add_history(
        doc,
        history
    )

    # ======================================================
# ROOT CAUSE
# ======================================================

    add_section(doc, "Root Cause")

    add_text(doc, event["Root Cause"])

# ======================================================
# CHECKLIST
# ======================================================

    add_checklist(
        doc,
        allow_variation=ENABLE_RANDOM_MISSING_FIELDS,
        title="Inspection Checklist"
    )

# ======================================================
# RECOMMENDATION
# ======================================================

    add_recommendation(
        doc,
        template["recommendation"]
    )

    # ======================================================
    # LINKED DOCUMENTS
    # ======================================================

    docs = linked_documents(event)

    add_linked_documents(
        doc,
        docs
    )

    # ======================================================
    # APPROVAL
    # ======================================================

    add_signature_block(
        doc,
        prepared_by=event["Assigned To"],
        approved_by=approver
    )

    # ======================================================
    # SAVE DOCUMENT
    # ======================================================

    save_document(
        doc,
        filepath
    )

    generated += 1

    success(filename)

# ==========================================================
# SUMMARY
# ==========================================================

print_summary(generated)

