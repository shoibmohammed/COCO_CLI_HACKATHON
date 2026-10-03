"""
services/report_service.py
Generates exportable Executive Incident Reports (CSV & Text format).
"""

import io
from typing import Dict, Any

def generate_incident_report_csv(
    machine_id: str,
    context: Dict[str, Any],
    diagnosis: Dict[str, Any],
    work_order: Dict[str, Any]
) -> str:
    """Generates a CSV report summarizing the predictive maintenance incident."""
    output = io.StringIO()
    output.write("FIELD,VALUE\n")
    output.write(f"Machine ID,{machine_id}\n")
    output.write(f"Incident Status,CRITICAL ANOMALY DETECTED\n")
    output.write(f"Vibration (mm/s),{context.get('vibration_mm_s', 6.15)}\n")
    output.write(f"Temperature (C),{context.get('temperature_c', 97.3)}\n")
    output.write(f"Spindle RPM,{context.get('rpm', 1552)}\n")
    output.write(f"Unified Risk Score,{context.get('risk_score', 1.0)}\n")
    output.write(f"Estimated RUL (Hours),18.0\n")
    output.write(f"Root Cause,{diagnosis.get('root_cause', 'Spindle bearing wear')}\n")
    output.write(f"Confidence Score,{diagnosis.get('confidence', 0.92)*100:.0f}%\n")
    output.write(f"Recommended Part,{diagnosis.get('recommended_part', 'SKF-6205-2RS')}\n")
    output.write(f"Inventory Available,{diagnosis.get('inventory_units', 4)}\n")
    output.write(f"Estimated Loss (USD),$12,500\n")
    output.write(f"Work Order Status,{work_order.get('status', 'PENDING_APPROVAL')}\n")
    output.write(f"Recommended Action,{diagnosis.get('recommended_action', 'Replace spindle bearing')}\n")
    return output.getvalue()
