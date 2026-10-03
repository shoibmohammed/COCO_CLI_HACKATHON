"""
services/knowledge_service.py
Three-Layer Dynamic Maintenance Knowledge Flow.

LAYER 1: Internal SOP / Cortex Search (MAINTENANCE_DOCS_SEARCH)
LAYER 2: External OEM Knowledge Fallback (model-based, not live web retrieval)
LAYER 3: Cortex Synthesis + AI Guardrails

The technician asks ONE question. The system automatically determines
the evidence path. No manual confirmation required.
"""

import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Match quality threshold: if the best Cortex Search result has
# relevance below this, we consider the internal match "weak".
# Cortex Search returns results ranked by relevance; we use the
# presence of keyword overlap + result count as quality signals.
INTERNAL_MATCH_MIN_RESULTS = 1
INTERNAL_MATCH_MIN_SCORE = 0.3  # normalized score from search results

CORTEX_MODEL = "llama3.1-70b"


# =============================================================================
# LAYER 1 — INTERNAL KNOWLEDGE SEARCH
# =============================================================================

def search_internal_knowledge(session, query: str) -> Dict[str, Any]:
    """
    Search PM_OEE_DB.CORE.MAINTENANCE_DOCS_SEARCH via Cortex Search.
    Returns match quality assessment and evidence.
    """
    if not session or not query or not query.strip():
        return {"match_quality": "NO_MATCH", "results": [], "source": "INTERNAL"}

    try:
        from config import DATABASE, SCHEMA
        search_svc = f"{DATABASE}.{SCHEMA}.MAINTENANCE_DOCS_SEARCH"
        clean_q = query.replace('"', "").replace("'", "")
        search_payload = json.dumps({"query": clean_q, "columns": ["source_file", "page_number", "chunk_text", "chunk_key"], "limit": 5})
        search_result = session.sql(f"""
            SELECT PARSE_JSON(
                SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                    '{search_svc}',
                    '{search_payload}'
                )
            )['results'] AS results
        """).collect()

        if not search_result or not search_result[0]["RESULTS"]:
            return {"match_quality": "NO_MATCH", "results": [], "source": "INTERNAL"}

        raw_results = json.loads(search_result[0]["RESULTS"])

        if not raw_results:
            return {"match_quality": "NO_MATCH", "results": [], "source": "INTERNAL"}

        # Assess match quality based on content relevance
        results = []
        for r in raw_results:
            results.append({
                "source_file": r.get("source_file", ""),
                "page_number": r.get("page_number"),
                "chunk_text": r.get("chunk_text", ""),
                "chunk_key": r.get("chunk_key", "")
            })

        # Determine match quality using keyword overlap heuristic
        query_terms = set(query.lower().split())
        best_overlap = 0
        for r in results:
            chunk_lower = r["chunk_text"].lower()
            overlap = sum(1 for t in query_terms if t in chunk_lower)
            best_overlap = max(best_overlap, overlap)

        total_query_terms = len(query_terms)
        overlap_ratio = best_overlap / max(total_query_terms, 1)

        if overlap_ratio >= INTERNAL_MATCH_MIN_SCORE and len(results) >= INTERNAL_MATCH_MIN_RESULTS:
            match_quality = "STRONG"
        elif results:
            match_quality = "WEAK"
        else:
            match_quality = "NO_MATCH"

        return {
            "match_quality": match_quality,
            "results": results,
            "result_count": len(results),
            "overlap_ratio": round(overlap_ratio, 3),
            "source": "INTERNAL"
        }

    except Exception as e:
        logger.warning(f"Internal search failed: {e}")
        return {"match_quality": "NO_MATCH", "results": [], "source": "INTERNAL", "error": str(e)}


# =============================================================================
# LAYER 2 — EXTERNAL OEM KNOWLEDGE FALLBACK (MODEL-BASED, NOT LIVE WEB)
# =============================================================================

