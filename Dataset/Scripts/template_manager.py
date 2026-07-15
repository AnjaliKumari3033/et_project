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

# ==========================================================
# WORK SCOPES
# ==========================================================

WORK_SCOPES = [

    "Replace failed component and restore equipment to normal operation.",

    "Inspect equipment, identify defects and perform necessary repairs.",

    "Carry out preventive maintenance activities as per maintenance schedule.",

    "Verify equipment alignment, lubrication and operational parameters.",

    "Repair damaged components and perform functional testing.",

    "Perform calibration and verify instrument accuracy.",

    "Conduct mechanical inspection and replace worn-out parts.",

    "Rectify reported fault and return equipment to service."

]

# ==========================================================
# SAFETY REQUIREMENTS
# ==========================================================

SAFETY_REQUIREMENTS = [

    "Follow Lock Out / Tag Out (LOTO) procedure before work.",

    "Wear mandatory PPE throughout the maintenance activity.",

    "Obtain valid Permit To Work (PTW) before starting work.",

    "Ensure equipment is electrically isolated before repair.",

    "Barricade work area to prevent unauthorized access.",

    "Verify zero energy state before maintenance."

]

# ==========================================================
# SPECIAL INSTRUCTIONS
# ==========================================================

SPECIAL_INSTRUCTIONS = [

    "Complete work before end of shift.",

    "Inform operations before equipment restart.",

    "Record all observations in maintenance log.",

    "Return replaced parts to maintenance store.",

    "Perform trial run in presence of production engineer.",

    "Notify supervisor immediately if additional defects are found."

]

# ==========================================================
# RANDOM WORK SCOPE
# ==========================================================

def random_work_scope():

    return random.choice(WORK_SCOPES)


# ==========================================================
# RANDOM SAFETY REQUIREMENT
# ==========================================================

def random_safety_requirement():

    return random.choice(SAFETY_REQUIREMENTS)


# ==========================================================
# RANDOM SPECIAL INSTRUCTION
# ==========================================================

def random_special_instruction():

    return random.choice(SPECIAL_INSTRUCTIONS)

# ==========================================================
# WORK ORDER TEMPLATE 1
# ==========================================================

def workorder_template_one(event):

    return {

        "title": "Corrective Work Order",

        "problem": f"""
Equipment reported the following issue:

{event['Description']}
""",

        "scope": random_work_scope(),

        "duration": f"{event['Downtime (hrs)']} Hours"

    }

# ==========================================================
# WORK ORDER TEMPLATE 2
# ==========================================================

def workorder_template_two(event):

    return {

        "title": "Preventive Maintenance Work Order",

        "problem": f"""
Scheduled maintenance activity for

{event['Equipment Name']}

Priority :

{event['Priority']}
""",

        "scope": random_work_scope(),

        "duration": f"{event['Downtime (hrs)']} Hours"

    }

# ==========================================================
# WORK ORDER TEMPLATE 3
# ==========================================================

def workorder_template_three(event):

    return {

        "title": "Emergency Work Order",

        "problem": f"""
Emergency response required for

{event['Equipment Name']}.

Issue:

{event['Description']}
""",

        "scope": random_work_scope(),

        "duration": f"{event['Downtime (hrs)']} Hours"

    }

# ==========================================================
# WORK ORDER TEMPLATE 4
# ==========================================================

def workorder_template_four(event):

    return {

        "title": "Equipment Repair Work Order",

        "problem": f"""
Repair request generated for

Equipment ID :

{event['Equipment ID']}

Reported Issue :

{event['Description']}
""",

        "scope": random_work_scope(),

        "duration": f"{event['Downtime (hrs)']} Hours"

    }

# ==========================================================
# MAIN WORK ORDER TEMPLATE
# ==========================================================

def workorder_template(event):

    templates = [

        workorder_template_one,
        workorder_template_two,
        workorder_template_three,
        workorder_template_four

    ]

    selected = random.choice(templates)

    data = selected(event)

    data["tool"] = random_tool()

    data["safety"] = random_safety_requirement()

    data["instruction"] = random_special_instruction()

    return data

# ==========================================================
# INCIDENT TEMPLATE 1
# ==========================================================

