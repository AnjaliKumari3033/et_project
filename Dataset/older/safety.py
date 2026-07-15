"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Safety Report Generator
=========================================================
"""

import os

from config import *
from utils import *
from template_manager import safety_template
from document_utils import *


# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

os.makedirs(SAFETY_DIR, exist_ok=True)



# ==========================================================
# LOAD EVENTS + EMPLOYEES
# ==========================================================

events = load_events(EVENT_FILE)

employees = load_employees(EMPLOYEE_FILE)


if TEST_MODE:

    events = first_n_events(
        events,
        TEST_EVENTS
    )


log(f"{len(events)} Events Loaded")



# ==========================================================
# GENERATE SAFETY REPORTS
# ==========================================================

generated = 0



for _, event in events.iterrows():


    template = safety_template(event)



    document_number = create_document_number(
        DOC_PREFIX["safety"],
        event
    )



    filename = f"{document_number}.docx"



    filepath = os.path.join(
        SAFETY_DIR,
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
    # SAFETY INFORMATION
    # ======================================================

    add_safety_information(
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
        "Safety Event Description"
    )


    add_text(
        doc,
        template["description"]
    )



    # ======================================================
    # HAZARD IDENTIFICATION
    # ======================================================

    add_section(
        doc,
        "Hazard Identification"
    )


    add_text(
        doc,
        template["hazard"]
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
        template["risk"]
    )



    # ======================================================
    # IMMEDIATE ACTION
    # ======================================================

    add_section(
        doc,
        "Immediate Action Taken"
    )


    add_text(
        doc,
        template["immediate_action"]
    )



    # ======================================================
    # ROOT CAUSE
    # ======================================================

    add_section(
        doc,
        "Root Cause Analysis"
    )


    add_text(
        doc,
        event["Root Cause"]
    )



    # ======================================================
    # CORRECTIVE ACTION
    # ======================================================

    add_section(
        doc,
        "Corrective Action"
    )


    add_text(
        doc,
        event["Corrective Action"]
    )



    # ======================================================
    # PREVENTIVE ACTION
    # ======================================================

    add_section(
        doc,
        "Preventive Action"
    )


    add_text(
        doc,
        template["preventive_action"]
    )



    # ======================================================
    # SAFETY OBSERVATION
    # ======================================================

    add_section(
        doc,
        "Safety Officer Remarks"
    )


    add_text(
        doc,
        template["engineer_remark"]
    )



    # ======================================================
    # SAFETY CHECKLIST
    # ======================================================

    add_checklist(
        doc,
        allow_variation=ENABLE_RANDOM_MISSING_FIELDS,
        title="Safety Compliance Checklist"
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