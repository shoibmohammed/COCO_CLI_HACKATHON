# Governed External MCP Server — MFG Predictive Maintenance V2
# Co-authored with CoCo
"""
mcp_server.py

External Python FastMCP Server exposing 7 governed tools for predictive maintenance:
1. get_machine_context (Read)
2. get_machine_risk (Read)
3. get_oee_metrics (Read)
4. search_maintenance_docs (Read)
5. get_work_order (Read)
6. create_work_order (Governed Action -> STATUS = PENDING_APPROVAL)
7. request_jira_ticket (Governed Ticketing Action -> Enqueues JIRA_INTEGRATION_QUEUE)
8. search_web_oem (Layer 2 External OEM Knowledge)

ARCHITECTURE & GOVERNANCE BOUNDARIES:
- External MCP Client -> FastMCP Server -> Snowflake / AI Guardrails
- AI/MCP can CREATE work orders strictly as STATUS = 'PENDING_APPROVAL' (NO AUTO-APPROVAL).
- request_jira_ticket BLOCKS if WORK_ORDERS.STATUS != 'APPROVED'.
- Zero credential exposure in tool responses, logs, or code.
- All queries strictly parameterized with centralized table identifiers.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List

try:
    from fastmcp import FastMCP
except ImportError:
    class FastMCP:
        def __init__(self, *args, **kwargs):
            pass
        def tool(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator
        def run(self, *args, **kwargs):
            pass

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import table
from snowflake_connection import get_snowflake_session
from services.jira_queue_service import enqueue_jira_request, check_work_order_approved, check_existing_success, get_queue_status
from services.ai_guardrails import validate_work_order_creation, validate_machine_id
from services.document_service import search_documents, get_relevant_document_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp_server")

# Initialize FastMCP Server
mcp = FastMCP("MFG_Predictive_Maintenance_MCP_Server")


def _get_session():
    """Helper to acquire active Snowpark/Snowflake session."""
    session, msg, is_local = get_snowflake_session()
    if session is None:
        raise RuntimeError(f"Failed to acquire Snowflake session: {msg}")
    return session


@mcp.tool()
def get_machine_context(machine_id: str) -> Dict[str, Any]:
    """
    Returns verified Snowflake machine telemetry, health indicators, supplier, and part context.
    Does not allow telemetry calculation or fabrication.
    """
    cleaned_id = machine_id.strip()
    session = _get_session()
    
    health_tbl = table("MACHINE_HEALTH_RT")
    risk_tbl = f"{health_tbl.rsplit('.', 1)[0]}.MACHINE_RISK_UNIFIED"
    
    rows = session.sql(f"""
        SELECT h.machine_id, h.machine_name, h.plant, h.line_name, h.criticality,
               h.telemetry_ts, h.vibration_mm_s, h.temperature_c, h.rpm, h.pressure_bar, h.power_kw,
               h.supplier, h.bearing_part_number, h.bearing_lead_days,
               r.statistical_risk_score, r.ml_failure_probability, r.unified_risk_score,
               r.top_reason, r.failure_class
        FROM {health_tbl} h
        LEFT JOIN {risk_tbl} r ON h.machine_id = r.machine_id
        WHERE h.machine_id = ?
    """, params=[cleaned_id]).collect()
    
    if not rows:
        return {
            "status": "NOT_FOUND",
            "machine_id": cleaned_id,
            "message": f"Machine {cleaned_id} not found in Snowflake MACHINE_HEALTH_RT."
        }
        
    r = rows[0]
    return {
        "status": "SUCCESS",
        "machine_id": r["MACHINE_ID"],
        "machine_name": r.get("MACHINE_NAME"),
        "plant": r.get("PLANT"),
        "line_name": r.get("LINE_NAME"),
        "criticality": r.get("CRITICALITY"),
        "telemetry_ts": str(r.get("TELEMETRY_TS")),
        "vibration_mm_s": r.get("VIBRATION_MM_S"),
        "temperature_c": r.get("TEMPERATURE_C"),
        "rpm": r.get("RPM"),
        "pressure_bar": r.get("PRESSURE_BAR"),
        "power_kw": r.get("POWER_KW"),
        "supplier": r.get("SUPPLIER"),
        "bearing_part_number": r.get("BEARING_PART_NUMBER"),
        "bearing_lead_days": r.get("BEARING_LEAD_DAYS"),
        "statistical_risk_score": r.get("STATISTICAL_RISK_SCORE"),
        "ml_failure_probability": r.get("ML_FAILURE_PROBABILITY"),
        "unified_risk_score": r.get("UNIFIED_RISK_SCORE"),
        "top_reason": r.get("TOP_REASON"),
        "failure_class": r.get("FAILURE_CLASS")
    }


@mcp.tool()
def get_machine_risk(machine_id: str) -> Dict[str, Any]:
    """
    Returns verified Snowflake statistical risk, ML failure probability, unified risk, RUL, and risk classification.
    Does not calculate probabilities or alter ML model values inside MCP.
    """
    cleaned_id = machine_id.strip()
    session = _get_session()
    
    health_tbl = table("MACHINE_HEALTH_RT")
    risk_tbl = f"{health_tbl.rsplit('.', 1)[0]}.MACHINE_RISK_UNIFIED"
    rul_tbl = f"{health_tbl.rsplit('.', 1)[0]}.RUL_PREDICTIONS"
    
    risk_rows = session.sql(f"""
        SELECT machine_id, statistical_risk_score, ml_failure_probability, unified_risk_score,
               top_reason, failure_class
        FROM {risk_tbl}
        WHERE machine_id = ?
    """, params=[cleaned_id]).collect()
    
    rul_rows = session.sql(f"""
        SELECT estimated_rul_hours, confidence, degradation_rate_per_hr, rul_status
        FROM {rul_tbl}
        WHERE machine_id = ?
        ORDER BY scored_at DESC LIMIT 1
    """, params=[cleaned_id]).collect()
    
    if not risk_rows:
        return {
            "status": "NOT_FOUND",
            "machine_id": cleaned_id,
            "message": f"Risk predictions for {cleaned_id} not found."
        }
        
    rk = risk_rows[0]
    rul_data = rul_rows[0] if rul_rows else {}
    
    risk_val = rk.get("UNIFIED_RISK_SCORE") or 0.0
    priority = "P1" if risk_val >= 0.75 else ("P2" if risk_val >= 0.50 else "P3")
    
    return {
        "status": "SUCCESS",
        "machine_id": rk["MACHINE_ID"],
        "statistical_risk_score": rk.get("STATISTICAL_RISK_SCORE"),
        "ml_failure_probability": rk.get("ML_FAILURE_PROBABILITY"),
        "unified_risk_score": risk_val,
        "priority_classification": priority,
        "top_reason": rk.get("TOP_REASON"),
        "failure_class": rk.get("FAILURE_CLASS"),
        "estimated_rul_hours": rul_data.get("ESTIMATED_RUL_HOURS"),
        "rul_confidence": rul_data.get("CONFIDENCE"),
        "rul_status": rul_data.get("RUL_STATUS")
    }


@mcp.tool()
def get_oee_metrics(machine_id: Optional[str] = None, time_range: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns verified Snowflake OEE metrics (Availability, Performance, Quality, OEE).
    Reuses existing OEE calculation logic.
    """
    session = _get_session()
    oee_tbl = table("OEE_METRICS_RT")
    
    if machine_id:
        rows = session.sql(f"""
            SELECT machine_id, availability, performance, quality, oee, calculation_ts
            FROM {oee_tbl}
            WHERE machine_id = ?
            ORDER BY calculation_ts DESC LIMIT 10
        """, params=[str(machine_id).strip()]).collect()
    else:
        rows = session.sql(f"""
            SELECT machine_id, availability, performance, quality, oee, calculation_ts
            FROM {oee_tbl}
            ORDER BY calculation_ts DESC LIMIT 10
        """).collect()
    
    if not rows:
        return {"status": "NOT_FOUND", "message": "No OEE metrics found."}
        
    metrics_list = []
    for r in rows:
        metrics_list.append({
            "machine_id": r["MACHINE_ID"],
            "availability": r.get("AVAILABILITY"),
            "performance": r.get("PERFORMANCE"),
            "quality": r.get("QUALITY"),
            "oee": r.get("OEE"),
            "timestamp": str(r.get("CALCULATION_TS"))
        })
        
    return {
        "status": "SUCCESS",
        "record_count": len(metrics_list),
        "metrics": metrics_list
    }


