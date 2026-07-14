"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Utility Functions
=========================================================
"""

import random
import pandas as pd
from datetime import datetime

from config import DOC_PREFIX, DOC_TYPE_MAP, APPROVER_FALLBACK, ENABLE_RANDOM_MISSING_FIELDS


# ==========================================================
# REQUIRED COLUMNS
# ==========================================================

REQUIRED_COLUMNS = [

    "Event ID",
    "Date",
    "Equipment ID",
    "Equipment Name",
    "Area",
    "Event Type",
    "Description",
    "Department",
    "Reported By",
    "Assigned To",
    "Severity",
    "Priority",
    "Status",
    "Downtime (hrs)",
    "Related Event",
    "Root Cause",
    "Corrective Action",
    "Documents to Generate",
    "Follow-up Required",

    "Failure Category",
    "Asset Criticality",

    "Chain_ID",
    "Previous_Document_Ref",
    "Shift",
    "Reported_From"

]


# ==========================================================
# LOAD EVENTS
# ==========================================================

def load_events(filepath):

    df = pd.read_excel(filepath, keep_default_na=False)

    missing = []

    for col in REQUIRED_COLUMNS:

        if col not in df.columns:
            missing.append(col)

    if len(missing) > 0:

        print("\nMissing Columns\n")

        for c in missing:
            print(c)

        raise Exception("Excel file is missing required columns.")

    df.fillna("", inplace=True)

    # Keep a proper datetime version for sorting / date comparisons.
    # The original "Date" column is left untouched for display.
    df["_ParsedDate"] = pd.to_datetime(df["Date"])

    return df


# ==========================================================
# LOAD EMPLOYEES
# ==========================================================

def load_employees(filepath):

    df = pd.read_excel(filepath, keep_default_na=False)

    return df


# ==========================================================
# GET APPROVER
# ==========================================================
# Picks a real employee to approve a document, instead of a
# generic role label. Order of preference:
#   1. A "Manager" in the same department as the event
#   2. The most senior person (by years of experience) in
#      that department
#   3. The Plant Manager
#   4. APPROVER_FALLBACK text, if nothing else exists

def get_approver(employees_df, department):

    dept_employees = employees_df[
        employees_df["Department"] == department
    ]

    managers = dept_employees[
        dept_employees["Role"].str.contains("Manager", case=False, na=False)
    ]

    if len(managers) > 0:

        return managers.iloc[0]["Name"]

    if len(dept_employees) > 0:

        dept_employees = dept_employees.copy()

        dept_employees["_Years"] = (
            dept_employees["Experience"]
            .astype(str)
            .str.extract(r"(\d+)")
            .astype(float)
        )

        senior = dept_employees.sort_values(
            "_Years",
            ascending=False
        ).iloc[0]

        return senior["Name"]

    plant_manager = employees_df[
        employees_df["Role"].str.contains("Plant Manager", case=False, na=False)
    ]

    if len(plant_manager) > 0:

        return plant_manager.iloc[0]["Name"]

    return APPROVER_FALLBACK


# ==========================================================
# TEST MODE
# ==========================================================

def first_n_events(df, n):

    return df.head(n)


# ==========================================================
# FORMAT DATE
# ==========================================================

def format_date(value):

    if isinstance(value, datetime):

        return value.strftime("%d-%b-%Y")

    try:

        return pd.to_datetime(value).strftime("%d-%b-%Y")

    except:

        return str(value)


# ==========================================================
# GET EVENT
# ==========================================================

def get_event(df, event_id):

    result = df[df["Event ID"] == event_id]

    if len(result) == 0:

        return None

    return result.iloc[0]


# ==========================================================
# EQUIPMENT HISTORY
# ==========================================================
# Returns only events that happened on/before the current
# document's date. Without as_of_date, a document generated
# for an early event would otherwise show later events as if
# they had already happened — a real report can never
# reference the future.

def equipment_history(df, equipment_id, as_of_date=None, exclude_event_id=None):

    history = df[df["Equipment ID"] == equipment_id]

    if as_of_date is not None:

        as_of_date = pd.to_datetime(as_of_date)

        history = history[history["_ParsedDate"] <= as_of_date]

    if exclude_event_id is not None:

        history = history[history["Event ID"] != exclude_event_id]

    return history.sort_values("_ParsedDate")


# ==========================================================
# CHAIN HISTORY
# ==========================================================

def chain_history(df, chain_id, as_of_date=None):

    history = df[df["Chain_ID"] == chain_id]

    if as_of_date is not None:

        as_of_date = pd.to_datetime(as_of_date)

        history = history[history["_ParsedDate"] <= as_of_date]

    return history.sort_values("_ParsedDate")


# ==========================================================
# LINKED DOCUMENTS
# ==========================================================
# Builds the linked-document list from the event's own
# "Documents to Generate" column, instead of a fixed list.
# This keeps every document's "Linked Documents" section
# truthful to what was actually planned for that event.

def linked_documents(event):

    event_id = event["Event ID"]

    raw_types = str(event["Documents to Generate"]).split(",")

    files = []

    for raw in raw_types:

        name = raw.strip().lower()

        key = DOC_TYPE_MAP.get(name)

        if key is None:

            warning(f"Unrecognised document type '{raw.strip()}' for {event_id} — skipped")

            continue

        prefix = DOC_PREFIX[key]

        extension = "txt" if key == "email" else "docx"

        files.append(f"{prefix}_{event_id}.{extension}")

    return files


# ==========================================================
# RANDOM CHOICE
# ==========================================================

def choose(items):

    return random.choice(items)


# ==========================================================
# OPTIONAL FIELD
# ==========================================================

def maybe_blank(text, probability=0.08):

    if not ENABLE_RANDOM_MISSING_FIELDS:

        return text

    if random.random() < probability:

        return ""

    return text


# ==========================================================
# UNDER INVESTIGATION
# ==========================================================

def maybe_under_investigation(text, probability=0.10):

    if not ENABLE_RANDOM_MISSING_FIELDS:

        return text

    if random.random() < probability:

        return "Under Investigation"

    return text


# ==========================================================
# DOCUMENT NUMBER
# ==========================================================

def create_document_number(prefix, event):

    return f"{prefix}_{event['Event ID']}"


# ==========================================================
# MAINTENANCE COST
# ==========================================================

def maintenance_cost(event):

    return f"₹ {event['Maintenance Cost']}"


# ==========================================================
# PRODUCTION LOSS
# ==========================================================

def production_loss(event):

    return f"₹ {event['Production Loss']}"


# ==========================================================
# LOG
# ==========================================================

def log(message):

    print(f"[INFO] {message}")


# ==========================================================
# WARNING
# ==========================================================

def warning(message):

    print(f"[WARNING] {message}")


# ==========================================================
# SUCCESS
# ==========================================================

def success(message):

    print(f"[SUCCESS] {message}")


# ==========================================================
# SUMMARY
# ==========================================================

def print_summary(total):

    print("\n====================================")

    print(f"Documents Generated : {total}")

    print("====================================\n")