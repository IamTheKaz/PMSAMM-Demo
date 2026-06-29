# ================================================================
# CLAUDE PRINT DEFECT ANALYZER - Haven-1 3D Printer Monitor
# ================================================================
# AWS Lambda function for analyzing 3D print defects using Claude AI
# Integrated with SAM model predictions and AWS Rekognition results.
# Manages print job history, autonomous corrections, and crew notifications.
#
# Purpose: Analyze defects detected in microgravity 3D printing,
#          determine risk levels, and notify crew with corrective actions.
# ================================================================

import json
import boto3
import base64
import re
import uuid
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

# ================================================================
# AWS SERVICE CLIENTS
# ================================================================
bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
TABLE_NAME = "SAM_PMSAMM_Logs"

# ================================================================
# CONFIGURATION
# ================================================================
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# CORS headers for API responses
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST,OPTIONS"
}

# ================================================================
# SYSTEM PROMPT - Haven-1 AI Analysis Instructions
# ================================================================
# This prompt defines Claude's behavior as Haven-1's monitoring specialist.
# It specifies the analysis format, defect assessment criteria, and
# crew notification rules for different part criticality levels.
SYSTEM_PROMPT = """You are Haven-1 AI Monitoring Specialist. Analyze 3D print defects for crew aboard space station Haven-1. Be concise and direct. Max 450 words total.

You will receive a report containing: telemetry data, SAM model prediction, Rekognition results, crew member name, part criticality level, print progress, print history, and an image.

RESPOND IN THIS FORMAT:

## Defect Assessment
What SAM/Rekognition detected and what the image confirms. If SAM confidence is below 55%, ignore SAM labels and make your own visual determination from the image. Name novel defects descriptively.

## Microgravity Impact
2-3 sentences on how this defect behaves in microgravity (FOD drift, cooling, surface tension).

## Risk & Safety
Risk level (LOW/MEDIUM/HIGH) with brief justification. If defect is fixable with parameter changes, state continuation risk (LOW/HIGH).

## Corrective Actions
3-5 numbered actions with exact parameter values. State specific telemetry changes made. Include FOD sweep if debris risk exists.

## Filament Waste Estimate
Estimate filament wasted based on print progress % and part criticality. Format: "Estimated [X]g wasted of approximately [Y]g total job."

## Crew Notification Decision
Apply these rules exactly:

LEVEL 1 NON-CRITICAL:
- Fixable defect + LOW continuation risk: NO crew notification. State exact autonomous telemetry corrections applied.
- Catastrophic failure (spaghetti/nest/abort): NOTIFY [crew member name]. Stop print. Include waste estimate.
- End of print (progress >= 98%): NOTIFY [crew member name] with full change log.

LEVEL 2 SEMI-CRITICAL:
- Fixable defect + LOW continuation risk: NO crew notification. State exact autonomous corrections applied.
- Fixable defect + HIGH continuation risk: NOTIFY [crew member name]. Pause for decision.
- Catastrophic failure: NOTIFY [crew member name]. Stop print. Include waste estimate.
- End of print (progress >= 98%): NOTIFY [crew member name] with full change log.

LEVEL 3 MISSION-CRITICAL:
- Any defect: NOTIFY [crew member name]. CREW_APPROVAL required. Print halted.
- End of print (progress >= 98%): NOTIFY [crew member name] with full change log.

ALL LEVELS - End of print notification format:
"[Crew member name] - Bay 3 print complete. Status: [PASS/FAIL]. Autonomous corrections applied: [list or NONE]. Manual crew interventions: [list or NONE]. Estimated filament used: [X]g."

## Compliance Log
action_required: NONE
risk_level: LOW
notify_crew: false
detected_defect: NONE
crew_message: NONE
autonomous_corrections: NONE
telemetry_adjustments: {}

Replace values with your actual determination.
action_required: NONE, PAUSE_AND_INSPECT, CREW_APPROVAL, ABORT
notify_crew: true or false
crew_message: the actual message to send to the crew member or NONE
autonomous_corrections: plain text summary of all changes applied or NONE
telemetry_adjustments: JSON object with only changed fields from: nozzle, bed, speed, retraction, extrude, layer
Example: {"nozzle": 205, "retraction": 1.4, "speed": 55}
If no autonomous parameter changes, use: {}"""


