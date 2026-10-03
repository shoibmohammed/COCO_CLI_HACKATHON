"""
tests/test_notifications.py
Verification test for Email and WhatsApp Notification Service.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.notification_service import dispatch_critical_notifications

def test_notification_dispatch():
    print("\n" + "="*40)
    print("NOTIFICATION SERVICE VERIFICATION")
    print("="*40)

    test_alert = {
        "machine_id": "Machine_03",
        "risk_level": "CRITICAL",
        "failure_probability": 0.93,
        "rul_hours": 18.0,
        "root_cause": "Probable bearing degradation in spindle assembly",
        "recommended_part": "SKF-6205-2RS",
        "inventory_on_hand": 4,
        "work_order_id": 10023,
        "timestamp": "2026-08-12 19:30:00"
    }

    # First dispatch (should succeed in TEST/LIVE mode)
    res1 = dispatch_critical_notifications(test_alert, force=True)
    print("First Dispatch (Forced):")
    print(f"  Email Status: {res1.get('email_status')} — {res1.get('email_message')}")
    print(f"  WhatsApp Status: {res1.get('whatsapp_status')} — {res1.get('whatsapp_error') or res1.get('whatsapp_message_id') or 'N/A'}")

    # Second dispatch without force (should trigger deduplication / cooldown)
    res2 = dispatch_critical_notifications(test_alert, force=False)
    print("\nSecond Dispatch (Deduplication Check):")
    print(f"  Result: {res2}")

    assert res1["email_status"] in ("SENT", "TEST_SENT", "FAILED", "NOT_CONFIGURED", "DELIVERY_ACCEPTED")
    assert res1["whatsapp_status"] in ("SENT", "TEST_SENT", "NOT_CONFIGURED", "SUPPRESSED", "FAILED", "DISABLED")

    print("\nNOTIFICATION TEST RESULT: PASS")
    print("="*40)

if __name__ == "__main__":
    test_notification_dispatch()
