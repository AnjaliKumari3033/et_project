"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Preventive Maintenance Schedule Generator
=========================================================
"""

import os
import random
import pandas as pd
from datetime import datetime, timedelta

from config import *


# ==========================================================
# PATHS
# ==========================================================

EQUIPMENT_FILE = os.path.join(
    DATASET_DIR,
    "equipment_master.xlsx"
)

OUTPUT_FILE = os.path.join(
    DATASET_DIR,
    "preventive_maintenance_schedule.xlsx"
)


# ==========================================================
# LOAD EQUIPMENT MASTER
# ==========================================================

equipment = pd.read_excel(
    EQUIPMENT_FILE
)


print(
    f"[INFO] {len(equipment)} Equipment Loaded"
)


# ==========================================================
# DEFAULT VALUES
# ==========================================================

PM_FREQUENCY = {

    "High": 30,       # monthly

    "Medium": 90,     # quarterly

    "Low": 180        # half yearly

}


ACTIVITIES = [

    "Visual inspection and condition check",

    "Lubrication inspection",

    "Vibration monitoring",

    "Temperature monitoring",

    "Alignment verification",

    "Leakage inspection",

    "Electrical parameter checking",

    "Safety inspection"

]


TECHNICIANS = [

    "Pooja Mehta",

    "Rahul Sharma",

    "Amit Patel",

    "Neha Singh",

    "Vikram Rao"

]


# ==========================================================
# GENERATE PM SCHEDULE
# ==========================================================

records = []


for _, eq in equipment.iterrows():


    # Handle missing Asset Criticality

    criticality = eq.get(
        "Asset Criticality",
        "Medium"
    )


    if pd.isna(criticality):

        criticality = "Medium"



    # PM frequency

    frequency_days = PM_FREQUENCY.get(
        criticality,
        90
    )



    # Random last maintenance date

    last_pm = datetime(
        2026,
        random.randint(1,6),
        random.randint(1,20)
    )


    next_pm = last_pm + timedelta(
        days=frequency_days
    )



    record = {


        "PM ID":

        f"PM-{eq['Equipment ID']}",



        "Equipment ID":

        eq["Equipment ID"],



        "Equipment Name":

        eq["Equipment Name"],



        "Area":

        eq["Area"],



        "Manufacturer":

        eq["Manufacturer"],



        "Criticality":

        criticality,



        "Maintenance Frequency":

        f"{frequency_days} Days",



        "Last Maintenance Date":

        last_pm.strftime("%Y-%m-%d"),



        "Next PM Due":

        next_pm.strftime("%Y-%m-%d"),



        "Maintenance Activity":

        random.choice(ACTIVITIES),



        "Assigned Technician":

        random.choice(TECHNICIANS),



        "Status":

        "Scheduled"

    }



    records.append(record)



# ==========================================================
# SAVE FILE
# ==========================================================

pm_df = pd.DataFrame(records)


pm_df.to_excel(
    OUTPUT_FILE,
    index=False
)


print(
    "[SUCCESS] Preventive Maintenance Schedule Generated"
)


print(
    OUTPUT_FILE
)