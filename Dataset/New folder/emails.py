"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Email Generator
=========================================================
"""

import os

from config import *
from utils import *
from template_manager import email_template
from document_utils import *

# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

os.makedirs(EMAIL_DIR, exist_ok=True)

# ==========================================================
# LOAD EVENTS + EMPLOYEES
# ==========================================================

events = load_events(EVENT_FILE)

employees = load_employees(EMPLOYEE_FILE)

if TEST_MODE:
    events = first_n_events(events, TEST_EVENTS)

log(f"{len(events)} Events Loaded")

# ==========================================================
# GENERATE EMAILS
# ==========================================================

generated = 0

for _, event in events.iterrows():

    template = email_template(event)

    document_number = create_document_number(
        DOC_PREFIX["email"],
        event
    )

    filename = f"{document_number}.{DOC_FORMAT['email']}"

    filepath = os.path.join(
        EMAIL_DIR,
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
    # EMAIL INFORMATION
    # ======================================================

    add_email_information(
        doc,
        event,
        template
    )

    # ======================================================
    # EMAIL SUBJECT
    # ======================================================

    add_section(
        doc,
        "Email Subject"
    )

    add_text(
        doc,
        template["subject"]
    )

    # ======================================================
    # EMAIL BODY
    # ======================================================

    add_section(
        doc,
        "Email Body"
    )

    add_text(
        doc,
        template["body"]
    )

    # ======================================================
    # ACTION REQUIRED
    # ======================================================

    add_section(
        doc,
        "Action Required"
    )

    add_text(
        doc,
        template["action"]
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
    # RECOMMENDATIONS
    # ======================================================

    add_recommendation(
        doc,
        template["recommendation"]
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
        DOC_FORMAT['email']
    )

    generated += 1

    success(filename)

# ==========================================================
# SUMMARY
# ==========================================================

print_summary(generated)