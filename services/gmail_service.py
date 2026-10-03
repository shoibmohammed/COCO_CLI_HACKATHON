"""
services/gmail_service.py
Official Gmail API + OAuth 2.0 Desktop Client Authorization Service for MFG Predictive Maintenance.
Uses Google Desktop Client Credentials (credentials.json), persists authorized tokens (token.json),
and executes emails via users.messages.send API with scope 'https://www.googleapis.com/auth/gmail.send'.
Includes robust Windows browser launching with PowerShell Start-Process, os.startfile, and webbrowser.
Includes account validation for siddharthawork7@gmail.com, 5-minute timeout handling,
and Snowflake NOTIFICATION_AUDIT integration.
NEVER logs, prints, or exposes client secrets or tokens.
"""

import os
import sys
import json
import base64
import logging
import subprocess
import webbrowser
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Allow local HTTP redirect testing for loopback server
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "token.json"))
CREDENTIALS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "credentials.json"))
DEFAULT_SENDER = "siddharthawork7@gmail.com"


def open_oauth_browser(auth_url: str) -> bool:
    """
    Robust Windows browser launcher.
    Tries:
    1. PowerShell Start-Process (launches in interactive user session)
    2. os.startfile (native Windows ShellExecute)
    3. webbrowser.open(auth_url, new=2)
    4. explorer.exe
    5. cmd start
    """
    logger.info(f"Opening browser for authorization: {auth_url[:60]}...")
    launched = False

    # 1. PowerShell Start-Process
    try:
        ps_cmd = f"Start-Process '{auth_url}'"
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], shell=False)
        logger.info("Browser launch via PowerShell Start-Process: SUCCESS")
        launched = True
    except Exception as e:
        logger.debug(f"PowerShell launch failed: {e}")

    # 2. Native Windows ShellExecute
    try:
        os.startfile(auth_url)
        logger.info("Browser launch via os.startfile: SUCCESS")
        launched = True
    except Exception as e:
        logger.debug(f"os.startfile launch failed: {e}")

    # 3. Python standard webbrowser
    try:
        if webbrowser.open(auth_url, new=2):
            logger.info("Browser launch via webbrowser.open: SUCCESS")
            launched = True
    except Exception as e:
        logger.debug(f"webbrowser.open launch failed: {e}")

    # 4. explorer.exe launch
    try:
        subprocess.Popen(["explorer.exe", auth_url], shell=False)
        logger.info("Browser launch via explorer.exe: SUCCESS")
        launched = True
    except Exception as e:
        logger.debug(f"explorer.exe launch failed: {e}")

    return launched


