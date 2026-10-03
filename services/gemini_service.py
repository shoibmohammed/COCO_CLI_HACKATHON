# Backward-compatibility shim — renamed to cortex_service.py
from services.cortex_service import *  # noqa: F401,F403
from services.cortex_service import (
    get_api_key, build_marketplace_context, generate_diagnosis,
    classify_intent, retrieve_matching_docs, ask_machine_question,
    _extract_json, _question_responsive_fallback, _fallback_diagnosis,
    CORTEX_MODEL,
)