def search_web_oem(session, query: str, manufacturer: str = None, model: str = None) -> Dict[str, Any]:
    """
    Search for external OEM/manufacturer technical guidance.

    ARCHITECTURE NOTE:
    - EAI (External Access Integration) is BLOCKED on trial accounts.
    - This implementation uses SNOWFLAKE.CORTEX.COMPLETE to provide
      manufacturer/OEM technical knowledge from the model's training data.
    - Results are clearly labeled as "AI-generated OEM guidance" not
      "verified web results".
    - When EAI is enabled, this function can be upgraded to actual web search.

    NEVER fabricates: URLs, specific document titles, or claims to have
    searched a live website.
    """
    if not session or not query or not query.strip():
        return {
            "status": "NO_MATCH",
            "source_type": "EXTERNAL_OEM_KNOWLEDGE",
            "results": [],
            "disclaimer": "No query provided."
        }

    # Build a focused OEM-knowledge prompt
    mfg_context = ""
    if manufacturer:
        mfg_context += f"Manufacturer: {manufacturer}. "
    if model:
        mfg_context += f"Model/Equipment: {model}. "

    oem_prompt = f"""You are a manufacturing maintenance technical reference assistant.
The user needs OEM/manufacturer technical guidance for maintenance.

{mfg_context}
Question: {query}

RULES:
- Provide ONLY factual OEM/manufacturer technical guidance that is widely documented.
- Reference specific error codes, procedures, or maintenance standards ONLY if they are
  well-established in public OEM documentation.
- Do NOT fabricate URLs, document titles, or specific page references.
- Do NOT invent procedures that may not exist.
- If you do not have reliable OEM knowledge for this specific query, respond with
  exactly: NO_RELIABLE_OEM_KNOWLEDGE
- Keep the response concise and technical.
- Focus on: official procedures, common root causes, recommended parts, safety warnings.

Respond in JSON format:
{{"has_knowledge": true/false, "guidance": "technical guidance text", "source_basis": "description of what OEM/public knowledge this is based on", "safety_warnings": ["any relevant safety notes"]}}"""

    try:
        result = session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS response",
            params=[CORTEX_MODEL, oem_prompt]
        ).collect()

        if not result:
            return {
                "status": "NO_MATCH",
                "source_type": "EXTERNAL_OEM_KNOWLEDGE",
                "results": []
            }

        response_text = result[0]["RESPONSE"]

        # Try to parse as JSON
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            # Check for explicit no-knowledge signal
            if "NO_RELIABLE_OEM_KNOWLEDGE" in response_text:
                return {
                    "status": "NO_MATCH",
                    "source_type": "EXTERNAL_OEM_KNOWLEDGE",
                    "results": []
                }
            # Treat as unstructured guidance
            parsed = {
                "has_knowledge": True,
                "guidance": response_text.strip(),
                "source_basis": "General OEM/manufacturer technical knowledge",
                "safety_warnings": []
            }

        if not parsed.get("has_knowledge", False):
            return {
                "status": "NO_MATCH",
                "source_type": "EXTERNAL_OEM_KNOWLEDGE",
                "results": []
            }

        return {
            "status": "SUCCESS",
            "source_type": "EXTERNAL_OEM_KNOWLEDGE",
            "results": [{
                "guidance": parsed.get("guidance", ""),
                "source_basis": parsed.get("source_basis", "OEM technical knowledge"),
                "safety_warnings": parsed.get("safety_warnings", [])
            }],
            "disclaimer": (
                "This recommendation is based on publicly available OEM/manufacturer "
                "technical knowledge and is not an internal maintenance SOP. Verify "
                "against site procedures before execution."
            )
        }

    except Exception as e:
        logger.warning(f"OEM knowledge search failed: {e}")
        return {
            "status": "ERROR",
            "source_type": "EXTERNAL_OEM_KNOWLEDGE",
            "results": [],
            "error": str(e)
        }


# =============================================================================
# LAYER 3 — CORTEX SYNTHESIS
# =============================================================================

