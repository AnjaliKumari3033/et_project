"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Incident Report Generator
=========================================================
"""

import os

from config import *
from utils import *
from template_manager import incident_template
from document_utils import *

# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

os.makedirs(INCIDENT_DIR, exist_ok=True)

# ==========================================================
# LOAD EVENTS + EMPLOYEES
# ==========================================================

events = load_events(EVENT_FILE)

employees = load_employees(EMPLOYEE_FILE)

if TEST_MODE:
    events = first_n_events(events, TEST_EVENTS)

log(f"{len(events)} Events Loaded")

# ==========================================================
# GENERATE INCIDENT REPORTS
# ==========================================================

generated = 0

for _, event in events.iterrows():

    template = incident_template(event)

    document_number = create_document_number(
        DOC_PREFIX["incident"],
        event
    )

    filename = f"{document_number}.docx"

    filepath = os.path.join(
        INCIDENT_DIR,
        filename
    )

    log(f"Generating {filename}")

    doc = create_document(
        template["title"]
    )

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
    # INCIDENT INFORMATION
    # ======================================================

    add_incident_information(
        doc,
        event
    )

# ======================================================
# EQUIPMENT DETAILS
# ======================================================

    add_equipment_details(
        doc,
        event
    )

# ======================================================
# INCIDENT DESCRIPTION
# ======================================================

    add_section(
        doc,
        "Incident Description"
    )

    add_text(
        doc,
        template["description"]
    )

# ======================================================
# IMPACT ASSESSMENT
# ======================================================

    add_impact_assessment(
        doc,
        event
    )

# ======================================================
# ROOT CAUSE ANALYSIS
# ======================================================

    add_section(
        doc,
        "Root Cause Analysis"
    )

    add_text(
        doc,
        template["root_cause"]
    )

# ======================================================
# IMMEDIATE ACTION TAKEN
# ======================================================

    add_immediate_action(
        doc,
        template["action"]
    )

# ======================================================
# SAFETY CLASSIFICATION
# ======================================================

    add_safety_classification(
        doc,
        event
    )

# ======================================================
# SAFETY REQUIREMENTS
# ======================================================

    add_safety_requirements(
        doc,
        template["safety"]
    )

# ======================================================
# RECOMMENDATIONS
# ======================================================

    add_recommendation(
        doc,
        template["recommendation"]
    )


    # ======================================================
    # PREVIOUS EQUIPMENT HISTORY
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