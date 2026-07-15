"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Failure Taxonomy Generator
=========================================================
"""

import os
import pandas as pd

from config import *


# ==========================================================
# OUTPUT FILE
# ==========================================================

FAILURE_TAXONOMY_FILE = os.path.join(
    DATASET_DIR,
    "failure_taxonomy.xlsx"
)


# ==========================================================
# FAILURE KNOWLEDGE STRUCTURE
# ==========================================================

failure_data = [

    # ================= Mechanical =================

    {
        "Level 1": "Mechanical",
        "Level 2": "Bearing Failure",
        "Level 3": "Bearing Wear",
        "Possible Cause": "Ageing, excessive load, poor lubrication",
        "Affected Equipment": "Pump, Motor, Compressor",
        "Recommended Action": "Replace bearing and check lubrication"
    },


    {
        "Level 1": "Mechanical",
        "Level 2": "Bearing Failure",
        "Level 3": "Overheating",
        "Possible Cause": "Insufficient lubrication or misalignment",
        "Affected Equipment": "Rotating Equipment",
        "Recommended Action": "Inspect lubrication system"
    },


    {
        "Level 1": "Mechanical",
        "Level 2": "Seal Failure",
        "Level 3": "Leakage",
        "Possible Cause": "Seal damage or pressure variation",
        "Affected Equipment": "Pump",
        "Recommended Action": "Replace mechanical seal"
    },


    {
        "Level 1": "Mechanical",
        "Level 2": "Alignment Issue",
        "Level 3": "Shaft Misalignment",
        "Possible Cause": "Improper installation or vibration",
        "Affected Equipment": "Motor Pump System",
        "Recommended Action": "Perform laser alignment"
    },


    # ================= Electrical =================


    {
        "Level 1": "Electrical",
        "Level 2": "Motor Failure",
        "Level 3": "Winding Damage",
        "Possible Cause": "Overload or insulation failure",
        "Affected Equipment": "Electric Motor",
        "Recommended Action": "Test winding and repair motor"
    },


    {
        "Level 1": "Electrical",
        "Level 2": "Power Supply Issue",
        "Level 3": "Voltage Fluctuation",
        "Possible Cause": "Power instability",
        "Affected Equipment": "Electrical Panel",
        "Recommended Action": "Check incoming supply"
    },


    {
        "Level 1": "Electrical",
        "Level 2": "Cable Failure",
        "Level 3": "Insulation Damage",
        "Possible Cause": "Ageing or overheating",
        "Affected Equipment": "Electrical System",
        "Recommended Action": "Replace damaged cable"
    },


    # ================= Instrumentation =================


    {
        "Level 1": "Instrumentation",
        "Level 2": "Sensor Failure",
        "Level 3": "Calibration Drift",
        "Possible Cause": "Ageing sensor or environmental effect",
        "Affected Equipment": "Transmitters, Sensors",
        "Recommended Action": "Perform calibration"
    },


    {
        "Level 1": "Instrumentation",
        "Level 2": "Signal Failure",
        "Level 3": "Communication Loss",
        "Possible Cause": "Cable fault or configuration issue",
        "Affected Equipment": "Control System",
        "Recommended Action": "Check signal wiring"
    },


    # ================= Process =================


    {
        "Level 1": "Process",
        "Level 2": "Pressure Abnormality",
        "Level 3": "High Pressure",
        "Possible Cause": "Valve malfunction or blockage",
        "Affected Equipment": "Pipeline System",
        "Recommended Action": "Inspect valves and pressure control"
    },


    {
        "Level 1": "Process",
        "Level 2": "Temperature Abnormality",
        "Level 3": "High Temperature",
        "Possible Cause": "Cooling failure",
        "Affected Equipment": "Reactors, Heat Exchangers",
        "Recommended Action": "Inspect cooling system"
    }

]


# ==========================================================
# CREATE DATAFRAME
# ==========================================================

df = pd.DataFrame(
    failure_data
)


# ==========================================================
# SAVE FILE
# ==========================================================

df.to_excel(
    FAILURE_TAXONOMY_FILE,
    index=False
)


print(
    "[SUCCESS] Failure Taxonomy Generated"
)


print(
    FAILURE_TAXONOMY_FILE
)