def incident_template_one(event):

    return {

        "title": "Equipment Incident Report",

        "description": f"""
An incident was reported involving

{event['Equipment Name']}

Description:

{event['Description']}
""",

        "root_cause": maybe_unknown(f"""
Initial investigation indicates:

{event['Root Cause']}
"""),

        "action": f"""
Immediate corrective action taken:

{event['Corrective Action']}
"""
    }

# ==========================================================
# INCIDENT TEMPLATE 2
# ==========================================================

def incident_template_two(event):

    return {

        "title": "Operational Incident Report",

        "description": f"""
During routine plant operation an incident
occurred involving equipment

{event['Equipment ID']}

Issue Reported:

{event['Description']}
""",

        "root_cause": maybe_unknown(f"""
Failure Category:

{event['Failure Category']}

Root Cause:

{event['Root Cause']}
"""),

        "action": f"""
Operations team responded immediately.

Corrective Action:

{event['Corrective Action']}
"""
    }

# ==========================================================
# INCIDENT TEMPLATE 3
# ==========================================================

def incident_template_three(event):

    return {

        "title": "Safety Incident Report",

        "description": f"""
An operational abnormality was observed
during the {event['Shift']} shift.

Observation:

{event['Description']}
""",

        "root_cause": maybe_unknown(f"""
Severity:

{event['Severity']}

Priority:

{event['Priority']}

Root Cause:

{event['Root Cause']}
"""),

        "action": f"""
Maintenance team secured the equipment
and carried out the following action:

{event['Corrective Action']}
"""
    }

# ==========================================================
# INCIDENT TEMPLATE 4
# ==========================================================

def incident_template_four(event):

    return {

        "title": "Equipment Failure Incident",

        "description": f"""
Equipment

{event['Equipment Name']}

experienced an operational failure.

Reported Problem:

{event['Description']}
""",

        "root_cause": maybe_unknown(f"""
Asset Criticality:

{event['Asset Criticality']}

Root Cause:

{event['Root Cause']}
"""),

        "action": f"""
Corrective maintenance performed.

Action Details:

{event['Corrective Action']}
"""
    }

# ==========================================================
# MAIN INCIDENT TEMPLATE
# ==========================================================

def incident_template(event):

    templates = [

        incident_template_one,

        incident_template_two,

        incident_template_three,

        incident_template_four

    ]

    selected = random.choice(templates)

    data = selected(event)

    data["recommendation"] = random_recommendation()

    data["engineer_remark"] = random_remark()

    data["tool"] = random_tool()

    data["safety"] = random_safety()

    return data

# ==========================================================
# EMAIL TEMPLATE 1
# ==========================================================

def email_template_one(event):

    return {

        "title": "Maintenance Notification Email",

        "subject": f"Maintenance Activity - {event['Equipment Name']}",

        "body": f"""
Dear Team,

This is to inform you that maintenance activity has been performed on
{event['Equipment Name']}.

Issue Reported:

{event['Description']}

Corrective Action Taken:

{event['Corrective Action']}

Equipment has been restored to normal operating condition.

Regards,

Maintenance Department
""",

        "action": "Please monitor the equipment during normal operation."

    }


# ==========================================================
# EMAIL TEMPLATE 2
# ==========================================================

def email_template_two(event):

    return {

        "title": "Equipment Breakdown Notification",

        "subject": f"Equipment Breakdown - {event['Equipment ID']}",

        "body": f"""
Dear Team,

An equipment breakdown occurred involving
{event['Equipment Name']}.

Failure Category:

{event['Failure Category']}

Root Cause:

{event['Root Cause']}

Corrective Action:

{event['Corrective Action']}

Regards,

Maintenance Department
""",

        "action": "Review maintenance schedule and monitor equipment closely."

    }


# ==========================================================
# EMAIL TEMPLATE 3
# ==========================================================

def email_template_three(event):

    return {

        "title": "Inspection Completion Email",

        "subject": f"Inspection Completed - {event['Equipment Name']}",

        "body": f"""
Dear Team,

Inspection activities have been completed successfully.

Equipment:

{event['Equipment Name']}

Inspection Findings:

{event['Description']}

Status:

{event['Status']}

Regards,

Inspection Team
""",

        "action": "No further action is required unless abnormality is observed."

    }