def get_gmail_credentials() -> Tuple[Optional[Any], str, str]:
    """
    Loads Google OAuth 2.0 Credentials from token.json or Streamlit secrets.
    Refreshes expired access tokens using refresh_token when available.
    Returns (credentials_object, status_code, status_message).
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError as e:
        logger.error(f"Google OAuth libraries missing: {e}")
        return None, "LIBRARIES_MISSING", "Required google-auth and google-api-python-client libraries missing."

    creds = None

    # 1. Try loading token.json
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, GMAIL_SCOPES)
        except Exception as e:
            logger.warning(f"Error loading token.json: {e}")
            creds = None

    # 2. Fallback to Streamlit secrets or Environment Variables if token.json is not found
    if not creds:
        client_id = os.environ.get("GMAIL_CLIENT_ID", "")
        client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
        refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "")
        token_uri = os.environ.get("GMAIL_TOKEN_URI", "https://oauth2.googleapis.com/token")

        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                _s = dict(st.secrets)  # force load — raises if no secrets.toml
                if "GMAIL_CLIENT_ID" in _s:
                    client_id = str(st.secrets["GMAIL_CLIENT_ID"])
                if "GMAIL_CLIENT_SECRET" in _s:
                    client_secret = str(st.secrets["GMAIL_CLIENT_SECRET"])
                if "GMAIL_REFRESH_TOKEN" in _s:
                    refresh_token = str(st.secrets["GMAIL_REFRESH_TOKEN"])
                
                sec_name = "gmail_oauth" if "gmail_oauth" in _s else ("gmail" if "gmail" in _s else None)
                if sec_name:
                    sec = st.secrets[sec_name]
                    client_id = str(sec.get("client_id") or client_id)
                    client_secret = str(sec.get("client_secret") or client_secret)
                    refresh_token = str(sec.get("refresh_token") or refresh_token)
                    token_uri = str(sec.get("token_uri") or token_uri)
        except Exception as e:
            logger.debug(f"Streamlit secrets token check skipped: {e}")

        if client_id and client_secret and refresh_token:
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri=token_uri,
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=GMAIL_SCOPES
                )
            except Exception as e:
                logger.warning(f"Error building credentials from secrets: {e}")
                creds = None

    # 3. Validate & Refresh Token if Expired
    if creds:
        try:
            if creds.valid:
                return creds, "AUTHENTICATED", "Gmail OAuth 2.0 Credentials Authorized & Valid."
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                try:
                    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                except Exception as save_err:
                    logger.debug(f"Could not save refreshed token: {save_err}")
                return creds, "AUTHENTICATED", "Gmail OAuth Access Token Refreshed Successfully."
        except Exception as ref_err:
            logger.error(f"Token refresh failed: {ref_err}")
            return None, "TOKEN_EXPIRED", "Gmail OAuth token expired or revoked. Authorization required."

    # 4. If credentials.json exists, prompt for authorization
    if os.path.exists(CREDENTIALS_FILE):
        return None, "AUTHORIZATION_REQUIRED", "Google Desktop OAuth client configured. User authorization required."
    else:
        return None, "CREDENTIALS_MISSING", "Desktop OAuth client configuration file 'credentials.json' not found."


def is_gmail_configured() -> bool:
    """Returns True if valid or refreshable Gmail API OAuth credentials exist."""
    creds, code, _ = get_gmail_credentials()
    return bool(creds and creds.valid)


def get_gmail_status() -> Dict[str, Any]:
    """
    Evaluates Gmail API OAuth authorization status.
    Returns structured status dictionary.
    """
    creds, code, msg = get_gmail_credentials()
    has_creds_file = os.path.exists(CREDENTIALS_FILE)

    if code == "AUTHENTICATED" and creds:
        return {
            "status": "READY",
            "overall_label": "🟢 GMAIL API READY",
            "auth_status": "🟢 AUTHENTICATED",
            "account": DEFAULT_SENDER,
            "permission": "gmail.send",
            "scope": GMAIL_SCOPES[0],
            "credentials_file_found": has_creds_file,
            "token_file_found": os.path.exists(TOKEN_FILE),
            "message": "Gmail API Desktop OAuth client authorized and active."
        }
    elif code == "AUTHORIZATION_REQUIRED":
        return {
            "status": "AUTHORIZATION_REQUIRED",
            "overall_label": "🟡 GMAIL AUTHORIZATION REQUIRED",
            "auth_status": "🟡 AUTHORIZATION REQUIRED",
            "account": DEFAULT_SENDER,
            "permission": "gmail.send",
            "scope": GMAIL_SCOPES[0],
            "credentials_file_found": True,
            "token_file_found": False,
            "message": "Desktop OAuth client credentials.json found. Click 'Connect Gmail' to authorize."
        }
    else:
        return {
            "status": code,
            "overall_label": f"🔴 GMAIL API {code}",
            "auth_status": f"🔴 {code}",
            "account": DEFAULT_SENDER,
            "permission": "gmail.send",
            "scope": GMAIL_SCOPES[0],
            "credentials_file_found": has_creds_file,
            "token_file_found": os.path.exists(TOKEN_FILE),
            "message": msg
        }


def authenticate_gmail(
    port: int = 0,
    timeout_seconds: int = 300,
    send_test_on_success: bool = True
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Initiates Desktop OAuth 2.0 authorization flow using credentials.json.
    1. Starts exactly ONE local callback server on an available localhost/127.0.0.1 port.
    2. Generates the complete Google OAuth URL with exact matching state and redirect_uri.
    3. Actively launches the Windows default browser via open_oauth_browser(auth_url).
    4. Handles callback within timeout_seconds (5 minutes default).
    5. Saves token.json.
    6. Validates authenticated account is siddharthawork7@gmail.com.
    7. Optionally executes real test email dispatch via users.messages.send().
    Returns (success: bool, status_message: str, details: dict).
    """
    if not os.path.exists(CREDENTIALS_FILE):
        return False, "credentials.json file not found in project root directory.", {}

    details = {}

    try:
        import wsgiref.simple_server
        from google_auth_oauthlib.flow import InstalledAppFlow, _RedirectWSGIApp, _WSGIRequestHandler, WSGITimeoutError
        from googleapiclient.discovery import build

        # Step 1: Create InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, GMAIL_SCOPES)

        # Step 2: Start ONE local callback server
        success_msg = (
            "<html><body style='font-family:sans-serif; text-align:center; padding-top:40px; background:#0F172A; color:#F8FAFC;'>"
            "<h2 style='color:#22C55E;'>&#10004; GMAIL AUTHENTICATION SUCCESSFUL</h2>"
            "<p>You can close this tab and return to the <strong>MFG Predictive Maintenance Command Center</strong>.</p>"
            "</body></html>"
        )
        wsgi_app = _RedirectWSGIApp(success_msg)
        wsgiref.simple_server.WSGIServer.allow_reuse_address = False
        local_server = wsgiref.simple_server.make_server(
            "127.0.0.1", port, wsgi_app, handler_class=_WSGIRequestHandler
        )

        server_port = local_server.server_port
        flow.redirect_uri = f"http://127.0.0.1:{server_port}/"

        # Step 3: Generate complete authorization URL
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

        # Save URL to scratch/oauth_url.txt
        url_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "oauth_url.txt"))
        try:
            with open(url_file, "w", encoding="utf-8") as uf:
                uf.write(auth_url)
        except Exception:
            pass

        # Diagnostic logging before launch
        logger.info("=" * 30)
        logger.info("Gmail OAuth")
        logger.info("------------------------------")
        logger.info("OAuth Client: Desktop")
        logger.info(f"Account: {DEFAULT_SENDER}")
        logger.info(f"Scope: {GMAIL_SCOPES[0]}")
        logger.info(f"Redirect URI: {flow.redirect_uri}")
        logger.info("Browser Launch: STARTING")
        logger.info("=" * 30)

        # Step 5: AUTOMATICALLY OPEN WINDOWS DEFAULT BROWSER
        opened = open_oauth_browser(auth_url)
        if opened:
            logger.info("Browser Launch: SUCCESS")
        else:
            logger.warning("Browser Launch: MANUAL_URL_FALLBACK")

        # Step 9: Handle callback with timeout
        local_server.timeout = timeout_seconds
        try:
            local_server.handle_request()
            try:
                authorization_response = wsgi_app.last_request_uri.replace("http", "https")
            except AttributeError as e:
                raise WSGITimeoutError("Timed out waiting for response from authorization server.") from e

            flow.fetch_token(authorization_response=authorization_response)
            creds = flow.credentials
        finally:
            local_server.server_close()

        logger.info("OAuth Callback: RECEIVED")

        # Step 10: Save token.json
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        logger.info("Token: SAVED")

        # Step 11: Validate Authenticated Account Identity
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        authorized_email = profile.get("emailAddress", "").strip()

        logger.info(f"Authenticated Account: {authorized_email}")
        details["authenticated_account"] = authorized_email
        details["scope"] = GMAIL_SCOPES[0]
        details["redirect_uri"] = flow.redirect_uri

        if authorized_email.lower() != DEFAULT_SENDER.lower():
            logger.error(f"🔴 WRONG GOOGLE ACCOUNT: Expected {DEFAULT_SENDER}, Got {authorized_email}")
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
            return False, f"🔴 WRONG GOOGLE ACCOUNT: Expected {DEFAULT_SENDER}, Authenticated: {authorized_email}", details

        # Step 13: Send Real Test Email if requested
        if send_test_on_success:
            test_subject = "🧪 MFG Predictive Maintenance — Gmail API Test"
            test_body = (
                f"Gmail API end-to-end test successful.\n\n"
                f"MFG Predictive Maintenance & OEE Command Center\n\n"
                f"Machine: Machine_03\n"
                f"Status: CRITICAL\n"
                f"Failure Probability: 100%\n"
                f"Unified Risk: 100%\n"
                f"Predicted RUL: 18.0 hours\n"
                f"Estimated Downtime: 4.0 hours\n"
                f"Financial Risk: $12,500\n\n"
                f"This email was sent using the official Gmail API (users.messages.send).\n"
                f"Sender: {DEFAULT_SENDER}\n"
                f"Recipient: {DEFAULT_SENDER}\n"
                f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )

            send_res = send_email(
                to=DEFAULT_SENDER,
                subject=test_subject,
                body=test_body
            )

            details["test_send"] = send_res
            if send_res.get("success"):
                details["message_id"] = send_res.get("message_id")
                # Record Snowflake audit
                try:
                    from snowflake_connection import get_snowflake_connection
                    session = get_snowflake_connection()
                    if session:
                        from services.universal_email_service import record_universal_audit
                        record_universal_audit(
                            session=session,
                            event_id="EV_GMAIL_OAUTH_CONNECT",
                            machine_id="Machine_03",
                            work_order_id="WO-10023",
                            notification_type="GMAIL_OAUTH_CONNECT",
                            provider="GMAIL_API",
                            recipient=DEFAULT_SENDER,
                            subject=test_subject,
                            status="SENT",
                            message_id=send_res.get("message_id")
                        )
                        details["snowflake_audit"] = "RECORDED"
                except Exception as audit_err:
                    logger.debug(f"Snowflake audit record skipped: {audit_err}")

        return True, f"🟢 GMAIL API READY. Authorized account: {authorized_email}", details

    except WSGITimeoutError:
        logger.error("🔴 GOOGLE AUTHORIZATION TIMED OUT (5 minutes elapsed).")
        return False, "🔴 GOOGLE AUTHORIZATION TIMED OUT: No response received within 5 minutes. Click 'Try Again'.", details
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Gmail OAuth authorization failed: {err_msg}")
        if "access_denied" in err_msg or "403" in err_msg:
            return False, "🟠 GOOGLE TEST USER REQUIRED: Ensure siddharthawork7@gmail.com is added under Google Auth Platform → Audience → Test users in Google Cloud Console.", details
        return False, f"Gmail authorization failed: {err_msg[:150]}", details


