"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Equipment Health History Generator
=========================================================
"""

import os
import pandas as pd

from config import *
from utils import *


# ==========================================================
# OUTPUT FILE
# ==========================================================

HEALTH_HISTORY_FILE = os.path.join(
    DATASET_DIR,
    "equipment_health_history.xlsx"
)


# ==========================================================
# LOAD EVENTS
# ==========================================================

events = load_events(EVENT_FILE)


log(f"{len(events)} Events Loaded")


# ==========================================================
# CREATE HEALTH HISTORY
# ==========================================================


history = []


for _, event in events.iterrows():

    record = {

        "Equipment ID":
            event["Equipment ID"],


        "Equipment Name":
            event["Equipment Name"],


        "Date":
            event["Date"],


        "Event ID":
            event["Event ID"],


        "Event Type":
            event["Event Type"],


        "Failure Category":
            event["Failure Category"],


        "Description":
            event["Description"],


        "Root Cause":
            event["Root Cause"],


        "Corrective Action":
            event["Corrective Action"],


        "Severity":
            event["Severity"],


        "Priority":
            event["Priority"],


        "Downtime (hrs)":
            event["Downtime (hrs)"],


        "Status":
            event["Status"],


        "Follow-up Required":
            event["Follow-up Required"]

    }


    history.append(record)



# ==========================================================
# DATAFRAME
# ==========================================================


health_df = pd.DataFrame(history)



# ==========================================================
# SORT HISTORY
# ==========================================================


health_df = health_df.sort_values(
    [
        "Equipment ID",
        "Date"
    ]
)



# ==========================================================
# SAVE
# ==========================================================


health_df.to_excel(
    HEALTH_HISTORY_FILE,
    index=False
)



success(
    "Equipment Health History Generated"
)


print(
    f"Saved : {HEALTH_HISTORY_FILE}"
)