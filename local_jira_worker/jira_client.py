# Jira REST API client for Local Jira Worker — creates issues via Jira Cloud API
# Co-authored with CoCo
"""
jira_client.py
Handles Jira REST API communication.
Credentials are passed in at initialization — never logged or stored.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from base64 import b64encode

import requests

logger = logging.getLogger(__name__)


class JiraClient:
    def __init__(self, base_url: str, user_email: str, api_token: str):
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        # Basic auth: email:api_token
        auth_str = b64encode(f"{user_email}:{api_token}".encode()).decode()
        self._session.headers.update({
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Creates a Jira issue.
        
        Returns:
            (success: bool, result: dict)
            On success: result has 'key', 'id', 'url'
            On failure: result has 'status_code', 'error'
        """
        url = f"{self._base_url}/rest/api/2/issue"

        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type}
            }
        }
        if priority:
            payload["fields"]["priority"] = {"name": priority}

        try:
            resp = self._session.post(url, json=payload, timeout=30)

            if resp.status_code in (200, 201):
                data = resp.json()
                issue_key = data.get("key", "")
                issue_id = data.get("id", "")
                issue_url = f"{self._base_url}/browse/{issue_key}"
                logger.info(f"Jira issue created: {issue_key}")
                return True, {
                    "key": issue_key,
                    "id": issue_id,
                    "url": issue_url,
                    "status_code": resp.status_code
                }
            else:
                # Do not log response body as it may contain sensitive info
                error_text = resp.text[:500] if resp.text else "No response body"
                logger.error(f"Jira API returned HTTP {resp.status_code}")
                return False, {
                    "status_code": resp.status_code,
                    "error": f"HTTP {resp.status_code}: {error_text}"
                }

        except requests.exceptions.Timeout:
            logger.error("Jira API request timed out")
            return False, {"status_code": None, "error": "Request timed out"}
        except requests.exceptions.ConnectionError as e:
            logger.error("Jira API connection error")
            return False, {"status_code": None, "error": f"Connection error: {str(e)[:200]}"}
        except Exception as e:
            logger.error("Unexpected error calling Jira API")
            return False, {"status_code": None, "error": f"Unexpected: {str(e)[:200]}"}