# ================================================================
# UTILITY FUNCTIONS - API Response Handling
# ================================================================
def respond(status, body_dict):
    """
    Format HTTP response for API Gateway.
    
    Args:
        status (int): HTTP status code
        body_dict (dict): Response body as dictionary
        
    Returns:
        dict: Formatted API Gateway response
    """
    return {
        "statusCode": status,
        "headers": CORS,
        "body": json.dumps(body_dict)
    }


# ================================================================
# DATABASE FUNCTIONS - DynamoDB Logging
# ================================================================
def write_log(item):
    """
    Write analysis or event log entry to DynamoDB.
    
    Args:
        item (dict): Log entry containing job_id, timestamp, analysis results
    """
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(Item=item)
        print(f"Logged: {item.get('job_id')} / {item.get('entry_type')}")
    except Exception as e:
        print(f"DynamoDB write error: {e}")


def get_job_history(job_id):
    """
    Retrieve all previous log entries for a print job.
    
    Args:
        job_id (str): Unique job identifier
        
    Returns:
        list: Sorted list of log entries for this job
    """
    try:
        table = dynamodb.Table(TABLE_NAME)
        result = table.query(
            KeyConditionExpression=Key("job_id").eq(job_id)
        )
        items = result.get("Items", [])
        # Sort chronologically by timestamp
        items.sort(key=lambda x: x.get("timestamp", ""))
        return items
    except Exception as e:
        print(f"DynamoDB query error: {e}")
        return []


# ================================================================
# DEFECT ANALYSIS FUNCTIONS
# ================================================================
def normalize_defect(label):
    """
    Normalize defect label variants to base categories.
    
    Converts different naming conventions (underextrusion, under_extrusion, etc.)
    to standard categories for consistent comparison and history tracking.
    
    Args:
        label: Raw defect label from SAM or visual inspection
        
    Returns:
        str: Normalized defect category (SPAGHETTI, STRINGING, UNDEREXTRUSION, etc.)
    """
    l = str(label or "").strip().lower().replace("_", " ").replace("-", " ")
    if "spaghet" in l: return "SPAGHETTI"
    if "string" in l or "wisp" in l or "hair" in l: return "STRINGING"
    if "under" in l or "extrusion" in l: return "UNDEREXTRUSION"
    if l in ("none", "good", "", "no defect", "nominal"): return "NONE"
    return l.upper()  # novel defect - keep normalized


def analyze_history(history):
    """
    Analyze print job history to identify patterns and trigger abort conditions.
    
    Implements abort logic:
    - Rule 1: Same defect appears 2+ times after autonomous corrections
    - Rule 2: Multiple different defect types in same print
    
    Args:
        history (list): Log entries for this job
        
    Returns:
        dict: Analysis with defect_counts, corrections, abort decision, and reason
    """
    defect_counts = {}
    previous_corrections = []
    unique_defects = set()

    # Aggregate defects and corrections from history
    for entry in history:
        entry_type = entry.get("entry_type", "")
        if "CLAUDE_ANALYSIS" in entry_type:
            raw_defect = entry.get("detected_defect", "")
            defect = normalize_defect(raw_defect)
            if defect and defect not in ("UNKNOWN", "NONE", ""):
                defect_counts[defect] = defect_counts.get(defect, 0) + 1
                unique_defects.add(defect)
            correction = entry.get("autonomous_corrections", "")
            if correction and correction.strip().lower() not in ("none", ""):
                previous_corrections.append(correction)

    should_abort = False
    abort_reason = ""

    # Rule 1: Same defect appeared more than once after corrections were applied
    for defect, count in defect_counts.items():
        if count >= 2 and len(previous_corrections) > 0:
            should_abort = True
            abort_reason = (
                f"PERSISTENT ERROR: {defect} detected {count} times despite "
                f"autonomous corrections ({'; '.join(previous_corrections)}). "
                f"Print integrity compromised."
            )
            break

    # Rule 2: Two or more different defect types in same print
    if not should_abort and len(unique_defects) >= 2:
        should_abort = True
        abort_reason = (
            f"UNSTABLE PRINT: Multiple defect types detected in same job "
            f"({', '.join(unique_defects)}). Print cannot be corrected autonomously."
        )

    return {
        "defect_counts": defect_counts,
        "previous_corrections": previous_corrections,
        "unique_defects": list(unique_defects),
        "should_abort": should_abort,
        "abort_reason": abort_reason
    }