def cortex_synthesis(
    session,
    question: str,
    internal_evidence: Dict[str, Any],
    external_evidence: Dict[str, Any],
    machine_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Synthesize final answer from all evidence layers using Cortex AI.
    Clearly attributes evidence sources.
    """
    if not session:
        return {"status": "ERROR", "answer": "No Snowflake session available."}

    # Build evidence context
    internal_text = ""
    if internal_evidence.get("match_quality") in ("STRONG", "WEAK"):
        chunks = internal_evidence.get("results", [])
        for c in chunks[:3]:
            internal_text += f"\n[Source: {c.get('source_file', 'Internal Manual')}]\n{c.get('chunk_text', '')}\n"

    external_text = ""
    if external_evidence.get("status") == "SUCCESS":
        for r in external_evidence.get("results", []):
            external_text += f"\n[Source basis: {r.get('source_basis', 'OEM knowledge')}]\n{r.get('guidance', '')}\n"
            warnings = r.get("safety_warnings", [])
            if warnings:
                external_text += f"Safety: {'; '.join(warnings)}\n"

    # Build machine context string
    mc = machine_context or {}
    machine_text = ""
    if mc:
        machine_text = f"""Machine: {mc.get('machine_id', 'Unknown')}
Vibration: {mc.get('vibration_mm_s', 'N/A')} mm/s
Temperature: {mc.get('temperature_c', 'N/A')} °C
RPM: {mc.get('rpm', 'N/A')}
Risk Score: {mc.get('risk_score', 'N/A')}
ML Failure Probability: {mc.get('ml_failure_probability', 'N/A')}
RUL: {mc.get('rul_hours', 'N/A')} hours
Part: {mc.get('bearing_part_number', 'N/A')}
Stock: {mc.get('inventory_units', 'N/A')} units"""

    synthesis_prompt = f"""You are a manufacturing predictive maintenance copilot.
Synthesize a clear, actionable answer to the technician's question using ONLY the provided evidence.

QUESTION: {question}

MACHINE CONTEXT (verified Snowflake data):
{machine_text if machine_text else "No specific machine context provided."}

INTERNAL EVIDENCE (from approved SOPs/manuals):
{internal_text if internal_text else "No relevant internal documentation found."}

EXTERNAL OEM EVIDENCE:
{external_text if external_text else "No external OEM evidence available."}

RULES:
- Ground every claim in the provided evidence.
- Clearly identify which evidence source supports each statement.
- Do NOT invent telemetry values, ML predictions, parts, or procedures.
- Do NOT fabricate URLs or document titles.
- If evidence is insufficient, say so clearly.
- Keep the response concise, technical, and actionable.
- If recommending maintenance action, reference the specific procedure source.
"""

    try:
        result = session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS response",
            params=[CORTEX_MODEL, synthesis_prompt]
        ).collect()

        answer = result[0]["RESPONSE"] if result else "Synthesis failed."

        return {
            "status": "SUCCESS",
            "answer": answer,
            "sources_used": {
                "internal": internal_evidence.get("match_quality", "NO_MATCH") != "NO_MATCH",
                "external": external_evidence.get("status") == "SUCCESS",
                "machine_context": bool(machine_text)
            }
        }

    except Exception as e:
        logger.warning(f"Cortex synthesis failed: {e}")
        return {"status": "ERROR", "answer": f"Cortex synthesis error: {e}"}


# =============================================================================
# THREE-LAYER ORCHESTRATOR
# =============================================================================

def three_layer_knowledge_query(
    session,
    question: str,
    machine_context: Optional[Dict[str, Any]] = None,
    manufacturer: str = None,
    model: str = None
) -> Dict[str, Any]:
    """
    Main entry point for the three-layer dynamic maintenance knowledge flow.

    ONE question in → automatic evidence path → ONE answer out.
    No user confirmation required.

    Returns:
        {
            "evidence_type": "INTERNAL" | "EXTERNAL" | "COMBINED" | "INSUFFICIENT",
            "label": "🟢 INTERNAL SOP-GROUNDED" | "🟡 EXTERNAL OEM/WEB GUIDANCE" | ...,
            "answer": str,
            "internal_evidence": {...},
            "external_evidence": {...},
            "disclaimer": str or None,
            "sources": [list of source names]
        }
    """
    if not session or not question or not question.strip():
        return {
            "evidence_type": "INSUFFICIENT",
            "label": "⚠️ INSUFFICIENT EVIDENCE",
            "answer": "No question provided.",
            "internal_evidence": {},
            "external_evidence": {},
            "disclaimer": None,
            "sources": []
        }

    # === LAYER 1: Internal Knowledge Search ===
    internal_result = search_internal_knowledge(session, question)
    internal_quality = internal_result.get("match_quality", "NO_MATCH")

    # === DECISION: Should we search external sources? ===
    external_result = {"status": "NOT_SEARCHED", "results": []}

    if internal_quality == "STRONG":
        # Strong internal match — do NOT search externally
        pass
    else:
        # No match or weak match — automatically search external OEM knowledge
        external_result = search_web_oem(
            session, question,
            manufacturer=manufacturer or (machine_context or {}).get("supplier"),
            model=model or (machine_context or {}).get("machine_type")
        )

    # === Determine evidence type ===
    has_internal = internal_quality in ("STRONG", "WEAK")
    has_external = external_result.get("status") == "SUCCESS"

    if has_internal and not has_external:
        evidence_type = "INTERNAL"
        label = "🟢 INTERNAL SOP-GROUNDED"
        disclaimer = None
    elif has_internal and has_external:
        evidence_type = "COMBINED"
        label = "🟢 INTERNAL + 🟡 EXTERNAL EVIDENCE"
        disclaimer = external_result.get("disclaimer")
    elif not has_internal and has_external:
        evidence_type = "EXTERNAL"
        label = "🟡 EXTERNAL OEM/WEB GUIDANCE"
        disclaimer = external_result.get("disclaimer")
    else:
        evidence_type = "INSUFFICIENT"
        label = "⚠️ INSUFFICIENT EVIDENCE"
        disclaimer = None

    # === LAYER 3: Cortex Synthesis ===
    if evidence_type == "INSUFFICIENT":
        answer = (
            "No relevant internal procedure or reliable external technical source "
            "was found for this query. Unable to provide a grounded recommendation."
        )
        sources = []
    else:
        synthesis = cortex_synthesis(
            session, question, internal_result, external_result, machine_context
        )
        answer = synthesis.get("answer", "Synthesis unavailable.")
        sources = []
        if has_internal:
            for r in internal_result.get("results", [])[:3]:
                src = r.get("source_file", "Internal Manual")
                if src not in sources:
                    sources.append(src)
        if has_external:
            for r in external_result.get("results", []):
                src_basis = r.get("source_basis", "OEM Knowledge")
                if src_basis not in sources:
                    sources.append(src_basis)

    return {
        "evidence_type": evidence_type,
        "label": label,
        "answer": answer,
        "internal_evidence": internal_result,
        "external_evidence": external_result,
        "disclaimer": disclaimer,
        "sources": sources
    }


# =============================================================================
# NATIVE AGENT ORCHESTRATOR (uses PM_AGENT with real web search)
# =============================================================================

def three_layer_agent_query(
    session,
    question: str,
    machine_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute the 3-layer knowledge flow via the native PM_AGENT.
    This path uses the Cortex Agent's built-in web_search tool (Brave)
    for Layer 2, providing real URLs and live web results.

    The agent handles the internal-first policy, automatic fallback,
    and evidence labeling autonomously.

    Returns the same interface as three_layer_knowledge_query for
    drop-in compatibility with the Streamlit UI.
    """
    if not session or not question or not question.strip():
        return {
            "evidence_type": "INSUFFICIENT",
            "label": "⚠️ INSUFFICIENT EVIDENCE",
            "answer": "No question provided.",
            "internal_evidence": {},
            "external_evidence": {},
            "disclaimer": None,
            "sources": []
        }

    try:
        # Build the request — include machine context if available
        prompt = question
        if machine_context and machine_context.get("machine_id"):
            mc = machine_context
            ctx_parts = [f"Machine: {mc.get('machine_id')}"]
            if mc.get("vibration_mm_s"):
                ctx_parts.append(f"Vibration: {mc['vibration_mm_s']} mm/s")
            if mc.get("temperature_c"):
                ctx_parts.append(f"Temperature: {mc['temperature_c']} °C")
            if mc.get("rpm"):
                ctx_parts.append(f"RPM: {mc['rpm']}")
            if mc.get("risk_score"):
                ctx_parts.append(f"Risk: {mc['risk_score']}")
            if mc.get("rul_hours"):
                ctx_parts.append(f"RUL: {mc['rul_hours']} hours")
            if mc.get("bearing_part_number"):
                ctx_parts.append(f"Part: {mc['bearing_part_number']}")
            prompt = question + "\n\n[Machine Context: " + ", ".join(ctx_parts) + "]"

        request_body = json.dumps({
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        })
        # Escape for Snowflake SQL literal: double backslashes first (so JSON
        # escape sequences like \n survive as literal \n), then single quotes.
        sql_safe_body = request_body.replace("\\", "\\\\").replace("'", "''")

        from config import DATABASE, SCHEMA
        agent_name = f"{DATABASE}.{SCHEMA}.PM_AGENT"
        result = session.sql(f"""
            SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
                '{agent_name}',
                '{sql_safe_body}'
            ) AS response
        """).collect()

        if not result:
            return {
                "evidence_type": "INSUFFICIENT",
                "label": "⚠️ INSUFFICIENT EVIDENCE",
                "answer": "Agent did not return a response.",
                "internal_evidence": {},
                "external_evidence": {},
                "disclaimer": None,
                "sources": []
            }

        response = json.loads(result[0]["RESPONSE"])

        # Extract the text answer
        answer_text = ""
        sources = []
        for content_block in response.get("content", []):
            if content_block.get("type") == "text":
                answer_text = content_block.get("text", "")
            elif content_block.get("type") == "tool_results":
                # Could extract tool call details here for attribution
                pass

        # Determine evidence type from the response labels
        answer_lower = answer_text.lower()
        if "internal sop-grounded" in answer_lower or "🟢" in answer_text:
            if "external" in answer_lower or "🟡" in answer_text:
                evidence_type = "COMBINED"
                label = "🟢 INTERNAL + 🟡 EXTERNAL EVIDENCE"
                disclaimer = (
                    "This recommendation includes publicly available OEM/web sources "
                    "in addition to internal SOPs. Verify external guidance against "
                    "site procedures before execution."
                )
            else:
                evidence_type = "INTERNAL"
                label = "🟢 INTERNAL SOP-GROUNDED"
                disclaimer = None
        elif "external oem/web" in answer_lower or "🟡" in answer_text:
            evidence_type = "EXTERNAL"
            label = "🟡 EXTERNAL OEM/WEB GUIDANCE"
            disclaimer = (
                "This recommendation is based on publicly available OEM/web sources "
                "and is not an internal maintenance SOP. Verify against site procedures "
                "before execution."
            )
        elif "insufficient" in answer_lower or "⚠️" in answer_text:
            evidence_type = "INSUFFICIENT"
            label = "⚠️ INSUFFICIENT EVIDENCE"
            disclaimer = None
        else:
            # Default: assume synthesis from verified context
            evidence_type = "INTERNAL"
            label = "🔵 AI SYNTHESIS FROM VERIFIED EVIDENCE"
            disclaimer = None

        # Extract source URLs if present in the answer
        import re
        url_pattern = re.compile(r'https?://[^\s\)\]\"\'<>]+')
        found_urls = url_pattern.findall(answer_text)
        sources = found_urls[:5] if found_urls else []

        # Also check for cortex_search citations in content
        for content_block in response.get("content", []):
            if content_block.get("type") == "cortex_search_citation":
                src = content_block.get("title", content_block.get("source_file", ""))
                if src and src not in sources:
                    sources.append(src)

        return {
            "evidence_type": evidence_type,
            "label": label,
            "answer": answer_text,
            "internal_evidence": {"source": "PM_AGENT/MaintenanceSearch"},
            "external_evidence": {"source": "PM_AGENT/WebSearch", "urls": found_urls},
            "disclaimer": disclaimer,
            "sources": sources
        }

    except Exception as e:
        logger.warning(f"Agent query failed: {e}")
        return {
            "evidence_type": "INSUFFICIENT",
            "label": "⚠️ INSUFFICIENT EVIDENCE",
            "answer": f"Agent query error: {e}",
            "internal_evidence": {},
            "external_evidence": {},
            "disclaimer": None,
            "sources": []
        }