# ==========================================================
# EMAIL TEMPLATE 4
# ==========================================================

def email_template_four(event):

    return {

        "title": "Incident Follow-up Email",

        "subject": f"Incident Follow-up - {event['Equipment Name']}",

        "body": f"""
Dear Team,

This email is regarding the recent incident involving

{event['Equipment Name']}.

Incident Summary:

{event['Description']}

Corrective Action:

{event['Corrective Action']}

Please ensure operational guidelines are followed.

Regards,

Operations Department
""",

        "action": "Share this information with all shift supervisors."

    }


# ==========================================================
# MAIN EMAIL TEMPLATE
# ==========================================================

def email_template(event):

    templates = [

        email_template_one,

        email_template_two,

        email_template_three,

        email_template_four

    ]

    selected = random.choice(templates)

    data = selected(event)

    data["recommendation"] = random_recommendation()

    data["engineer_remark"] = random_remark()

    return data

# ==========================================================
# RCA TEMPLATE 1
# ==========================================================

def rca_template_one(event):

    return {

        "title": "Root Cause Analysis Report",

        "problem": f"""
Equipment {event['Equipment Name']} experienced the
following issue:

{event['Description']}
""",

        "root_cause": maybe_unknown(f"""
Investigation identified the probable root cause:

{event['Root Cause']}
"""),

        "corrective_action": f"""
Corrective action implemented:

{event['Corrective Action']}
""",

        "preventive_action":
        "Increase inspection frequency and monitor equipment performance."

    }


# ==========================================================
# RCA TEMPLATE 2
# ==========================================================

def rca_template_two(event):

    return {

        "title": "Equipment Failure RCA",

        "problem": f"""
Failure occurred in

{event['Equipment Name']}

Failure Category:

{event['Failure Category']}
""",

        "root_cause": maybe_unknown(f"""
Detailed investigation concluded:

{event['Root Cause']}
"""),

        "corrective_action": f"""
Maintenance team performed:

{event['Corrective Action']}
""",

        "preventive_action":
        "Review preventive maintenance schedule."

    }


# ==========================================================
# RCA TEMPLATE 3
# ==========================================================

def rca_template_three(event):

    return {

        "title": "Operational Root Cause Analysis",

        "problem": f"""
Operational abnormality reported during

{event['Shift']} shift.

Description:

{event['Description']}
""",

        "root_cause": maybe_unknown(f"""
Primary cause identified:

{event['Root Cause']}
"""),

        "corrective_action": f"""
Corrective measures:

{event['Corrective Action']}
""",

        "preventive_action":
        "Provide additional operator training."

    }


# ==========================================================
# RCA TEMPLATE 4
# ==========================================================

def rca_template_four(event):

    return {

        "title": "Equipment Reliability RCA",

        "problem": f"""
Reliability issue reported for

{event['Equipment ID']}

Equipment:

{event['Equipment Name']}
""",

        "root_cause": maybe_unknown(f"""
Failure analysis indicates:

{event['Root Cause']}
"""),

        "corrective_action": f"""
Maintenance completed:

{event['Corrective Action']}
""",

        "preventive_action":
        "Perform condition monitoring every week."

    }


# ==========================================================
# MAIN RCA TEMPLATE
# ==========================================================

def rca_template(event):

    templates = [

        rca_template_one,

        rca_template_two,

        rca_template_three,

        rca_template_four

    ]

    selected = random.choice(templates)

    data = selected(event)

    data["recommendation"] = random_recommendation()

    data["engineer_remark"] = random_remark()

    data["tool"] = random_tool()

    data["safety"] = random_safety()

    return data

# ==========================================================
# QUALITY TEMPLATE 1
# ==========================================================


