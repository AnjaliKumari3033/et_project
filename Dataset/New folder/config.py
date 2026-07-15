"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Configuration File
=========================================================
"""

import os

# =========================================================
# COMPANY DETAILS
# =========================================================

COMPANY_NAME = "NovaChem Chemicals Pvt. Ltd."
PLANT_NAME = "NovaChem Industrial Plant"

COMPANY_ADDRESS = (
    "Plot No. 18, GIDC Industrial Estate,\n"
    "Vadodara, Gujarat - 390010"
)

CONFIDENTIALITY = "Internal Use Only"

REVISION = "Rev-1.0"

# Used only if no real employee match is found at all
APPROVER_FALLBACK = "Plant Manager"

# =========================================================
# PROJECT PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

EVENT_FILE = os.path.join(DATASET_DIR, "plant_events.xlsx")

EMPLOYEE_FILE = os.path.join(DATASET_DIR, "novachem_employees.xlsx")

OUTPUT_DIR = os.path.join(DATASET_DIR, "generated_documents")

# =========================================================
# OUTPUT FOLDERS
# =========================================================

MAINTENANCE_DIR = os.path.join(OUTPUT_DIR, "maintenance")
INSPECTION_DIR = os.path.join(OUTPUT_DIR, "inspection")
WORKORDER_DIR = os.path.join(OUTPUT_DIR, "work_orders")
INCIDENT_DIR = os.path.join(OUTPUT_DIR, "incidents")
EMAIL_DIR = os.path.join(OUTPUT_DIR, "emails")
RCA_DIR = os.path.join(OUTPUT_DIR, "rca")
QUALITY_DIR = os.path.join(OUTPUT_DIR, "quality")
SAFETY_DIR = os.path.join(OUTPUT_DIR, "safety")
CALIBRATION_DIR = os.path.join(OUTPUT_DIR, "calibration")

DOCUMENT_INDEX_FILE = os.path.join(
    OUTPUT_DIR,
    "document_index.xlsx"
)

# =========================================================
# DOCUMENT PREFIXES
# =========================================================

DOC_PREFIX = {
    "maintenance": "MNT",
    "inspection": "INS",
    "work_order": "WO",
    "incident": "INC",
    "email": "EMAIL",
    "rca": "RCA",
    "quality": "QA",
    "safety": "SAF",
    "calibration": "CAL"
}

# Output file format for each document type — deliberately
# heterogeneous, matching how these documents would really be
# produced/stored in a plant (some in Word, some scanned/exported
# as PDF, some as spreadsheets, plain email text, etc.)
DOC_FORMAT = {
    "maintenance": "docx",
    "inspection": "pdf",
    "work_order": "xlsx",
    "incident": "pdf",
    "email": "txt",
    "rca": "docx",
    "quality": "xlsx",
    "safety": "pdf",
    "calibration": "pdf"
}

# Maps the text used in the "Documents to Generate" column
# (in plant_events.xlsx) to the DOC_PREFIX key above.
# Add an entry here any time you introduce a new document type.
DOC_TYPE_MAP = {
    "work order": "work_order",
    "maintenance report": "maintenance",
    "inspection report": "inspection",
    "incident report": "incident",
    "email": "email",
    "rca": "rca",
    "rca report": "rca",
    "quality report": "quality",
    "safety report": "safety",
    "calibration report": "calibration"
}

# =========================================================
# TEST SETTINGS
# =========================================================

TEST_MODE = False

TEST_EVENTS = 10

# Set to True only after review
GENERATE_ALL = True

# =========================================================
# DOCUMENT SETTINGS
# =========================================================

DEFAULT_FONT = "Calibri"

FONT_SIZE = 11

TITLE_SIZE = 18

HEADING_SIZE = 14

PAGE_MARGIN = 0.6

# =========================================================
# RANDOMIZATION
# =========================================================

ENABLE_RANDOM_REMARKS = True

ENABLE_RANDOM_MISSING_FIELDS = True

ENABLE_VARIATION = True

# =========================================================
# CREATE FOLDERS AUTOMATICALLY
# =========================================================

FOLDERS = [

    OUTPUT_DIR,

    MAINTENANCE_DIR,

    INSPECTION_DIR,

    WORKORDER_DIR,

    INCIDENT_DIR,

    EMAIL_DIR,

    RCA_DIR,

    QUALITY_DIR,

    SAFETY_DIR,

    CALIBRATION_DIR

]

for folder in FOLDERS:

    os.makedirs(folder, exist_ok=True)