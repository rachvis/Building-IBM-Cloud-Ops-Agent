"""
cloud_logs_tools.py — IBM Cloud Logs tools for watsonx Orchestrate.
6 tools: search, tail, filter by severity, count errors, list alerts.
Credentials from ibmcloud_creds connection — never asked in chat.
"""
import os
import sys
import requests
from datetime import datetime, timedelta, timezone
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, logs_instance_guid, logs_region


def _logs_base() -> str:
    guid = logs_instance_guid()
    if not guid:
        raise EnvironmentError("CLOUD_LOGS_INSTANCE_GUID not set in .env")
    return f"https://{guid}.api.{logs_region()}.logs.cloud.ibm.com/v1"


def _query(query: str, minutes_ago: int, limit: int, severity: str = None) -> dict:
    now = datetime.now(timezone.utc)
    payload = {
        "query": query,
        "metadata": {
            "start_date": (now - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "limit": min(limit, 500),
    }
    if severity:
        payload["severity"] = severity.lower()
    resp = requests.post(f"{_logs_base()}/logs/query", headers=auth_headers(), json=payload, timeout=30)
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    logs = [{"timestamp": e.get("timestamp"), "severity": e.get("severity"),
              "text": e.get("text", e.get("log_line", "")), "app": e.get("applicationName")}
             for e in resp.json().get("results", [])]
    return {"logs": logs, "count": len(logs), "query": query, "time_range_minutes": minutes_ago}


@tool(permission=ToolPermission.READ_ONLY)
def list_log_instances() -> dict:
    """List all IBM Cloud Logs instances in the account with their GUIDs, names, and regions."""
    resp = requests.get(
        "https://resource-controller.cloud.ibm.com/v2/resource_instances",
        headers=auth_headers(),
        params={"resource_id": "logs", "limit": 50},
        timeout=30,
    )
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {
        "instances": [
            {"guid": r.get("guid"), "name": r.get("name"), "region": r.get("region_id"), "state": r.get("state")}
            for r in resp.json().get("resources", [])
        ]
    }


@tool(permission=ToolPermission.READ_ONLY)
def search_logs(query: str, minutes_ago: int = 60, limit: int = 50) -> dict:
    """Search IBM Cloud Logs by text query over a time window.

    Args:
        query: Text to search for e.g. 'error', 'timeout', 'NullPointerException'.
        minutes_ago: How far back to search in minutes. Default 60.
        limit: Maximum log lines to return. Default 50.
    """
    return _query(query, minutes_ago, limit)


@tool(permission=ToolPermission.READ_ONLY)
def get_recent_logs(minutes_ago: int = 15, limit: int = 100) -> dict:
    """Get the most recent log entries across all applications.

    Args:
        minutes_ago: How far back to look in minutes. Default 15.
        limit: Number of lines to return. Default 100.
    """
    return _query("*", minutes_ago, limit)


@tool(permission=ToolPermission.READ_ONLY)
def get_logs_by_severity(severity: str, minutes_ago: int = 60, limit: int = 100) -> dict:
    """Get logs filtered to a specific severity level.

    Args:
        severity: One of debug, info, warning, error, critical.
        minutes_ago: Time window in minutes. Default 60.
        limit: Max results. Default 100.
    """
    valid = ["debug", "info", "warning", "error", "critical"]
    if severity.lower() not in valid:
        return {"error": f"Invalid severity '{severity}'. Must be one of: {', '.join(valid)}"}
    return _query("*", minutes_ago, limit, severity)


@tool(permission=ToolPermission.READ_ONLY)
def count_errors(minutes_ago: int = 60) -> dict:
    """Count error and critical log events and return a health label: healthy, degraded, or critical.

    Args:
        minutes_ago: Time window to count over in minutes. Default 60.
    """
    errors = _query("*", minutes_ago, 500, "error")
    crits = _query("*", minutes_ago, 500, "critical")
    if "error" in errors:
        return errors
    ec, cc = errors.get("count", 0), crits.get("count", 0)
    total = ec + cc
    health = "healthy" if total == 0 else ("critical" if cc > 0 or ec > 50 else "degraded")
    return {"time_window_minutes": minutes_ago, "error_count": ec, "critical_count": cc,
            "total_issues": total, "health_status": health}


@tool(permission=ToolPermission.READ_ONLY)
def get_log_alerts() -> dict:
    """List all configured alerting rules for the Cloud Logs instance."""
    try:
        resp = requests.get(f"{_logs_base()}/alerts", headers=auth_headers(), timeout=30)
    except EnvironmentError as e:
        return {"error": str(e)}
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {
        "alerts": [{"name": a.get("name"), "enabled": a.get("is_active"), "severity": a.get("severity")}
                   for a in resp.json().get("alerts", [])]
    }