def verify_gmail_connection() -> Dict[str, Any]:
    """
    Verifies Gmail API reachability and authorized sender without sending an email.
    """
    creds, code, msg = get_gmail_credentials()
    if not creds:
        return {
            "success": False,
            "status": code,
            "message": f"Gmail connection verification failed: {msg}"
        }

    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email_addr = profile.get("emailAddress", DEFAULT_SENDER)
        return {
            "success": True,
            "status": "VERIFIED",
            "email_address": email_addr,
            "message": f"🟢 Gmail API connection verified. Authorized account: {email_addr}"
        }
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Gmail API verification error: {err_msg}")
        return {
            "success": False,
            "status": "API_ERROR",
            "message": f"🔴 Gmail API verification error: {err_msg[:150]}"
        }


def create_mime_message(
    sender: str,
    recipient: str,
    subject: str,
    body_text: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> MIMEMultipart:
    """Constructs an RFC-compliant MIMEMultipart email message."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"MFG Predictive Maintenance <{sender}>"
    msg["To"] = recipient

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body_text, "plain", "utf-8"))
    if html_body:
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body_part)

    if attachments:
        for att in attachments:
            fname = att.get("filename", "attachment.bin")
            content = att.get("content", b"")
            part = MIMEBase("application", "octet-stream")
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
            msg.attach(part)

    return msg


def send_email(
    to: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Dispatches email via Google Gmail API users.messages.send.
    Encodes RFC MIME payload into base64url format.
    Returns structured response dict.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    target_to = (to or "").strip()
    sender = DEFAULT_SENDER

    creds, code, auth_msg = get_gmail_credentials()
    if not creds:
        return {
            "success": False,
            "status": code,
            "recipient": target_to,
            "sender": sender,
            "subject": subject,
            "message": f"Gmail authorization required: {auth_msg}",
            "error_category": code,
            "timestamp": timestamp
        }

    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)

        mime_msg = create_mime_message(sender, target_to, subject, body, html_body, attachments)
        raw_b64 = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")

        response = service.users().messages().send(
            userId="me",
            body={"raw": raw_b64}
        ).execute()

        msg_id = response.get("id")
        if not msg_id:
            return {
                "success": False,
                "status": "FAILED",
                "recipient": target_to,
                "sender": sender,
                "subject": subject,
                "message": "Gmail API response missing message ID.",
                "error_category": "UNKNOWN_ERROR",
                "timestamp": timestamp
            }

        logger.info(f"Gmail API email sent successfully to {target_to}. Message ID: {msg_id}")
        return {
            "success": True,
            "status": "SENT",
            "message_id": msg_id,
            "recipient": target_to,
            "sender": sender,
            "subject": subject,
            "message": f"Gmail API notification dispatched successfully to {target_to}.",
            "timestamp": timestamp
        }

    except Exception as e:
        err_str = str(e)
        logger.error(f"Gmail API send execution failed: {err_str}")

        cat = "UNKNOWN_ERROR"
        if "quota" in err_str.lower():
            cat = "QUOTA_EXCEEDED"
        elif "invalid recipient" in err_str.lower() or "recipient" in err_str.lower():
            cat = "INVALID_RECIPIENT"
        elif "disabled" in err_str.lower():
            cat = "GMAIL_API_DISABLED"
        elif "permission" in err_str.lower() or "forbidden" in err_str.lower():
            cat = "PERMISSION_DENIED"

        return {
            "success": False,
            "status": "FAILED",
            "recipient": target_to,
            "sender": sender,
            "subject": subject,
            "message": f"Gmail API delivery failed: {err_str[:150]}",
            "error_category": cat,
            "error": err_str[:200],
            "timestamp": timestamp
        }
