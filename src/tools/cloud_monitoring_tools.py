"""
cloud_monitoring_tools.py — IBM Cloud Monitoring (Sysdig) tools for watsonx Orchestrate.
6 tools: list instances, query metrics, get alerts, check alert events, list dashboards.
Credentials from ibmcloud_creds connection — never asked in chat.
"""
import os
import sys
import requests
from datetime import datetime, timedelta, timezone
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, region


def _mon_url() -> str:
    return f"https://{region()}.monitoring.cloud.ibm.com"


def _mon_headers() -> dict:
    h = auth_headers()
    guid = os.environ.get("CLOUD_MONITORING_INSTANCE_GUID", "")
    if guid:
        h["IBMInstanceID"] = guid
    return h


@tool(permission=ToolPermission.READ_ONLY)
def list_monitoring_instances() -> dict:
    """List all IBM Cloud Monitoring instances in the account with their GUIDs and names."""
    resp = requests.get(
        "https://resource-controller.cloud.ibm.com/v2/resource_instances",
        headers=auth_headers(),
        params={"resource_id": "sysdig-monitor", "limit": 50},
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
def query_metric(metric: str, minutes_ago: int = 30) -> dict:
    """Query a metric from IBM Cloud Monitoring. Returns time-series data points.

    Args:
        metric: Metric name e.g. 'cpu.used.percent', 'memory.bytes.used', 'net.bytes.in'.
        minutes_ago: How far back to query in minutes. Default 30.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes_ago)
    payload = {
        "metrics": [{"id": metric, "aggregations": {"time": "avg"}}],
        "filter": "",
        "time": {
            "from": int(start.timestamp()) * 1000000,
            "to": int(now.timestamp()) * 1000000,
            "sampling": max(60, minutes_ago * 60 // 10) * 1000000,
        },
        "last": minutes_ago * 60,
    }
    resp = requests.post(f"{_mon_url()}/api/data/batch", headers=_mon_headers(), json=payload, timeout=30)
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    data = resp.json()
    return {"metric": metric, "time_range_minutes": minutes_ago, "data": data.get("data", [])}


@tool(permission=ToolPermission.READ_ONLY)
def get_platform_metrics(service: str = "codeengine", minutes_ago: int = 30) -> dict:
    """Get IBM Cloud platform metrics for a specific service.

    Args:
        service: IBM Cloud service name e.g. 'codeengine', 'databases-for-postgresql', 'containers-kubernetes'.
        minutes_ago: How far back in minutes. Default 30.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes_ago)
    payload = {
        "metrics": [{"id": f"ibm_{service}_*", "aggregations": {"time": "avg"}}],
        "filter": f"ibm_service_name = '{service}'",
        "time": {"from": int(start.timestamp()) * 1000000, "to": int(now.timestamp()) * 1000000},
        "last": minutes_ago * 60,
    }
    resp = requests.post(f"{_mon_url()}/api/data/batch", headers=_mon_headers(), json=payload, timeout=30)
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {"service": service, "time_range_minutes": minutes_ago, "data": resp.json().get("data", [])}


@tool(permission=ToolPermission.READ_ONLY)
def list_alerts() -> dict:
    """List all configured alert rules in the IBM Cloud Monitoring instance."""
    resp = requests.get(f"{_mon_url()}/api/alerts", headers=_mon_headers(), timeout=30)
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    alerts = resp.json().get("alerts", [])
    return {
        "alerts": [
            {"id": a.get("id"), "name": a.get("name"), "enabled": a.get("enabled"),
             "severity": a.get("severity"), "condition": a.get("condition", {}).get("queryExpression")}
            for a in alerts
        ],
        "count": len(alerts),
    }


@tool(permission=ToolPermission.READ_ONLY)
def get_alert_events(minutes_ago: int = 60) -> dict:
    """Get recent alert firing events from IBM Cloud Monitoring.

    Args:
        minutes_ago: How far back to look in minutes. Default 60.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes_ago)
    resp = requests.get(
        f"{_mon_url()}/api/events",
        headers=_mon_headers(),
        params={"from": int(start.timestamp()), "to": int(now.timestamp()), "limit": 100},
        timeout=30,
    )
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    events = resp.json().get("events", [])
    return {
        "events": [
            {"name": e.get("name"), "severity": e.get("severity"),
             "timestamp": e.get("timestamp"), "description": e.get("description")}
            for e in events
        ],
        "count": len(events),
        "time_range_minutes": minutes_ago,
    }


@tool(permission=ToolPermission.READ_ONLY)
def get_team_dashboards() -> dict:
    """List all available dashboards in the IBM Cloud Monitoring instance."""
    resp = requests.get(f"{_mon_url()}/api/v3/dashboards", headers=_mon_headers(), timeout=30)
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    dashboards = resp.json().get("dashboards", [])
    return {
        "dashboards": [{"id": d.get("id"), "name": d.get("name"), "shared": d.get("shared", False)} for d in dashboards],
        "count": len(dashboards),
    }