def extract_compliance(raw_text):
    """
    Extract compliance fields from Claude's analysis response using regex.
    
    Parses Claude's structured output to extract:
    - action_required: (NONE, PAUSE_AND_INSPECT, CREW_APPROVAL, ABORT)
    - risk_level: (LOW, MEDIUM, HIGH)
    - notify_crew: (true/false)
    - detected_defect: Defect classification
    - crew_message: Message to send to crew
    - autonomous_corrections: Summary of parameter changes applied
    - telemetry_adjustments: JSON object with specific parameter values
    
    Args:
        raw_text (str): Claude's full response text
        
    Returns:
        tuple: (action, risk, notify, defect, crew_msg, auto_correct, telemetry_adj)
    """
    # Use regex to extract compliance fields (flexible format handling)
    am = re.search(r"action[_\s]required\s*:\s*(NONE|PAUSE_AND_INSPECT|CREW_APPROVAL|ABORT)", raw_text, re.I)
    rm = re.search(r"risk[_\s]level\s*:\s*(LOW|MEDIUM|HIGH)", raw_text, re.I)
    nm = re.search(r"notify[_\s]crew\s*:\s*(true|false)", raw_text, re.I)

    # Flexible detected_defect — handles direct value on same line
    dm = re.search(r"detected[_\s]defect\s*:\s*([^\n]+)", raw_text, re.I)

    # crew_message, autonomous_corrections and telemetry_adjustments
    cm = re.search(r"crew[_\s]message\s*:\s*([^\n]+)", raw_text, re.I)
    ac = re.search(r"autonomous[_\s]corrections\s*:\s*([^\n]+)", raw_text, re.I)
    ta = re.search(r"telemetry[_\s]adjustments\s*:(\s*\{[^}]*\})", raw_text, re.I)

    # Extract and normalize values
    action       = am.group(1).upper().strip() if am else "MANUAL_REVIEW"
    risk         = rm.group(1).upper().strip() if rm else "UNKNOWN"
    notify       = nm.group(1).lower() == "true" if nm else (action != "NONE")
    defect       = dm.group(1).strip() if dm else "UNKNOWN"
    crew_msg     = cm.group(1).strip() if cm and cm.group(1).strip().lower() != "none" else ""
    auto_correct = ac.group(1).strip() if ac and ac.group(1).strip().lower() != "none" else ""

    # Parse telemetry adjustments JSON
    telemetry_adj = {}
    if ta:
        try:
            telemetry_adj = json.loads(ta.group(1).strip())
        except:
            telemetry_adj = {}

    # Clean up defect - strip markdown bold
    defect = re.sub(r"\*+", "", defect).strip()

    # Determine if crew notification is required based on action
    if action in ("MANUAL_REVIEW", "CREW_APPROVAL", "ABORT"):
        notify = True

    return action, risk, notify, defect, crew_msg, auto_correct, telemetry_adj


def determine_override(sam_label, detected_defect):
    """
    Determine if Claude's defect determination overrides SAM model prediction.
    
    Compares SAM label with Claude's visual analysis to flag discrepancies.
    Returns "sam_deferred" if SAM has low confidence, "false" if they match,
    "true" if they conflict.
    
    Args:
        sam_label (str): SAM model's predicted defect
        detected_defect (str): Claude's defect determination
        
    Returns:
        str: "sam_deferred", "false" (match), or "true" (override)
    """
    sam = (sam_label or "").strip().lower()
    claude = (detected_defect or "").strip().lower()

    # SAM defers to visual inspection
    if sam in ("low confidence (unsure)", "unsure", ""):
        return "sam_deferred"

    # Normalize both strings for comparison
    sam_norm    = re.sub(r"[\s_\-]", "", sam)
    claude_norm = re.sub(r"[\s_\-]", "", claude)

    # Check if labels overlap or match
    if sam_norm in claude_norm or claude_norm in sam_norm:
        return "false"

    # Labels conflict
    return "true"


