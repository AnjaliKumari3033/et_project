"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Work Order Generator
=========================================================
"""

import os

from config import *
from utils import *
from template_manager import (
    workorder_template,
    random_recommendation
)
from document_utils import *

# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

os.makedirs(WORKORDER_DIR, exist_ok=True)

# ==========================================================
# LOAD EVENTS + EMPLOYEES
# ==========================================================

events = load_events(EVENT_FILE)

employees = load_employees(EMPLOYEE_FILE)

if TEST_MODE:
    events = first_n_events(events, TEST_EVENTS)

log(f"{len(events)} Events Loaded")

# ==========================================================
# GENERATE WORK ORDERS
# ==========================================================

generated = 0

for _, event in events.iterrows():

    template = workorder_template(event)

    document_number = create_document_number(
        DOC_PREFIX["work_order"],
        event
    )

    filename = f"{document_number}.docx"

    filepath = os.path.join(
        WORKORDER_DIR,
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
# WORK ORDER INFORMATION
# ======================================================

    add_workorder_information(
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
# PROBLEM DESCRIPTION
# ======================================================

    add_section(
        doc,
        "Problem Description"
    )

    add_text(
        doc,
        template["problem"]
    )

# ======================================================
# WORK SCOPE
# ======================================================

    add_section(
        doc,
        "Work Scope"
    )

    add_text(
        doc,
        template["scope"]
    )

# ======================================================
# REQUIRED RESOURCES
# ======================================================

    add_required_resources(
        doc,
        event,
        template["tool"]
    )

# ======================================================
# ESTIMATED DURATION
# ======================================================

    add_estimated_duration(
        doc,
        template["duration"]
    )

# ======================================================
# SAFETY REQUIREMENTS
# ======================================================

    add_safety_requirements(
        doc,
        template["safety"]
    )

# ======================================================
# SPECIAL INSTRUCTIONS
# ======================================================

    add_special_instructions(
        doc,
        template["instruction"]
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
    # RECOMMENDATIONS
    # ======================================================

    add_recommendation(
        doc,
        random_recommendation()
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