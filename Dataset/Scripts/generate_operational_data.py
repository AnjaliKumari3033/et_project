"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Operational Data Generator

Generates:
1. Daily Production Reports
2. Operator Logs
3. Shift Logs
4. Spare Parts Requests
=========================================================
"""


import os
import random
import pandas as pd

from datetime import timedelta, datetime

from config import *
from utils import *



# ==========================================================
# OUTPUT DIRECTORY
# ==========================================================

OPERATIONAL_DIR = os.path.join(
    OUTPUT_DIR,
    "operational_data"
)

os.makedirs(
    OPERATIONAL_DIR,
    exist_ok=True
)



# ==========================================================
# LOAD DATA
# ==========================================================

events = load_events(EVENT_FILE)

employees = load_employees(
    EMPLOYEE_FILE
)


log(
    f"{len(events)} Events Loaded"
)



# ==========================================================
# SAMPLE VALUES
# ==========================================================


PRODUCTS = [

    "Acetic Acid",
    "Ethylene Glycol",
    "Industrial Solvent",
    "Polymer Resin",
    "Chemical Additive"

]


PRODUCTION_STATUS = [

    "Running",
    "Reduced Production",
    "Stopped",
    "Maintenance Hold"

]


QUALITY_STATUS = [

    "Accepted",
    "Rejected",
    "Under Review"

]


OBSERVATIONS = [

    "Abnormal vibration detected",

    "Temperature slightly higher than normal",

    "Minor leakage observed",

    "Noise level increased",

    "Pressure fluctuation noticed",

    "Equipment operating normally"

]


SHIFT_HANDOVER = [

    "Continue monitoring equipment",

    "Check lubrication condition",

    "Follow preventive maintenance schedule",

    "No pending issues",

    "Monitor pressure readings"

]


PARTS = [

    "Bearing",

    "Mechanical Seal",

    "Pressure Sensor",

    "Motor Coupling",

    "Fuse",

    "Valve Assembly",

    "Filter Element",

    "Cable Assembly"

]



# ==========================================================
# DAILY PRODUCTION REPORTS
# ==========================================================


production_reports = []


for index, event in events.iterrows():

    quantity = random.randint(
        4000,
        8000
    )


    downtime = float(
        event["Downtime (hrs)"]
    )


    production_loss = int(
        downtime * random.randint(50,150)
    )


    production_reports.append({

        "Report ID":
        f"DPR-{index+1:03}",


        "Date":
        event["Date"],


        "Shift":
        event["Shift"],


        "Department":
        event["Department"],


        "Product Name":
        random.choice(PRODUCTS),


        "Batch Number":
        f"BAT-{1000+index}",


        "Planned Quantity (kg)":
        quantity,


        "Actual Quantity (kg)":
        quantity-production_loss,


        "Production Loss (kg)":
        production_loss,


        "Equipment ID":
        event["Equipment ID"],


        "Downtime Hours":
        downtime,


        "Downtime Reason":
        event["Root Cause"],


        "Quality Status":
        random.choice(QUALITY_STATUS),


        "Supervisor":
        event["Assigned To"]

    })



pd.DataFrame(
    production_reports
).to_excel(

    os.path.join(
        OPERATIONAL_DIR,
        "daily_production_reports.xlsx"
    ),

    index=False

)



success(
    "Daily Production Reports Generated"
)



# ==========================================================
# OPERATOR LOGS
# ==========================================================


operator_logs = []


operators = employees[
    employees["Role"]
    .astype(str)
    .str.contains(
        "operator",
        case=False,
        na=False
    )
]


for index,event in events.iterrows():


    if len(operators)>0:

        operator = random.choice(
            operators["Name"].tolist()
        )

    else:

        operator = event["Assigned To"]



    operator_logs.append({

        "Log ID":
        f"OPLOG-{index+1:03}",


        "Date":
        event["Date"],


        "Shift":
        event["Shift"],


        "Operator Name":
        operator,


        "Equipment ID":
        event["Equipment ID"],


        "Observation":
        random.choice(
            OBSERVATIONS
        ),


        "Temperature":
        f"{random.randint(50,90)} °C",


        "Pressure":
        f"{random.randint(2,8)} bar",


        "Noise Level":
        random.choice(
            [
                "Normal",
                "Medium",
                "High"
            ]
        ),


        "Action Taken":
        "Supervisor informed",


        "Status":
        event["Status"]

    })



pd.DataFrame(
    operator_logs
).to_excel(

    os.path.join(
        OPERATIONAL_DIR,
        "operator_logs.xlsx"
    ),

    index=False

)



success(
    "Operator Logs Generated"
)



# ==========================================================
# SHIFT LOGS
# ==========================================================


shift_logs=[]


for index,event in events.iterrows():


    shift_logs.append({

        "Shift ID":
        f"SHIFT-{index+1:03}",


        "Date":
        event["Date"],


        "Shift":
        event["Shift"],


        "Supervisor":
        event["Assigned To"],


        "Operators Count":
        random.randint(
            5,
            20
        ),


        "Production Status":
        random.choice(
            PRODUCTION_STATUS
        ),


        "Equipment Status":
        event["Status"],


        "Safety Issues":
        "None",


        "Pending Work":
        event["Corrective Action"],


        "Handover Notes":
        random.choice(
            SHIFT_HANDOVER
        )

    })



pd.DataFrame(
    shift_logs
).to_excel(

    os.path.join(
        OPERATIONAL_DIR,
        "shift_logs.xlsx"
    ),

    index=False

)



success(
    "Shift Logs Generated"
)



# ==========================================================
# SPARE PART REQUESTS
# ==========================================================


spare_requests=[]



for index,event in events.iterrows():


    spare_requests.append({

        "Request ID":
        f"SPR-{index+1:03}",


        "Date":
        event["Date"],


        "Equipment ID":
        event["Equipment ID"],


        "Part Name":
        random.choice(
            PARTS
        ),


        "Quantity":
        random.randint(
            1,
            5
        ),


        "Requested By":
        event["Assigned To"],


        "Priority":
        event["Priority"],


        "Reason":
        event["Root Cause"],


        "Approval Status":
        random.choice(
            [
                "Approved",
                "Pending",
                "Rejected"
            ]
        ),


        "Replacement Date":
(
    pd.to_datetime(event["Date"])
    +
    timedelta(
        days=random.randint(1,10)
    )
).strftime("%d-%b-%Y")

    })



pd.DataFrame(
    spare_requests
).to_excel(

    os.path.join(
        OPERATIONAL_DIR,
        "spare_parts_requests.xlsx"
    ),

    index=False

)



success(
    "Spare Parts Requests Generated"
)



# ==========================================================
# SUMMARY
# ==========================================================


print("\n==============================")
print("Operational Data Generation Completed")
print("==============================")

print(
    f"Production Reports : {len(production_reports)}"
)

print(
    f"Operator Logs      : {len(operator_logs)}"
)

print(
    f"Shift Logs         : {len(shift_logs)}"
)

print(
    f"Spare Requests     : {len(spare_requests)}"
)