def quality_template_one(event):

    return {

        "title": "Quality Inspection Report",

        "description": f"""
Quality issue identified during inspection
of equipment:

Equipment Name:
{event['Equipment Name']}

Reported Issue:

{event['Description']}
""",

        "findings": maybe_unknown(f"""
Quality inspection findings:

Failure Category:
{event['Failure Category']}

Severity:
{event['Severity']}

Priority:
{event['Priority']}

Equipment condition requires corrective action.
"""),


        "non_conformance": f"""
Non-conformance observed due to:

{event['Root Cause']}

The issue affected normal equipment performance.
""",


        "verification": """
Corrective action verification completed.

Equipment performance checked and found
within acceptable operating parameters.
""",


        "status": "Quality issue resolved and closed."

    }



# ==========================================================
# QUALITY TEMPLATE 2
# ==========================================================


def quality_template_two(event):

    return {

        "title": "Non Conformance Quality Report",

        "description": f"""
A quality deviation was reported for:

{event['Equipment Name']}

Observation:

{event['Description']}
""",


        "findings": maybe_unknown(f"""
Detailed quality analysis performed.

Asset Criticality:

{event['Asset Criticality']}

Status:

{event['Status']}
"""),


        "non_conformance": f"""
Non-conformance was linked with:

Failure Category:

{event['Failure Category']}

Root Cause:

{event['Root Cause']}
""",


        "verification": """
Corrective action effectiveness verified
through operational testing.
""",


        "status": "Accepted after corrective action implementation."

    }



# ==========================================================
# QUALITY TEMPLATE 3
# ==========================================================


def quality_template_three(event):

    return {

        "title": "Equipment Quality Assessment Report",


        "description": f"""
Quality assessment initiated after abnormal
equipment behavior.

Equipment:

{event['Equipment Name']}

Issue:

{event['Description']}
""",


        "findings": maybe_unknown(f"""
Assessment findings:

Severity:
{event['Severity']}

Failure Category:
{event['Failure Category']}

Inspection completed successfully.
"""),


        "non_conformance": f"""
Detected non-conformance:

{event['Root Cause']}

Corrective measures recommended.
""",


        "verification": """
Follow-up inspection completed.

Equipment performance monitored after repair.
""",


        "status": "Monitoring required after corrective action."

    }



# ==========================================================
# QUALITY TEMPLATE 4
# ==========================================================


def quality_template_four(event):

    return {

        "title": "Quality Failure Investigation Report",


        "description": f"""
Investigation started for quality related
failure involving:

Equipment ID:

{event['Equipment ID']}


Problem Description:

{event['Description']}
""",


        "findings": maybe_unknown(f"""
Investigation findings:

Root Cause Category:

{event['Failure Category']}

Priority:

{event['Priority']}
"""),


        "non_conformance": f"""
Quality failure occurred because:

{event['Root Cause']}

Corrective action:

{event['Corrective Action']}
""",


        "verification": """
Verification carried out after corrective
maintenance activity.

No further abnormality observed.
""",


        "status": "Investigation completed."

    }



# ==========================================================
# MAIN QUALITY TEMPLATE
# ==========================================================


def quality_template(event):


    templates = [

        quality_template_one,

        quality_template_two,

        quality_template_three,

        quality_template_four

    ]


    selected = random.choice(templates)


    data = selected(event)


    data["recommendation"] = random_recommendation()


    data["engineer_remark"] = random_remark()


    data["tool"] = random_tool()


    data["safety"] = random_safety()


    return data

# ==========================================================
# SAFETY TEMPLATE 1
# ==========================================================

def safety_template_one(event):

    return {

        "title": "Safety Observation Report",

        "description": f"""
Safety observation recorded for:

Equipment Name:
{event['Equipment Name']}

Observation:

{event['Description']}
""",


        "hazard": f"""
Potential hazard identified:

Failure Category:

{event['Failure Category']}

Severity:

{event['Severity']}
""",


        "risk": f"""
Risk Level:

{event['Severity']}

Asset Criticality:

{event['Asset Criticality']}
""",


        "immediate_action": f"""
Immediate action taken:

{event['Corrective Action']}
""",


        "preventive_action": """
Conduct regular safety inspections
and ensure compliance with safety procedures.
"""

    }



# ==========================================================
# SAFETY TEMPLATE 2
# ==========================================================

