"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Spare Parts Inventory Generator
=========================================================
"""

import os
import pandas as pd

from config import *


# ==========================================================
# OUTPUT FILE
# ==========================================================

SPARE_PART_FILE = os.path.join(
    DATASET_DIR,
    "spare_parts_inventory.xlsx"
)


# ==========================================================
# SPARE PART KNOWLEDGE
# ==========================================================

spare_parts = [

    # Mechanical Parts

    {
        "Part ID": "SP-M001",
        "Part Name": "Bearing",
        "Category": "Mechanical",
        "Used For": "Pump, Motor",
        "Compatible Equipment": "P-101,P-102,M-201",
        "Quantity Available": 25,
        "Minimum Stock Level": 5,
        "Storage Location": "Mechanical Store",
        "Criticality": "High"
    },


    {
        "Part ID": "SP-M002",
        "Part Name": "Mechanical Seal",
        "Category": "Mechanical",
        "Used For": "Pump",
        "Compatible Equipment": "P-101,P-102",
        "Quantity Available": 12,
        "Minimum Stock Level": 3,
        "Storage Location": "Mechanical Store",
        "Criticality": "High"
    },


    {
        "Part ID": "SP-M003",
        "Part Name": "Lubricant",
        "Category": "Mechanical",
        "Used For": "Rotating Equipment",
        "Compatible Equipment": "All Pumps",
        "Quantity Available": 100,
        "Minimum Stock Level": 20,
        "Storage Location": "Maintenance Store",
        "Criticality": "Medium"
    },


    {
        "Part ID": "SP-M004",
        "Part Name": "Coupling",
        "Category": "Mechanical",
        "Used For": "Motor Pump System",
        "Compatible Equipment": "P-101,P-103",
        "Quantity Available": 8,
        "Minimum Stock Level": 2,
        "Storage Location": "Mechanical Store",
        "Criticality": "Medium"
    },


    # Electrical Parts


    {
        "Part ID": "SP-E001",
        "Part Name": "Fuse",
        "Category": "Electrical",
        "Used For": "Electrical Panel",
        "Compatible Equipment": "MCC Panels",
        "Quantity Available": 50,
        "Minimum Stock Level": 10,
        "Storage Location": "Electrical Store",
        "Criticality": "Medium"
    },


    {
        "Part ID": "SP-E002",
        "Part Name": "Power Cable",
        "Category": "Electrical",
        "Used For": "Motor Connection",
        "Compatible Equipment": "All Motors",
        "Quantity Available": 200,
        "Minimum Stock Level": 50,
        "Storage Location": "Electrical Store",
        "Criticality": "High"
    },


    {
        "Part ID": "SP-E003",
        "Part Name": "Terminal Lug",
        "Category": "Electrical",
        "Used For": "Electrical Wiring",
        "Compatible Equipment": "Control Panels",
        "Quantity Available": 150,
        "Minimum Stock Level": 30,
        "Storage Location": "Electrical Store",
        "Criticality": "Low"
    },


    # Instrumentation Parts


    {
        "Part ID": "SP-I001",
        "Part Name": "Pressure Sensor",
        "Category": "Instrumentation",
        "Used For": "Pressure Monitoring",
        "Compatible Equipment": "Process Equipment",
        "Quantity Available": 10,
        "Minimum Stock Level": 2,
        "Storage Location": "Instrument Store",
        "Criticality": "High"
    },


    {
        "Part ID": "SP-I002",
        "Part Name": "Temperature Sensor",
        "Category": "Instrumentation",
        "Used For": "Temperature Monitoring",
        "Compatible Equipment": "Reactors",
        "Quantity Available": 15,
        "Minimum Stock Level": 5,
        "Storage Location": "Instrument Store",
        "Criticality": "Medium"
    },


    {
        "Part ID": "SP-I003",
        "Part Name": "Signal Cable",
        "Category": "Instrumentation",
        "Used For": "Control Signal",
        "Compatible Equipment": "PLC System",
        "Quantity Available": 75,
        "Minimum Stock Level": 15,
        "Storage Location": "Instrument Store",
        "Criticality": "Medium"
    }

]


# ==========================================================
# CREATE DATAFRAME
# ==========================================================

df = pd.DataFrame(
    spare_parts
)



# ==========================================================
# STOCK STATUS
# ==========================================================

df["Stock Status"] = df.apply(

    lambda x:
    "LOW STOCK"
    if x["Quantity Available"] <= x["Minimum Stock Level"]
    else "AVAILABLE",

    axis=1

)



# ==========================================================
# SAVE
# ==========================================================

df.to_excel(
    SPARE_PART_FILE,
    index=False
)


print(
    "[SUCCESS] Spare Parts Inventory Generated"
)


print(
    SPARE_PART_FILE
)