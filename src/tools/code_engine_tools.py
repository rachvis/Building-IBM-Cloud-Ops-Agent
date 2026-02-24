"""
code_engine_tools.py — IBM Cloud Code Engine tools for watsonx Orchestrate.

15 tools: list, diagnose, fix, and manage Code Engine apps and batch jobs.
Credentials come from the ibmcloud_creds connection — never asked in chat.
"""
import os
import sys
import re
import time
import requests
from typing import Optional
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

# Allow importing ibm_auth from same package directory when running inside Orchestrate
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, region, ce_project_id

_CE_BASE = f"https://api.{region()}.codeengine.cloud.ibm.com/v2"


def _ce_get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{_CE_BASE}{path}", headers=auth_headers(), timeout=30, **kwargs)


def _ce_post(path: str, payload: dict) -> requests.Response:
    return requests.post(f"{_CE_BASE}{path}", headers=auth_headers(), json=payload, timeout=60)


def _ce_patch(path: str, payload: dict) -> requests.Response:
    return requests.patch(
        f"{_CE_BASE}{path}",
        headers={**auth_headers(), "If-Match": "*"},
        json=payload,
        timeout=30,
    )


def _ce_delete(path: str) -> requests.Response:
    return requests.delete(f"{_CE_BASE}{path}", headers=auth_headers(), timeout=30)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — List projects
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def list_code_engine_projects() -> dict:
    """List all IBM Cloud Code Engine projects in the account with their IDs, names, regions, and status."""
    resp = _ce_get("/projects")
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {
        "projects": [
            {"id": p["id"], "name": p["name"], "region": p.get("region"), "status": p.get("status")}
            for p in resp.json().get("projects", [])
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — List apps in a project
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def list_code_engine_apps(project_id: str) -> dict:
    """List all applications in a Code Engine project with health status and URLs.

    Args:
        project_id: Code Engine project ID. Use list_code_engine_projects to get this.
    """
    resp = _ce_get(f"/projects/{project_id}/apps")
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    apps, unhealthy = [], []
    for a in resp.json().get("apps", []):
        status = a.get("status", "unknown")
        apps.append({"name": a["name"], "status": status, "image": a.get("image_reference"), "url": a.get("endpoint"), "port": a.get("image_port")})
        if status != "ready":
            unhealthy.append(a["name"])
    return {"apps": apps, "unhealthy": unhealthy, "count": len(apps)}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — Get app details
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def get_app_details(project_id: str, app_name: str) -> dict:
    """Get full configuration of a Code Engine app: image, port, environment variables, CPU, memory, and scaling.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name.
    """
    resp = _ce_get(f"/projects/{project_id}/apps/{app_name}")
    if resp.status_code == 404:
        return {"error": f"App '{app_name}' not found."}
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    a = resp.json()
    return {
        "name": a["name"],
        "status": a.get("status"),
        "image": a.get("image_reference"),
        "port": a.get("image_port"),
        "cpu": a.get("scale_cpu_limit"),
        "memory": a.get("scale_memory_limit"),
        "min_instances": a.get("scale_min_instances"),
        "max_instances": a.get("scale_max_instances"),
        "env_vars": {e["name"]: e.get("value", "***") for e in a.get("run_env_variables", [])},
        "url": a.get("endpoint"),
        "latest_revision": a.get("latest_ready_revision"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 — Get app instances (pod / crash-loop status)
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def get_app_instances(project_id: str, app_name: str) -> dict:
    """Check running pod/instance status for a Code Engine app. Reveals crash-loops, OOM kills, and restart counts.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name.
    """
    resp = _ce_get(f"/projects/{project_id}/apps/{app_name}/instances")
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    instances = resp.json().get("app_instances", [])
    result = []
    max_restarts = 0
    for i in instances:
        rc = i.get("restart_count", 0)
        max_restarts = max(max_restarts, rc)
        result.append({"name": i.get("name"), "status": i.get("status"), "restart_count": rc, "reason": i.get("reason")})
    return {
        "instances": result,
        "total": len(result),
        "crash_looping": max_restarts >= 3,
        "max_restarts": max_restarts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5 — Get app logs
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def get_app_logs(project_id: str, app_name: str, lines: int = 100) -> dict:
    """Fetch recent stdout/stderr log lines from a Code Engine app. Primary tool for diagnosing startup errors, missing env vars, and exceptions.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name.
        lines: Number of recent log lines to return. Default 100.
    """
    resp = _ce_get(f"/projects/{project_id}/apps/{app_name}/logs", params={"limit": min(lines, 500)})
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}", "tip": "App may not be running. Try get_app_instances first."}
    log_lines = [e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in resp.json().get("logs", [])]
    error_lines = [l for l in log_lines if any(k in l.lower() for k in ["error", "exception", "fatal", "panic", "traceback"])]
    hints = []
    for l in log_lines:
        if "KeyError" in l or "environ" in l.lower():
            match = re.search(r"KeyError: ['\"]?([A-Z_]{2,})['\"]?", l)
            hints.append(f"Missing env var: {match.group(1)}" if match else "Missing environment variable detected")
        if any(p in l.lower() for p in ["address already in use", "bind:", "eaddrinuse"]):
            hints.append("Port binding failure — image_port may not match container EXPOSE port")
    return {"logs": log_lines, "error_lines": error_lines[:20], "hints": list(dict.fromkeys(hints))}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 6 — Check app health (one-shot diagnosis)
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def check_app_health(project_id: str, app_name: str) -> dict:
    """One-shot health check combining app status, crash data, and log analysis into a root-cause report with recommended fixes. Call this first for any unhealthy app.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name.
    """
    details = get_app_details(project_id, app_name)
    if "error" in details:
        return details
    status = details.get("status", "unknown")
    problems, fixes = [], []
    if status != "ready":
        problems.append(f"App status is '{status}' (expected 'ready')")

    inst = get_app_instances(project_id, app_name)
    if inst.get("crash_looping"):
        problems.append(f"Container crash-looping with {inst['max_restarts']} restarts")

    logs = get_app_logs(project_id, app_name, lines=150)
    for h in logs.get("hints", []):
        problems.append(h)

    combined = " ".join(problems).lower()
    if "env var" in combined or "missing" in combined:
        fixes.append({"action": "update_app_env_vars", "reason": "Set the missing environment variable identified in logs"})
    if "port" in combined:
        fixes.append({"action": "update_app", "params": {"port": "<correct_port>"}, "reason": "Fix port to match what the container actually binds"})
    if not fixes and problems:
        fixes.append({"action": "restart_app", "reason": "No specific misconfiguration found — try a fresh restart"})

    return {
        "app": app_name,
        "status": status,
        "overall_health": "healthy" if not problems else "unhealthy",
        "problems": problems or ["No problems detected"],
        "recommended_fixes": fixes,
        "recent_error_logs": logs.get("error_lines", [])[:5],
        "config": {"image": details.get("image"), "port": details.get("port"), "env_vars": details.get("env_vars")},
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 7 — Update app environment variables
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.ADMIN)
def update_app_env_vars(project_id: str, app_name: str, env_vars: dict) -> dict:
    """Set or update environment variables on a Code Engine app. Creates a new revision automatically. Existing vars not listed are preserved.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name.
        env_vars: Key-value pairs to set, e.g. {"DATABASE_URL": "postgres://host/db", "LOG_LEVEL": "info"}.
    """
    details = get_app_details(project_id, app_name)
    if "error" in details:
        return details
    existing = {k: {"type": "literal", "name": k, "value": v} for k, v in details.get("env_vars", {}).items() if v != "***"}
    existing.update({k: {"type": "literal", "name": k, "value": str(v)} for k, v in env_vars.items()})
    resp = _ce_patch(f"/projects/{project_id}/apps/{app_name}", {"run_env_variables": list(existing.values())})
    if resp.status_code not in (200, 201, 202):
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {"success": True, "vars_set": list(env_vars.keys()), "message": "New revision triggered. Check health in ~60s."}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 8 — Update app (port, image, resources)
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.ADMIN)
def update_app(project_id: str, app_name: str,
               port: Optional[int] = None, image: Optional[str] = None,
               cpu: Optional[str] = None, memory: Optional[str] = None,
               min_instances: Optional[int] = None, max_instances: Optional[int] = None) -> dict:
    """Patch a Code Engine app's port, image, CPU, memory, or scaling. Only specified fields change.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name.
        port: New container port, e.g. 5000.
        image: New container image reference.
        cpu: CPU limit e.g. '0.5'.
        memory: Memory limit e.g. '1G'.
        min_instances: Minimum running instances (0 = scale to zero).
        max_instances: Maximum running instances.
    """
    patch = {}
    if port is not None: patch["image_port"] = port
    if image is not None: patch["image_reference"] = image
    if cpu is not None: patch["scale_cpu_limit"] = cpu
    if memory is not None: patch["scale_memory_limit"] = memory
    if min_instances is not None: patch["scale_min_instances"] = min_instances
    if max_instances is not None: patch["scale_max_instances"] = max_instances
    if not patch:
        return {"error": "No changes specified."}
    resp = _ce_patch(f"/projects/{project_id}/apps/{app_name}", patch)
    if resp.status_code not in (200, 201, 202):
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {"success": True, "changes": patch, "message": "New revision triggered. Check health in ~60s."}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 9 — Restart app
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.ADMIN)
def restart_app(project_id: str, app_name: str) -> dict:
    """Force a rolling restart of a Code Engine app to pick up config changes or recover from a stuck state.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name.
    """
    resp = _ce_patch(f"/projects/{project_id}/apps/{app_name}",
                     {"run_env_variables": [{"name": "_RESTART", "value": str(int(time.time())), "type": "literal"}]})
    if resp.status_code not in (200, 201, 202):
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {"success": True, "message": f"Restart triggered for '{app_name}'. Monitor with check_app_health."}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 10 — Create app
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.ADMIN)
def create_app(project_id: str, app_name: str, image: str, port: int = 8080,
               min_instances: int = 0, max_instances: int = 10,
               cpu: str = "0.25", memory: str = "0.5G",
               env_vars: Optional[dict] = None) -> dict:
    """Deploy a new containerised application to IBM Cloud Code Engine.

    Args:
        project_id: Code Engine project ID.
        app_name: Unique app name (lowercase, hyphens allowed).
        image: Container image e.g. icr.io/namespace/app:latest.
        port: Port the container listens on. Default 8080.
        min_instances: Minimum instances (0 = scale to zero). Default 0.
        max_instances: Maximum instances. Default 10.
        cpu: CPU limit e.g. '0.25'. Default '0.25'.
        memory: Memory limit e.g. '0.5G'. Default '0.5G'.
        env_vars: Optional environment variables as name/value dict.
    """
    payload = {"name": app_name, "image_reference": image, "image_port": port,
               "scale_min_instances": min_instances, "scale_max_instances": max_instances,
               "scale_cpu_limit": cpu, "scale_memory_limit": memory}
    if env_vars:
        payload["run_env_variables"] = [{"type": "literal", "name": k, "value": str(v)} for k, v in env_vars.items()]
    resp = _ce_post(f"/projects/{project_id}/apps", payload)
    if resp.status_code not in (200, 201, 202):
        return {"error": f"{resp.status_code}: {resp.text}"}
    a = resp.json()
    return {"success": True, "name": a.get("name"), "status": a.get("status"), "url": a.get("endpoint")}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 11 — Delete app
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.ADMIN)
def delete_app(project_id: str, app_name: str) -> dict:
    """Delete a Code Engine application and all its revisions. This action is irreversible.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name to delete.
    """
    resp = _ce_delete(f"/projects/{project_id}/apps/{app_name}")
    if resp.status_code == 404:
        return {"error": f"App '{app_name}' not found."}
    if resp.status_code not in (200, 202, 204):
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {"success": True, "deleted": app_name}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 12 — Get app revisions
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def get_app_revisions(project_id: str, app_name: str) -> dict:
    """List revision history for a Code Engine app to see what configuration changes were made recently.

    Args:
        project_id: Code Engine project ID.
        app_name: Application name.
    """
    resp = _ce_get(f"/projects/{project_id}/apps/{app_name}/revisions")
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    revs = resp.json().get("revisions", [])
    return {"revisions": [{"name": r.get("name"), "status": r.get("status"), "image": r.get("image_reference"),
                           "port": r.get("image_port"), "created_at": r.get("created_at")} for r in revs], "count": len(revs)}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 13 — List jobs
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def list_jobs(project_id: str) -> dict:
    """List all batch job definitions in a Code Engine project.

    Args:
        project_id: Code Engine project ID.
    """
    resp = _ce_get(f"/projects/{project_id}/jobs")
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    return {"jobs": [{"name": j["name"], "image": j.get("image_reference")} for j in resp.json().get("jobs", [])]}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 14 — Create job run
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.ADMIN)
def create_job_run(project_id: str, job_name: str, array_indices: str = "0") -> dict:
    """Trigger a Code Engine batch job run.

    Args:
        project_id: Code Engine project ID.
        job_name: Job definition name to run.
        array_indices: Indices to run e.g. '0' or '0-4'. Default '0'.
    """
    resp = _ce_post(f"/projects/{project_id}/job_runs", {"job_name": job_name, "scale_array_spec": array_indices})
    if resp.status_code not in (200, 201, 202):
        return {"error": f"{resp.status_code}: {resp.text}"}
    r = resp.json()
    return {"job_run_name": r.get("name"), "status": r.get("status")}


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 15 — Get job run status
# ─────────────────────────────────────────────────────────────────────────────
@tool(permission=ToolPermission.READ_ONLY)
def get_job_run_status(project_id: str, job_run_name: str) -> dict:
    """Check the status and progress of a Code Engine batch job run.

    Args:
        project_id: Code Engine project ID.
        job_run_name: Job run name returned by create_job_run.
    """
    resp = _ce_get(f"/projects/{project_id}/job_runs/{job_run_name}")
    if resp.status_code == 404:
        return {"error": f"Job run '{job_run_name}' not found."}
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    r = resp.json()
    s = r.get("status_details", {})
    return {"name": r.get("name"), "status": r.get("status"),
            "succeeded": s.get("succeeded", 0), "failed": s.get("failed", 0),
            "running": s.get("running", 0), "started_at": s.get("start_time")}
