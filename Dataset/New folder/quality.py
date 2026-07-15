"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Quality Report Generator
=========================================================
"""

import os

from config import *
from utils import *
from template_manager import quality_template
from document_utils import *


# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

os.makedirs(QUALITY_DIR, exist_ok=True)


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
# GENERATE QUALITY REPORTS
# ==========================================================

generated = 0


for _, event in events.iterrows():


    template = quality_template(event)



    document_number = create_document_number(
        DOC_PREFIX["quality"],
        event
    )


    filename = f"{document_number}.{DOC_FORMAT['quality']}"


    filepath = os.path.join(
        QUALITY_DIR,
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
    # QUALITY INFORMATION
    # ======================================================


    add_quality_information(
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
    # QUALITY ISSUE DESCRIPTION
    # ======================================================


    add_section(
        doc,
        "Quality Issue Description"
    )


    add_text(
        doc,
        template["description"]
    )



    # ======================================================
    # QUALITY FINDINGS
    # ======================================================


    add_section(
        doc,
        "Quality Findings"
    )


    add_text(
        doc,
        template["findings"]
    )



    # ======================================================
    # NON CONFORMANCE DETAILS
    # ======================================================


    add_section(
        doc,
        "Non Conformance Details"
    )


    add_text(
        doc,
        template["non_conformance"]
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
    # QUALITY ASSESSMENT
    # ======================================================


    add_quality_assessment(
        doc,
        event
    )



    # ======================================================
    # VERIFICATION
    # ======================================================


    add_section(
        doc,
        "Verification Status"
    )


    add_text(
        doc,
        template["verification"]
    )



    # ======================================================
    # QUALITY STATUS
    # ======================================================


    add_section(
        doc,
        "Final Quality Status"
    )


    add_text(
        doc,
        template["status"]
    )


    # ======================================================
# ENGINEER REMARKS
# ======================================================

    add_section(
        doc,
        "Quality Engineer Remarks"
    )

    add_text(
        doc,
        template["engineer_remark"]
    )



# ======================================================
# SAFETY OBSERVATION
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
        "Inspection Tools Used"
    )

    add_text(
        doc,
        template["tool"]
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
    # CHECKLIST
    # ======================================================


    add_checklist(
        doc,
        allow_variation=ENABLE_RANDOM_MISSING_FIELDS,
        title="Quality Inspection Checklist"
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


    save_document_as(
        doc,
        filepath,
        DOC_FORMAT['quality']
    )


    generated += 1


    success(filename)



# ==========================================================
# SUMMARY
# ==========================================================

print_summary(generated)