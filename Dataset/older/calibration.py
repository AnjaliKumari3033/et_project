"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Calibration Report Generator
=========================================================
"""

import os

from config import *
from utils import *
from template_manager import calibration_template
from document_utils import *


# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

os.makedirs(CALIBRATION_DIR, exist_ok=True)



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
# GENERATE CALIBRATION REPORTS
# ==========================================================

generated = 0



for _, event in events.iterrows():


    template = calibration_template(event)



    document_number = create_document_number(
        DOC_PREFIX["calibration"],
        event
    )



    filename = f"{document_number}.docx"



    filepath = os.path.join(
        CALIBRATION_DIR,
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
    # CALIBRATION INFORMATION
    # ======================================================

    add_calibration_information(
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
    # CALIBRATION OBJECTIVE
    # ======================================================

    add_section(
        doc,
        "Calibration Objective"
    )


    add_text(
        doc,
        template["objective"]
    )



    # ======================================================
    # CALIBRATION FINDINGS
    # ======================================================

    add_section(
        doc,
        "Calibration Findings"
    )


    add_text(
        doc,
        template["findings"]
    )



    # ======================================================
    # DEVIATION ANALYSIS
    # ======================================================

    add_section(
        doc,
        "Deviation Analysis"
    )


    add_text(
        doc,
        template["deviation"]
    )



    # ======================================================
    # ADJUSTMENT
    # ======================================================

    add_section(
        doc,
        "Adjustment Performed"
    )


    add_text(
        doc,
        template["adjustment"]
    )



    # ======================================================
    # VERIFICATION
    # ======================================================

    add_section(
        doc,
        "Calibration Verification"
    )


    add_text(
        doc,
        template["verification"]
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
    # CHECKLIST
    # ======================================================

    add_checklist(
        doc,
        allow_variation=ENABLE_RANDOM_MISSING_FIELDS,
        title="Calibration Checklist"
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
    # SAVE
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