# ================================================================
# LAMBDA HANDLER - Main Entry Point
# ================================================================
def lambda_handler(event, context):
    """
    AWS Lambda handler for print defect analysis requests.
    
    Supports three actions:
    1. "get_logs" - Retrieve job history
    2. "log_sam" - Log SAM model run
    3. (default) - Run full Claude analysis with Bedrock
    
    Args:
        event: API Gateway Lambda event
        context: Lambda context
        
    Returns:
        dict: API Gateway formatted response
    """
    # Extract HTTP method (support both ALB and API Gateway formats)
    method = ""
    try:
        method = event["requestContext"]["http"]["method"]
    except:
        method = event.get("httpMethod", "POST")

    # Handle CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS, "body": ""}

    # Parse request body
    try:
        raw_body = event.get("body", "{}")
        if event.get("isBase64Encoded", False):
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        body = json.loads(raw_body)
    except Exception as e:
        return respond(400, {"error": "Bad request body: " + str(e)})

    # ================================================================
    # ACTION: GET_LOGS - Retrieve job history
    # ================================================================
    if body.get("action") == "get_logs":
        job_id = body.get("job_id", "")
        if not job_id:
            return respond(400, {"error": "job_id required"})
        try:
            items = get_job_history(job_id)
            return respond(200, {"logs": items})
        except Exception as e:
            return respond(500, {"error": str(e)})

    # ================================================================
    # ACTION: LOG_SAM - Record SAM model prediction without analysis
    # ================================================================
    if body.get("action") == "log_sam":
        ts = datetime.now(timezone.utc).isoformat()
        item = {
            "job_id":           body.get("job_id", "UNKNOWN"),
            "entry_type":       "SAM_RUN#" + ts,
            "timestamp":        ts,
            "crew_member":      body.get("crew_member", ""),
            "part_description": body.get("part_description", ""),
            "criticality":      str(body.get("criticality", "")),
            "print_progress":   str(body.get("print_progress", "")),
            "sam_confidence":   str(body.get("sam_confidence", "")),
            "sam_label":        body.get("sam_label", ""),
            "bay_id":           "BAY-3",
            "serial_number":    "3DP-H1-007"
        }
        write_log(item)
        return respond(200, {"logged": True})

    # ================================================================
    # ACTION: DEFAULT - Full Bedrock Analysis
    # ================================================================
    report_text = body.get("report", "")
    image_b64   = body.get("image", None)
    image_type  = body.get("imageType", "image/jpeg")
    job_id      = body.get("job_id", str(uuid.uuid4()))
    meta        = body.get("meta", {})

    if not report_text:
        return respond(400, {"error": "No report text provided"})

    # ================================================================
    # CHECK JOB HISTORY - Determine if print should be aborted
    # ================================================================
    history          = get_job_history(job_id)
    history_analysis = analyze_history(history)

    print(f"Job {job_id} history: {history_analysis}")

    # Auto-abort if history shows persistent errors or multiple defects
    if history_analysis["should_abort"]:
        ts          = datetime.now(timezone.utc).isoformat()
        crew_member = meta.get("crew_member", "Crew")
        abort_reason = history_analysis["abort_reason"]
        crew_msg    = (
            f"{crew_member} - PRINT ABORTED. Bay 3 print job terminated. "
            f"{abort_reason} Immediate FOD sweep required."
        )
        abort_text = (
            "## Defect Assessment\n"
            f"{abort_reason}\n\n"
            "## Crew Notification Decision\n"
            f"NOTIFY {crew_member}. Print aborted due to unresolvable defect pattern.\n\n"
            "## Compliance Log\n"
            "action_required: ABORT\n"
            "risk_level: HIGH\n"
            "notify_crew: true\n"
            f"detected_defect: {', '.join(history_analysis['unique_defects'])}\n"
            f"crew_message: {crew_msg}\n"
            "autonomous_corrections: NONE - ABORT TRIGGERED\n"
        )
        log_item = {
            "job_id":                 job_id,
            "entry_type":             "ABORT#" + ts,
            "timestamp":              ts,
            "crew_member":            crew_member,
            "part_description":       meta.get("part_description", ""),
            "criticality":            str(meta.get("criticality", "")),
            "print_progress":         str(meta.get("print_progress", "")),
            "risk_level":             "HIGH",
            "action_required":        "ABORT",
            "notify_crew":            "true",
            "detected_defect":        ", ".join(history_analysis["unique_defects"]),
            "crew_message":           crew_msg,
            "autonomous_corrections": "NONE - ABORT TRIGGERED",
            "analysis_text":          abort_reason[:4000],
            "claude_override":        "N/A - ABORT",
            "sam_original_label":     meta.get("sam_label", ""),
            "claude_determination":   ", ".join(history_analysis["unique_defects"]),
            "bay_id":                 "BAY-3",
            "serial_number":          "3DP-H1-007"
        }
        write_log(log_item)
        return respond(200, {
            "response":               abort_text,
            "job_id":                 job_id,
            "action_required":        "ABORT",
            "risk_level":             "HIGH",
            "notify_crew":            True,
            "detected_defect":        ", ".join(history_analysis["unique_defects"]),
            "crew_message":           crew_msg,
            "autonomous_corrections": ""
        })

    # ================================================================
    # BUILD HISTORY CONTEXT - Include previous defects and corrections
    # ================================================================
    if history_analysis["defect_counts"]:
        history_block = "\n-- PRINT HISTORY FOR THIS JOB ----------------------\n"
        for defect, count in history_analysis["defect_counts"].items():
            history_block += f"  {defect}: detected {count} time(s)\n"
        if history_analysis["previous_corrections"]:
            history_block += "  Previous corrections applied:\n"
            for c in history_analysis["previous_corrections"]:
                history_block += f"    - {c}\n"
        report_text = report_text + history_block

    # ================================================================
    # INVOKE CLAUDE VIA BEDROCK - Get AI analysis
    # ================================================================
    content = []
    if image_b64:
        # Handle base64 encoded image (may include data URL prefix)
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        media_type = image_type if image_type in ["image/jpeg","image/png","image/gif","image/webp"] else "image/jpeg"
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": image_b64}
        })
    content.append({"type": "text", "text": report_text})

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": content}]
            })
        )

        response_body = json.loads(response["body"].read())
        raw_text = response_body["content"][0]["text"].strip()

        # Handle JSON-formatted responses from Claude
        clean = raw_text
        if clean.startswith("{") or "```" in clean:
            clean = re.sub(r"```[a-z]*", "", clean).replace("```", "").strip()
            try:
                parsed       = json.loads(clean)
                summary      = parsed.get("analysis_summary", "")
                recs         = parsed.get("recommendations", [])
                rec_text     = "\n".join(recs) if isinstance(recs, list) else str(recs)
                action       = parsed.get("action_required", "NONE")
                risk         = parsed.get("risk_level", "UNKNOWN")
                notify       = str(parsed.get("notify_crew", False)).lower()
                defect       = parsed.get("detected_defect", "UNKNOWN")
                raw_text = (
                    "## Analysis\n" + summary + "\n\n"
                    "## Recommendations\n" + rec_text + "\n\n"
                    "## Compliance Log\n"
                    "action_required: " + action + "\n"
                    "risk_level: " + risk + "\n"
                    "notify_crew: " + notify + "\n"
                    "detected_defect: " + defect + "\n"
                    "crew_message: NONE\n"
                    "autonomous_corrections: NONE\n"
                )
            except:
                pass

        # Extract structured compliance data from Claude's response
        action, risk, notify, defect, crew_msg, auto_correct, telemetry_adj = extract_compliance(raw_text)

        sam_label     = meta.get("sam_label", "")
        override_flag = determine_override(sam_label, defect)

        ts = datetime.now(timezone.utc).isoformat()

        # ================================================================
        # LOG CLAUDE ANALYSIS - Write to DynamoDB
        # ================================================================
        log_item = {
            "job_id":                 job_id,
            "entry_type":             "CLAUDE_ANALYSIS#" + ts,
            "timestamp":              ts,
            "crew_member":            meta.get("crew_member", ""),
            "part_description":       meta.get("part_description", ""),
            "criticality":            str(meta.get("criticality", "")),
            "print_progress":         str(meta.get("print_progress", "")),
            "sam_confidence":         str(meta.get("sam_confidence", "")),
            "sam_label":              sam_label,
            "risk_level":             risk,
            "action_required":        action,
            "notify_crew":            str(notify),
            "detected_defect":        defect,
            "crew_message":           crew_msg,
            "autonomous_corrections": auto_correct,
            "analysis_text":          raw_text[:4000],
            "claude_override":        override_flag,
            "sam_original_label":     sam_label,
            "claude_determination":   defect,
            "telemetry_adjustments":  json.dumps(telemetry_adj),
            "bay_id":                 "BAY-3",
            "serial_number":          "3DP-H1-007"
        }
        write_log(log_item)

        # Log crew notification separately if required
        if notify and crew_msg:
            notif_item = {**log_item,
                "entry_type": "CREW_NOTIFICATION#" + ts,
                "timestamp":  ts
            }
            write_log(notif_item)

        # Return structured response to client
        return respond(200, {
            "response":               raw_text,
            "job_id":                 job_id,
            "action_required":        action,
            "risk_level":             risk,
            "notify_crew":            notify,
            "detected_defect":        defect,
            "crew_message":           crew_msg,
            "autonomous_corrections": auto_correct,
            "claude_override":        override_flag,
            "telemetry_adjustments":  telemetry_adj
        })

    except Exception as e:
        return respond(500, {"error": str(e)})
