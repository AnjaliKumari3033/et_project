"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Maintenance Report Generator
=========================================================
"""

import os

from config import *

from utils import *

from template_manager import maintenance_template

from document_utils import *


# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

os.makedirs(MAINTENANCE_DIR, exist_ok=True)


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

    template = maintenance_template(event)

    document_number = create_document_number(
        DOC_PREFIX["maintenance"],
        event
    )

    filename = f"{document_number}.docx"

    filepath = os.path.join(
        MAINTENANCE_DIR,
        filename
    )

    log(f"Generating {filename}")

    doc = create_document(template["title"])

    # ======================================================
    # DOCUMENT INFO
    # ======================================================

    add_document_metadata(

        doc,

        event,

        document_number

    )

    approver = get_approver(employees, event["Department"])

    add_document_control(

        doc,

        document_number=document_number,

        issue_date=format_date(event["Date"]),

        prepared_by=event["Assigned To"],

        approved_by=approver,

        revision=REVISION

    )


    # ======================================================
    # EQUIPMENT
    # ======================================================

    add_equipment_details(

        doc,

        event

    )


    # ======================================================
    # PROBLEM
    # ======================================================

    add_section(doc, "Problem Description")

    add_text(doc, template["problem"])


    # ======================================================
    # INSPECTION
    # ======================================================

    add_section(doc, "Inspection Findings")

    add_text(doc, template["inspection"])


    # ======================================================
    # ACTION
    # ======================================================

    add_section(doc, "Corrective Action")

    add_text(doc, template["action"])

    # ======================================================
    # ROOT CAUSE
    # ======================================================

    add_section(doc, "Root Cause")

    add_text(doc, event["Root Cause"])


    # ======================================================
    # ENGINEER REMARK
    # ======================================================

    add_section(doc, "Engineer Remarks")

    add_text(doc, template["engineer_remark"])


    # ======================================================
    # SAFETY
    # ======================================================

    add_section(doc, "Safety")

    add_text(doc, template["safety"])


    # ======================================================
    # TOOL USED
    # ======================================================

    add_section(doc, "Tools Used")

    add_text(doc, template["tool"])


    # ======================================================
    # SUMMARY
    # ======================================================

    add_summary_table(doc, event)

    # ======================================================
    # HISTORY
    # ======================================================
    # Only events up to and including this event's own date —
    # a document can never reference something that hasn't
    # happened yet.

    history = equipment_history(
        events,
        event["Equipment ID"],
        as_of_date=event["Date"]
    )

    add_history(doc, history)


    # ======================================================
    # SPARE PARTS
    # ======================================================

    add_spare_parts(doc, event)


    # ======================================================
    # CHECKLIST
    # ======================================================

    add_checklist(doc, allow_variation=ENABLE_RANDOM_MISSING_FIELDS)


    # ======================================================
    # RECOMMENDATION
    # ======================================================

    add_recommendation(doc, template["recommendation"])


    # ======================================================
    # LINKED DOCUMENTS
    # ======================================================
    # Built from this event's own "Documents to Generate"
    # column, so the list only ever shows documents that
    # actually correspond to this event.

    docs = linked_documents(event)

    add_linked_documents(doc, docs)


    # ======================================================
    # APPROVAL
    # ======================================================

    add_signature_block(

        doc,

        prepared_by=event["Assigned To"],

        approved_by=approver

    )

    # ======================================================
    # SAVE
    # ======================================================

    save_document(doc, filepath)

    generated += 1

    success(filename)


print_summary(generated)