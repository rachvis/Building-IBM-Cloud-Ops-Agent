"""
databases_tools.py — IBM Cloud Databases (ICD) tools for watsonx Orchestrate.
8 tools: list instances, get details, manage backups, scaling, connections, tasks.
Credentials from ibmcloud_creds connection — never asked in chat.
"""
import os
import sys
import requests
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, region

_ICD_BASE = f"https://api.{region()}.databases.cloud.ibm.com/v5/ibm"


@tool(permission=ToolPermission.READ_ONLY)
def list_database_instances(database_type: Optional[str] = None) -> dict:
    """List all IBM Cloud Database instances in the account. Optionally filter by database type.

    Args:
        database_type: Optional filter e.g. 'postgresql', 'mysql', 'redis', 'mongodb', 'elasticsearch'.
    """
    resp = requests.get(
        "https://resource-controller.cloud.ibm.com/v2/resource_instances",
        headers=auth_headers(),
        params={"resource_id": "databases-for-" + database_type if database_type else None, "limit": 100},
        timeout=30,
    )
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    resources = resp.json().get("resources", [])
    if database_type:
        resources = [r for r in resources if database_type.lower() in r.get("resource_id", "").lower()]
    return {
        "instances": [
            {"guid": r.get("guid"), "name": r.get("name"), "type": r.get("resource_id"),
             "region": r.get("region_id"), "state": r.get("state"), "created_at": r.get("created_at")}
            for r in resources
        ],
        "count": len(resources),
    }


@tool(permission=ToolPermission.READ_ONLY)
def get_database_details(instance_guid: str) -> dict:
    """Get detailed information about an IBM Cloud Database instance including version, members, and state.

    Args:
        instance_guid: The GUID of the database instance. Get from list_database_instances.
    """
    resp = requests.get(f"{_ICD_BASE}/deployments/{instance_guid}", headers=auth_headers(), timeout=30)
    if resp.status_code == 404:
        return {"error": f"Database instance '{instance_guid}' not found."}
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    d = resp.json().get("deployment", {})
    return {
        "name": d.get("name"),
        "type": d.get("type"),
        "version": d.get("version"),
        "state": d.get("state"),
        "region": d.get("region_crn"),
        "platform_options": d.get("platform_options"),
    }


@tool(permission=ToolPermission.READ_ONLY)
def list_database_backups(instance_guid: str) -> dict:
    """List available backups for an IBM Cloud Database instance.

    Args:
        instance_guid: The GUID of the database instance.
    """
    resp = requests.get(f"{_ICD_BASE}/deployments/{instance_guid}/backups", headers=auth_headers(), timeout=30)
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    backups = resp.json().get("backups", [])
    return {
        "backups": [
            {"id": b.get("id"), "type": b.get("type"), "status": b.get("status"),
             "created_at": b.get("created_at"), "size_bytes": b.get("size")}
            for b in backups
        ],
        "count": len(backups),
    }


@tool(permission=ToolPermission.ADMIN)
def create_manual_backup(instance_guid: str) -> dict:
    """Trigger an immediate manual backup for an IBM Cloud Database instance.

    Args:
        instance_guid: The GUID of the database instance.
    """
    resp = requests.post(f"{_ICD_BASE}/deployments/{instance_guid}/backups",
                         headers=auth_headers(), json={}, timeout=30)
    if resp.status_code not in (200, 201, 202):
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {"success": True, "task": resp.json().get("task", {})}


@tool(permission=ToolPermission.READ_ONLY)
def get_connection_strings(instance_guid: str, user_type: str = "admin") -> dict:
    """Get connection strings (host, port, TLS cert) for an IBM Cloud Database instance. Passwords are not returned.

    Args:
        instance_guid: The GUID of the database instance.
        user_type: User type to get connection info for. Default 'admin'.
    """
    resp = requests.get(
        f"{_ICD_BASE}/deployments/{instance_guid}/users/{user_type}/connections/public",
        headers=auth_headers(),
        timeout=30,
    )
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    conn = resp.json().get("connection", {})
    result = {}
    for conn_type, info in conn.items():
        if isinstance(info, dict):
            result[conn_type] = {
                "hosts": info.get("hosts", []),
                "database": info.get("database"),
                "scheme": info.get("scheme"),
                "ssl": info.get("ssl", True),
            }
    return {"connection_strings": result, "note": "Passwords are not returned for security. Retrieve via IBM Secrets Manager."}


@tool(permission=ToolPermission.ADMIN)
def scale_database(instance_guid: str, memory_mb: Optional[int] = None,
                   disk_mb: Optional[int] = None, cpu: Optional[int] = None) -> dict:
    """Scale an IBM Cloud Database instance by changing memory, disk, or CPU allocation.

    Args:
        instance_guid: The GUID of the database instance.
        memory_mb: New memory per member in MB e.g. 4096 for 4GB.
        disk_mb: New disk per member in MB e.g. 20480 for 20GB.
        cpu: New number of CPUs per member.
    """
    groups = {}
    if memory_mb: groups["memory"] = {"allocation_mb": memory_mb}
    if disk_mb: groups["disk"] = {"allocation_mb": disk_mb}
    if cpu: groups["cpu"] = {"allocation_count": cpu}
    if not groups:
        return {"error": "Specify at least one of: memory_mb, disk_mb, cpu."}
    resp = requests.patch(
        f"{_ICD_BASE}/deployments/{instance_guid}/groups/member",
        headers=auth_headers(),
        json=groups,
        timeout=30,
    )
    if resp.status_code not in (200, 202):
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {"success": True, "changes": groups, "task": resp.json().get("task", {})}


@tool(permission=ToolPermission.READ_ONLY)
def list_database_tasks(instance_guid: str) -> dict:
    """List ongoing and recent tasks for an IBM Cloud Database instance (backups, scaling, restores).

    Args:
        instance_guid: The GUID of the database instance.
    """
    resp = requests.get(f"{_ICD_BASE}/deployments/{instance_guid}/tasks", headers=auth_headers(), timeout=30)
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    tasks = resp.json().get("tasks", [])
    return {
        "tasks": [
            {"id": t.get("id"), "description": t.get("description"),
             "status": t.get("status"), "progress_percent": t.get("progress_percent"),
             "created_at": t.get("created_at")}
            for t in tasks
        ],
        "count": len(tasks),
    }


@tool(permission=ToolPermission.READ_ONLY)
def get_database_whitelist(instance_guid: str) -> dict:
    """Get the IP allowlist (whitelist) rules for an IBM Cloud Database instance.

    Args:
        instance_guid: The GUID of the database instance.
    """
    resp = requests.get(f"{_ICD_BASE}/deployments/{instance_guid}/whitelists/ip_addresses",
                        headers=auth_headers(), timeout=30)
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    ips = resp.json().get("ip_addresses", [])
    return {"ip_addresses": ips, "count": len(ips)}