@mcp.tool()
def search_maintenance_docs(query: str) -> Dict[str, Any]:
    """
    Performs Cortex Search / document retrieval over maintenance manuals, SOPs, and historical repair knowledge.
    Returns grounded document references and content. Zero fabricated content.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return {"status": "INVALID_INPUT", "message": "Query string cannot be empty."}
        
    results = search_documents(cleaned_query, top_k=5)
    
    return {
        "status": "SUCCESS",
        "query": cleaned_query,
        "result_count": len(results),
        "documents": results
    }


@mcp.tool()
def get_work_order(work_order_id: str) -> Dict[str, Any]:
    """
    Returns complete details of a specific work order from PM_OEE_DB.CORE.WORK_ORDERS.
    """
    cleaned_id = work_order_id.strip().upper()
    wo_num = cleaned_id.replace("WO-", "")
    
    session = _get_session()
    wo_tbl = table("WORK_ORDERS")
    rows = session.sql(f"""
        SELECT WORK_ORDER_ID, MACHINE_ID, DIAGNOSIS, RECOMMENDED_ACTION, PARTS_REQUIRED,
               PRIORITY, STATUS, RISK_SCORE, RUL_HOURS, CREATED_AT, APPROVED_AT, EXTERNAL_TICKET_ID
        FROM {wo_tbl}
        WHERE LOWER(WORK_ORDER_ID) = LOWER(?) OR LOWER(WORK_ORDER_ID) = LOWER(?)
    """, params=[wo_num, cleaned_id]).collect()
    
    if not rows:
        return {"status": "NOT_FOUND", "work_order_id": cleaned_id, "message": f"Work order {cleaned_id} not found."}
        
    r = rows[0]
    return {
        "status": "SUCCESS",
        "work_order_id": f"WO-{r['WORK_ORDER_ID']}",
        "machine_id": r["MACHINE_ID"],
        "diagnosis": r.get("DIAGNOSIS"),
        "recommended_action": r.get("RECOMMENDED_ACTION"),
        "parts_required": r.get("PARTS_REQUIRED"),
        "priority": r.get("PRIORITY"),
        "work_order_status": r.get("STATUS"),
        "risk_score": r.get("RISK_SCORE"),
        "rul_hours": r.get("RUL_HOURS"),
        "created_at": str(r.get("CREATED_AT")),
        "approved_at": str(r.get("APPROVED_AT")) if r.get("APPROVED_AT") else None,
        "external_ticket_id": r.get("EXTERNAL_TICKET_ID")
    }


@mcp.tool()
def create_work_order(
    machine_id: str,
    diagnosis: str,
    recommended_action: str,
    parts_required: str,
    priority: str = "P1",
    risk_score: float = 0.85,
    rul_hours: float = 12.0,
    evidence: str = "Cortex Search: Maintenance Knowledge Base"
) -> Dict[str, Any]:
    """
    GOVERNED ACTION: Validates inputs via AI Guardrails and creates a Work Order.
    MANDATORY RULE: Always creates record with STATUS = 'PENDING_APPROVAL'.
    MUST NEVER set STATUS = 'APPROVED' or set APPROVED_AT. Human approval remains mandatory.
    """
    session = _get_session()
    cleaned_machine = machine_id.strip()
    
    # 1. Run AI Guardrails Validation
    guardrail_result = validate_work_order_creation({
        "machine_id": cleaned_machine,
        "diagnosis": diagnosis,
        "recommended_action": recommended_action,
        "parts_required": parts_required,
        "priority": priority,
        "risk_score": risk_score,
        "rul_hours": rul_hours,
        "evidence": evidence
    })
    
    if not guardrail_result.get("is_valid", True):
        return {
            "status": "GUARDRAIL_BLOCKED",
            "guardrail_status": "FAIL",
            "reason": guardrail_result.get("reason", "AI Guardrails validation failed."),
            "work_order_id": None
        }

    wo_tbl = table("WORK_ORDERS")
    safe_diag = str(diagnosis)[:1000]
    safe_action = str(recommended_action)[:1000]
    safe_parts = str(parts_required)[:500]
    safe_evidence = str(evidence)[:1000]

    # Parameterized Insert (Strictly PENDING_APPROVAL)
    session.sql(f"""
        INSERT INTO {wo_tbl}
            (machine_id, priority, status, diagnosis, recommended_action,
             parts_required, estimated_downtime_hours, risk_score, rul_hours,
             source_documents, created_at)
        VALUES
            (?, ?, 'PENDING_APPROVAL',
             ?, ?, ?, 4.0,
             ?, ?, ?, CURRENT_TIMESTAMP())
    """, params=[
        cleaned_machine,
        priority.upper(),
        safe_diag,
        safe_action,
        safe_parts,
        float(risk_score),
        float(rul_hours),
        safe_evidence
    ]).collect()

    # Get newly created WO ID
    wo_rows = session.sql(f"""
        SELECT MAX(work_order_id) AS NEW_WO_ID
        FROM {wo_tbl}
        WHERE machine_id = ?
    """, params=[cleaned_machine]).collect()
    
    new_wo_id = f"WO-{wo_rows[0]['NEW_WO_ID']}"
    
    logger.info(f"MCP create_work_order: Created {new_wo_id} with STATUS=PENDING_APPROVAL")
    
    return {
        "status": "PENDING_APPROVAL",
        "work_order_id": new_wo_id,
        "machine_id": cleaned_machine,
        "priority": priority.upper(),
        "guardrail_status": "PASS",
        "human_approval_required": True,
        "message": f"Governed work order {new_wo_id} created as PENDING_APPROVAL. Human approval required."
    }


@mcp.tool()
def request_jira_ticket(work_order_id: str) -> Dict[str, Any]:
    """
    GOVERNED TICKETING ACTION: Requests Jira ticket creation for an approved work order.
    GOVERNANCE RULES:
    - BLOCKS if WORK_ORDERS.STATUS != 'APPROVED'.
    - Checks idempotency: if ticket already exists (SUCCESS), returns existing Jira Key without duplicate creation.
    - Enqueues PENDING request into JIRA_INTEGRATION_QUEUE.
    - ZERO direct HTTP calls to Jira REST API inside MCP server. Outbound execution performed by Local Jira Worker.
    """
    session = _get_session()
    cleaned_wo_id = work_order_id.strip().upper()
    wo_num = cleaned_wo_id.replace("WO-", "")
    formatted_wo_id = f"WO-{wo_num}"

    wo_tbl = table("WORK_ORDERS")
    # 1. Read WORK_ORDERS to verify approval (parameterized)
    wo_rows = session.sql(f"""
        SELECT WORK_ORDER_ID, MACHINE_ID, STATUS, DIAGNOSIS, RECOMMENDED_ACTION, PRIORITY
        FROM {wo_tbl}
        WHERE LOWER(WORK_ORDER_ID) = LOWER(?) OR LOWER(WORK_ORDER_ID) = LOWER(?)
    """, params=[wo_num, formatted_wo_id]).collect()

    if not wo_rows:
        return {
            "status": "NOT_FOUND",
            "work_order_id": formatted_wo_id,
            "message": f"Work Order {formatted_wo_id} not found."
        }

    wo = wo_rows[0]
    wo_status = str(wo["STATUS"]).upper()

    # Approval Guard
    if wo_status != "APPROVED":
        logger.warning(f"MCP request_jira_ticket blocked: {formatted_wo_id} is {wo_status} (not APPROVED)")
        return {
            "status": "BLOCKED",
            "reason": "WORK_ORDER_NOT_APPROVED",
            "work_order_id": formatted_wo_id,
            "current_work_order_status": wo_status,
            "message": f"Work Order {formatted_wo_id} is not APPROVED. Jira creation blocked."
        }

    # 2. Idempotency Check (Existing SUCCESS, PROCESSING, PENDING)
    existing_success = check_existing_success(session, formatted_wo_id)
    if existing_success:
        return {
            "status": "SUCCESS",
            "jira_issue_key": existing_success["jira_issue_key"],
            "jira_url": existing_success["jira_url"],
            "idempotency": "PASS",
            "message": f"Jira issue already exists: {existing_success['jira_issue_key']}"
        }

    queue_status = get_queue_status(session, formatted_wo_id)
    if queue_status:
        q_stat = queue_status["status"]
        if q_stat == "PROCESSING":
            return {"status": "PROCESSING", "work_order_id": formatted_wo_id, "message": "Jira request is currently processing."}
        elif q_stat == "PENDING":
            return {"status": "PENDING", "work_order_id": formatted_wo_id, "message": "Jira request is already queued."}

    # 3. Enqueue Jira Request into JIRA_INTEGRATION_QUEUE
    enqueue_res = enqueue_jira_request(
        session=session,
        work_order_id=formatted_wo_id,
        machine_id=wo["MACHINE_ID"],
        short_description=f"Maintenance Work Order {formatted_wo_id} ({wo['MACHINE_ID']})",
        description=f"Diagnosis: {wo['DIAGNOSIS']}\nRecommended Action: {wo['RECOMMENDED_ACTION']}",
        impact="HIGH",
        urgency="HIGH",
        jira_project_key="KAN"
    )

    return {
        "status": "PENDING",
        "work_order_id": formatted_wo_id,
        "machine_id": wo["MACHINE_ID"],
        "jira_queue_status": "QUEUED",
        "message": f"Jira creation request enqueued for {formatted_wo_id}. Local Jira Worker will process shortly."
    }


# =============================================================================
# TOOL 8: search_web_oem — LAYER 2 External OEM/Manufacturer Knowledge
# =============================================================================

@mcp.tool()
def search_web_oem(query: str, manufacturer: str = None, model: str = None) -> Dict[str, Any]:
    """
    LAYER 2 — Search external OEM/manufacturer technical knowledge.
    Called automatically when internal maintenance manuals have no relevant match.
    """
    session = _get_session()

    try:
        from config import DATABASE, SCHEMA
        rows = session.sql(f"""
            CALL {DATABASE}.{SCHEMA}.SEARCH_WEB_OEM(?, ?, ?)
        """, params=[str(query), manufacturer, model]).collect()

        if not rows:
            return {
                "status": "NO_MATCH",
                "source_type": "EXTERNAL_OEM_KNOWLEDGE",
                "results": [],
                "disclaimer": "No OEM knowledge available for this query."
            }

        import json as json_mod
        result = json_mod.loads(rows[0][0])
        return result

    except Exception as e:
        logger.error(f"search_web_oem failed: {e}")
        return {
            "status": "ERROR",
            "source_type": "EXTERNAL_OEM_KNOWLEDGE",
            "results": [],
            "error": str(e)
        }


if __name__ == "__main__":
    print("Starting Governed FastMCP Server for MFG Predictive Maintenance V3...")
    print("Tools: 8 (get_machine_context, get_machine_risk, get_oee_metrics,")
    print("        search_maintenance_docs, get_work_order, create_work_order,")
    print("        request_jira_ticket, search_web_oem)")
    mcp.run()
