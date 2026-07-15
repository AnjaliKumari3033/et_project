"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Document Index Generator
=========================================================
"""


import os
import pandas as pd

from config import *


# ==========================================================
# SETTINGS
# ==========================================================


OUTPUT_FILE = DOCUMENT_INDEX_FILE


DOCUMENT_FOLDERS = {


    "Maintenance Report":
    MAINTENANCE_DIR,


    "Inspection Report":
    INSPECTION_DIR,


    "Work Order":
    WORKORDER_DIR,


    "Incident Report":
    INCIDENT_DIR,


    "Email":
    EMAIL_DIR,


    "RCA Report":
    RCA_DIR,


    "Quality Report":
    QUALITY_DIR,


    "Safety Report":
    SAFETY_DIR,


    "Calibration Report":
    CALIBRATION_DIR

}



# ==========================================================
# LOAD EVENTS
# ==========================================================


events = pd.read_excel(
    EVENT_FILE
)


print(
    f"[INFO] {len(events)} Events Loaded"
)



# ==========================================================
# CREATE LOOKUP
# ==========================================================


event_lookup = {}


for _, row in events.iterrows():

    event_lookup[
        row["Event ID"]
    ] = row



# ==========================================================
# GENERATE INDEX
# ==========================================================


records = []



for doc_type, folder in DOCUMENT_FOLDERS.items():


    if not os.path.exists(folder):

        continue



    for filename in os.listdir(folder):


        if not filename.endswith(".docx"):

            continue



        # Example:
        # MNT_EVT-001.docx


        parts = filename.replace(
            ".docx",
            ""
        ).split("_")



        event_id = None


        for part in parts:

            if part.startswith("EVT"):

                event_id = part



        if event_id not in event_lookup:

            continue



        event = event_lookup[event_id]



        record = {


            "Document ID":

            filename.replace(".docx",""),



            "Document Type":

            doc_type,



            "File Name":

            filename,



            "File Path":

            os.path.join(
                folder,
                filename
            ),



            "Event ID":

            event_id,



            "Equipment ID":

            event["Equipment ID"],



            "Equipment Name":

            event["Equipment Name"],



            "Department":

            event["Department"],



            "Date":

            event["Date"],



            "Failure Category":

            event["Failure Category"],



            "Root Cause":

            event["Root Cause"],



            "Status":

            event["Status"]

        }



        records.append(record)



# ==========================================================
# SAVE INDEX
# ==========================================================


df = pd.DataFrame(records)



df.to_excel(
    OUTPUT_FILE,
    index=False
)



print(
    "[SUCCESS] Document Index Generated"
)


print(
    OUTPUT_FILE
)