def safety_template_two(event):

    return {

        "title": "Safety Incident Investigation",


        "description": f"""
Safety incident occurred during:

{event['Shift']} shift.


Incident Details:

{event['Description']}
""",


        "hazard": f"""
Hazard category:

{event['Failure Category']}


Root Cause:

{event['Root Cause']}
""",


        "risk": f"""
Risk Priority:

{event['Priority']}


Severity:

{event['Severity']}
""",


        "immediate_action": f"""
Immediate corrective action:

{event['Corrective Action']}
""",


        "preventive_action": """
Provide safety awareness training
and improve preventive monitoring.
"""

    }



# ==========================================================
# MAIN SAFETY TEMPLATE
# ==========================================================

def safety_template(event):

    templates = [

        safety_template_one,

        safety_template_two

    ]


    selected = random.choice(templates)


    data = selected(event)


    data["recommendation"] = random_recommendation()


    data["engineer_remark"] = random_remark()


    data["tool"] = random_tool()


    data["safety"] = random_safety()


    return data

# ==========================================================
# CALIBRATION TEMPLATE 1
# ==========================================================

def calibration_template_one(event):

    return {

        "title": "Calibration Certificate Report",


        "objective": f"""
Calibration activity initiated for equipment:

{event['Equipment Name']}

The objective was to verify measurement accuracy
and ensure instrument performance within acceptable limits.
""",


        "findings": f"""
Calibration inspection performed.

Instrument:

{event['Equipment Name']}

Observation:

{event['Description']}
""",


        "deviation": """
No significant calibration deviation observed.
Instrument readings were compared with standard reference values.
""",


        "adjustment": """
No adjustment required.

Instrument performance was within acceptable tolerance limits.
""",


        "verification": """
Calibration verification completed successfully.

Equipment is approved for normal operation.
"""

    }



# ==========================================================
# CALIBRATION TEMPLATE 2
# ==========================================================

def calibration_template_two(event):

    return {


        "title":"Instrument Calibration Report",


        "objective": f"""
Calibration check performed for:

{event['Equipment ID']}

Purpose was to verify instrument accuracy
and detect measurement deviation.
""",


        "findings": f"""
Calibration findings:

Equipment:

{event['Equipment Name']}

Observed Condition:

{event['Description']}
""",


        "deviation": f"""
Calibration deviation identified.

Possible Cause:

{event['Root Cause']}
""",


        "adjustment": f"""
Adjustment performed.

Corrective Action:

{event['Corrective Action']}
""",


        "verification": """
Post-adjustment verification completed.

Instrument accuracy restored successfully.
"""

    }



# ==========================================================
# CALIBRATION TEMPLATE 3
# ==========================================================

def calibration_template_three(event):

    return {


        "title":"Instrument Accuracy Verification Report",


        "objective": f"""
Routine calibration verification conducted
for {event['Equipment Name']}.
""",


        "findings": f"""
Inspection result:

{event['Description']}

Instrument condition evaluated successfully.
""",


        "deviation": """
Minor deviation observed during calibration testing.
""",


        "adjustment": """
Calibration parameters adjusted according to specification.
""",


        "verification": """
Final calibration test completed successfully.
Equipment released for operation.
"""

    }



# ==========================================================
# CALIBRATION TEMPLATE 4
# ==========================================================

def calibration_template_four(event):

    return {


        "title":"Calibration Failure Analysis Report",


        "objective": """
Detailed calibration assessment performed
after abnormal instrument reading.
""",


        "findings": f"""
Calibration investigation:

Failure Category:

{event['Failure Category']}

Description:

{event['Description']}
""",


        "deviation": f"""
Deviation analysis:

Root Cause:

{event['Root Cause']}
""",


        "adjustment": f"""
Corrective calibration action:

{event['Corrective Action']}
""",


        "verification": """
Instrument tested after calibration activity.

Performance verified successfully.
"""

    }



# ==========================================================
# MAIN CALIBRATION TEMPLATE
# ==========================================================

def calibration_template(event):


    templates=[

        calibration_template_one,
        calibration_template_two,
        calibration_template_three,
        calibration_template_four

    ]


    selected=random.choice(templates)


    data=selected(event)


    data["recommendation"]=random_recommendation()


    data["engineer_remark"]=random_remark()


    data["tool"]=random_tool()


    data["safety"]=random_safety()


    return data