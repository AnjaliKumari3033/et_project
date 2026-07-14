"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Template Manager
=========================================================
"""

import random

from config import ENABLE_RANDOM_MISSING_FIELDS


# ==========================================================
# ENGINEER REMARKS
# ==========================================================

ENGINEER_REMARKS = [
    "Equipment restored to normal operating condition.",
    "Recommend vibration monitoring during next inspection.",
    "No abnormal noise observed after trial run.",
    "Preventive maintenance interval should be reduced.",
    "Recommend OEM inspection during annual shutdown.",
    "Equipment performance is within acceptable limits.",
    "Operator advised to monitor pressure readings for 48 hours.",
    "Further monitoring is recommended before closing the case."
]


# ==========================================================
# SAFETY NOTES
# ==========================================================

SAFETY_NOTES = [
    "LOTO procedure was followed throughout maintenance.",
    "All PPE requirements were complied with.",
    "Area was barricaded before maintenance work.",
    "Gas detector readings were within permissible limits.",
    "Equipment was electrically isolated before repair.",
    "Permit To Work (PTW) was verified before maintenance."
]


# ==========================================================
# TOOLS USED
# ==========================================================

TOOLS_USED = [
    "Torque Wrench",
    "Bearing Puller",
    "Laser Alignment Kit",
    "Grease Gun",
    "Digital Multimeter",
    "Dial Gauge",
    "Hydraulic Jack",
    "Socket Wrench Set",
    "Pressure Gauge",
    "Insulation Tester"
]


# ==========================================================
# RECOMMENDATIONS
# ==========================================================

RECOMMENDATIONS = [
    "Continue weekly inspection.",
    "Perform vibration analysis after one week.",
    "Monitor bearing temperature daily.",
    "Replace similar components during annual shutdown.",
    "Increase preventive maintenance frequency.",
    "Check lubrication schedule.",
    "Conduct thermography inspection next month.",
    "Schedule detailed equipment health assessment."
]


# ==========================================================
# OPTIONAL INCOMPLETE FIELD
# ==========================================================
# Only injects "Under Investigation" when the config flag is on.
# This is what makes reports occasionally incomplete, like real
# ones — but you can turn it off globally from config.py.

def maybe_unknown(text, probability=0.10):

    if not ENABLE_RANDOM_MISSING_FIELDS:

        return text

    if random.random() < probability:

        return "Under Investigation"

    return text


# ==========================================================
# RANDOM REMARK
# ==========================================================

def random_remark():

    return random.choice(ENGINEER_REMARKS)


# ==========================================================
# RANDOM SAFETY
# ==========================================================

def random_safety():

    return random.choice(SAFETY_NOTES)


# ==========================================================
# RANDOM TOOL
# ==========================================================

def random_tool():

    return random.choice(TOOLS_USED)


# ==========================================================
# RANDOM RECOMMENDATION
# ==========================================================

def random_recommendation():

    return random.choice(RECOMMENDATIONS)


# ==========================================================
# TEMPLATE 1
# ==========================================================

def template_one(event):

    return {

        "title": "Corrective Maintenance Report",

        "problem": f"""
During routine plant operation, equipment
{event['Equipment ID']} ({event['Equipment Name']})
experienced the following issue:

{event['Description']}
""",

        "inspection": maybe_unknown(f"""
Inspection confirmed:

Failure Category :
{event['Failure Category']}

Severity :
{event['Severity']}

Priority :
{event['Priority']}
"""),

        "action": f"""
Maintenance team performed:

{event['Corrective Action']}

Equipment was tested after maintenance.

Performance restored successfully.
"""

    }


# ==========================================================
# TEMPLATE 2
# ==========================================================

def template_two(event):

    return {

        "title": "Emergency Maintenance Report",

        "problem": f"""
An unexpected equipment failure occurred on
{event['Equipment Name']}.

Observed Problem:

{event['Description']}
""",

        "inspection": maybe_unknown(f"""
Inspection observations:

Root Cause Category:

{event['Failure Category']}

Downtime:

{event['Downtime (hrs)']} Hours
"""),

        "action": f"""
Emergency maintenance carried out.

Action Taken:

{event['Corrective Action']}

Equipment returned to service.
"""

    }


# ==========================================================
# TEMPLATE 3
# ==========================================================

def template_three(event):

    return {

        "title": "Maintenance Activity Report",

        "problem": f"""
Maintenance request received from
{event['Department']} department.

Issue:

{event['Description']}
""",

        "inspection": maybe_unknown(f"""
Inspection Summary

Priority :

{event['Priority']}

Severity :

{event['Severity']}
"""),

        "action": f"""
Maintenance activities completed.

Corrective action:

{event['Corrective Action']}

Equipment performance verified.
"""

    }


# ==========================================================
# TEMPLATE 4
# ==========================================================

def template_four(event):

    return {

        "title": "Equipment Repair Report",

        "problem": f"""
Equipment ID:

{event['Equipment ID']}

Failure Report:

{event['Description']}
""",

        "inspection": maybe_unknown(f"""
Inspection identified:

Failure Category:

{event['Failure Category']}
"""),

        "action": f"""
Repair completed.

Action performed:

{event['Corrective Action']}
"""

    }


# ==========================================================
# SELECT TEMPLATE
# ==========================================================

def maintenance_template(event):

    templates = [
        template_one,
        template_two,
        template_three,
        template_four
    ]

    selected = random.choice(templates)

    data = selected(event)

    data["recommendation"] = random_recommendation()

    data["engineer_remark"] = random_remark()

    data["tool"] = random_tool()

    data["safety"] = random_safety()

    return data

# ==========================================================
# INSPECTION TEMPLATE 1
# ==========================================================

def inspection_template_one(event):

    return {

        "title": "Routine Inspection Report",

        "objective": f"""
Routine inspection was conducted on
{event['Equipment Name']} to evaluate its
operating condition and identify any
abnormalities.
""",

        "findings": maybe_unknown(f"""
Inspection completed successfully.

Failure Category :
{event['Failure Category']}

Severity :
{event['Severity']}

Equipment condition appears satisfactory.
"""),

        "observation": f"""
Observed condition:

{event['Description']}
""",

        "risk": "Low"

    }


# ==========================================================
# INSPECTION TEMPLATE 2
# ==========================================================

def inspection_template_two(event):

    return {

        "title": "Preventive Inspection Report",

        "objective": f"""
Preventive inspection performed before
scheduled maintenance shutdown.
""",

        "findings": maybe_unknown(f"""
Minor abnormalities detected.

Priority :
{event['Priority']}

Downtime :
{event['Downtime (hrs)']} Hours
"""),

        "observation": f"""
Inspection identified:

{event['Root Cause']}
""",

        "risk": "Medium"

    }


# ==========================================================
# INSPECTION TEMPLATE 3
# ==========================================================

def inspection_template_three(event):

    return {

        "title": "Equipment Condition Inspection",

        "objective": f"""
Inspection initiated following an operational
complaint from {event['Department']}.
""",

        "findings": maybe_unknown(f"""
Equipment checked for vibration,
temperature, leakage and alignment.

Status :

{event['Status']}
"""),

        "observation": f"""
Inspector observed:

{event['Description']}
""",

        "risk": "Medium"

    }


# ==========================================================
# INSPECTION TEMPLATE 4
# ==========================================================

def inspection_template_four(event):

    return {

        "title": "Detailed Equipment Inspection",

        "objective": f"""
Detailed inspection performed after
maintenance completion.
""",

        "findings": maybe_unknown(f"""
Inspection verified that corrective action
has been completed.

Asset Criticality :

{event['Asset Criticality']}
"""),

        "observation": f"""
Verification Remarks:

{event['Corrective Action']}
""",

        "risk": "Low"

    }


# ==========================================================
# MAIN INSPECTION TEMPLATE
# ==========================================================

def inspection_template(event):

    templates = [

        inspection_template_one,

        inspection_template_two,

        inspection_template_three,

        inspection_template_four

    ]

    selected = random.choice(templates)

    data = selected(event)

    data["recommendation"] = random_recommendation()

    data["engineer_remark"] = random_remark()

    data["tool"] = random_tool()

    data["safety"] = random_safety()

    return data