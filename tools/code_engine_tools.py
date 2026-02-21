"""
code_engine_tools.py — IBM Cloud Code Engine ADK Tools
=======================================================
These tools let the IBM Cloud Ops Agent manage IBM Cloud Code Engine
applications — including detecting faults, diagnosing root causes,
applying fixes, and verifying recovery.

Available tools:
  ── Discovery ──────────────────────────────────────────────────
  1.  list_code_engine_projects   — List all Code Engine projects
  2.  list_code_engine_apps       — List apps and their health status
  3.  get_app_details             — Full app config (image, env vars, port, scaling)
  4.  get_app_revisions           — List revision history for an app

  ── Diagnosis ──────────────────────────────────────────────────
  5.  get_app_instances           — Check instance / pod crash-loop status
  6.  get_app_logs                — Pull recent stdout/stderr log lines
  7.  check_app_health            — One-shot health summary with root-cause hints

  ── Remediation ────────────────────────────────────────────────
  8.  update_app_env_vars         — Add or update environment variables
  9.  update_app                  — Patch port, image, or resource limits
  10. restart_app                 — Force a rolling restart / new revision
  11. create_app                  — Deploy a new application
  12. delete_app                  — Remove an application

  ── Jobs ───────────────────────────────────────────────────────
  13. list_jobs                   — List batch job definitions
  14. create_job_run              — Trigger a batch job run
  15. get_job_run_status          — Check job run progress
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, get_region

load_dotenv()

CE_API_BASE = os.getenv(
    "IBM_CODE_ENGINE_API",
    f"https://api.{get_region()}.codeengine.cloud.ibm.com/v2"
)


# =============================================================================
# TOOL 1 — List Code Engine Projects
# =============================================================================

def list_code_engine_projects() -> dict:
    """
    List all IBM Cloud Code Engine projects in your account.
    Returns project IDs, names, regions, and status.
    Use project IDs from this list as input to all other Code Engine tools.
    """
    url = f"{CE_API_BASE}/projects"
    response = requests.get(url, headers=auth_headers(), timeout=30)
    if response.status_code != 200:
        return {"error": f"Failed to list projects: {response.status_code} — {response.text}"}
    data = response.json()
    projects = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "region": p.get("region"),
            "status": p.get("status"),
            "created_at": p.get("created_at"),
        }
        for p in data.get("projects", [])
    ]
    return {"projects": projects, "count": len(projects)}


# =============================================================================
# TOOL 2 — List Apps in a Project
# =============================================================================

def list_code_engine_apps(project_id: str) -> dict:
    """
    List all applications in a Code Engine project with health status.
    Status values: ready | deploying | failed | warning | unknown.
    The 'unhealthy' list highlights apps that need attention.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project. Get from list_code_engine_projects().
    """
    if not project_id:
        return {"error": "project_id is required."}
    url = f"{CE_API_BASE}/projects/{project_id}/apps"
    response = requests.get(url, headers=auth_headers(), timeout=30)
    if response.status_code != 200:
        return {"error": f"Failed to list apps: {response.status_code} — {response.text}"}
    data = response.json()
    apps = []
    unhealthy = []
    for app in data.get("apps", []):
        status = app.get("status", "unknown")
        entry = {
            "name": app.get("name"),
            "status": status,
            "image": app.get("image_reference"),
            "url": app.get("endpoint"),
            "port": app.get("image_port", 8080),
            "cpu": app.get("scale_cpu_limit"),
            "memory": app.get("scale_memory_limit"),
            "created_at": app.get("created_at"),
        }
        apps.append(entry)
        if status != "ready":
            unhealthy.append(app.get("name"))
    return {"apps": apps, "unhealthy": unhealthy, "count": len(apps)}


# =============================================================================
# TOOL 3 — Get App Details
# =============================================================================

def get_app_details(project_id: str, app_name: str) -> dict:
    """
    Get the full configuration of a Code Engine application.
    Returns image, port, env vars, scaling, and current status.
    Env vars are critical for diagnosing misconfiguration errors.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}
    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}"
    response = requests.get(url, headers=auth_headers(), timeout=30)
    if response.status_code == 404:
        return {"error": f"App '{app_name}' not found in project '{project_id}'."}
    if response.status_code != 200:
        return {"error": f"Failed to get app: {response.status_code} — {response.text}"}
    app = response.json()
    return {
        "name": app.get("name"),
        "status": app.get("status"),
        "image": app.get("image_reference"),
        "url": app.get("endpoint"),
        "port": app.get("image_port", 8080),
        "env_vars": app.get("run_env_variables", []),
        "scaling": {
            "min_instances": app.get("scale_min_instances", 0),
            "max_instances": app.get("scale_max_instances", 10),
            "concurrency": app.get("scale_concurrency", 100),
            "cpu": app.get("scale_cpu_limit"),
            "memory": app.get("scale_memory_limit"),
        },
        "created_at": app.get("created_at"),
        "updated_at": app.get("updated_at"),
        "latest_revision": app.get("latest_created_revision"),
        "ready_revision": app.get("latest_ready_revision"),
    }


# =============================================================================
# TOOL 4 — Get App Revisions
# =============================================================================

def get_app_revisions(project_id: str, app_name: str) -> dict:
    """
    List the revision history for a Code Engine application.
    Each update creates a new revision. Use this to see what changed recently
    and which revision is currently serving traffic.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}
    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}/revisions"
    response = requests.get(url, headers=auth_headers(), timeout=30)
    if response.status_code != 200:
        return {"error": f"Failed to list revisions: {response.status_code} — {response.text}"}
    data = response.json()
    revisions = [
        {
            "name": r.get("name"),
            "status": r.get("status"),
            "image": r.get("image_reference"),
            "port": r.get("image_port"),
            "created_at": r.get("created_at"),
        }
        for r in data.get("revisions", [])
    ]
    return {
        "revisions": revisions,
        "count": len(revisions),
        "latest": revisions[0]["name"] if revisions else None,
    }


# =============================================================================
# TOOL 5 — Get App Instances (pod / crash-loop status)
# =============================================================================

def get_app_instances(project_id: str, app_name: str) -> dict:
    """
    Check the running instances (pods) of a Code Engine application.
    Reveals crash-looping containers, OOMKilled pods, and instances stuck pending.
    This is the key diagnostic tool for runtime startup failures.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}
    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}/instances"
    response = requests.get(url, headers=auth_headers(), timeout=30)
    if response.status_code != 200:
        return {"error": f"Failed to get instances: {response.status_code} — {response.text}"}
    data = response.json()
    instances = []
    running = pending = failed = 0
    max_restarts = 0
    for inst in data.get("instances", []):
        status = inst.get("status", "unknown")
        restart_count = inst.get("restart_count", 0)
        max_restarts = max(max_restarts, restart_count)
        entry = {
            "name": inst.get("name"),
            "status": status,
            "restart_count": restart_count,
            "exit_code": inst.get("last_exit_code"),
            "reason": inst.get("reason"),
            "message": inst.get("message"),
        }
        instances.append(entry)
        if status == "running":
            running += 1
        elif status in ("pending", "starting"):
            pending += 1
        else:
            failed += 1

    crash_looping = max_restarts >= 3
    if crash_looping:
        diagnosis = (
            f"Container is crash-looping ({max_restarts} restarts). "
            "Use get_app_logs() to read the error. "
            "Common causes: missing env var, wrong port, startup exception."
        )
    elif failed > 0:
        diagnosis = "Instances have failed. Check get_app_logs() for the exit reason."
    elif pending > 0 and running == 0:
        diagnosis = "Instances stuck pending — possible image pull error or resource quota exceeded."
    elif running > 0:
        diagnosis = "Instances appear healthy."
    else:
        diagnosis = "No instances found — app may be scaled to zero or still initialising."

    return {
        "instances": instances,
        "summary": {
            "running": running,
            "pending": pending,
            "failed": failed,
            "total_restarts": max_restarts,
            "crash_looping": crash_looping,
            "diagnosis": diagnosis,
        },
    }


# =============================================================================
# TOOL 6 — Get App Logs
# =============================================================================

def get_app_logs(project_id: str, app_name: str, lines: int = 100) -> dict:
    """
    Retrieve recent stdout/stderr log lines from a Code Engine application.
    Logs reveal startup errors, missing env var panics, port binding failures,
    and unhandled exceptions. This is the primary diagnosis tool.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application.
    lines : int
        Number of recent log lines to return. Default: 100. Max: 500.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}
    lines = min(lines, 500)
    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}/logs"
    response = requests.get(url, headers=auth_headers(), params={"limit": lines}, timeout=30)
    if response.status_code != 200:
        return {
            "error": f"Failed to get logs: {response.status_code} — {response.text}",
            "tip": "If the app never started, logs may be empty. Try get_app_instances() first.",
        }
    data = response.json()
    log_lines = []
    for entry in data.get("logs", []):
        log_lines.append(entry.get("message", str(entry)) if isinstance(entry, dict) else str(entry))

    error_lines = []
    hints = []
    error_kw = ["error", "exception", "traceback", "fatal", "panic", "critical", "failed"]
    for line in log_lines:
        lower = line.lower()
        if any(k in lower for k in error_kw):
            error_lines.append(line)
        if any(p in line for p in ["KeyError", "not set", "undefined", "getenv", "env var", "environment"]):
            for word in line.split():
                clean = word.strip("\"',:()[]")
                if clean.isupper() and len(clean) > 2:
                    hints.append(f"Missing or misconfigured env var: {clean}")
                    break
            else:
                hints.append("Missing or misconfigured environment variable detected.")
        if any(p in lower for p in ["address already in use", "bind:", "eaddrinuse", "failed to listen"]):
            hints.append("Port binding failure detected — verify image_port matches container EXPOSE.")

    return {
        "logs": log_lines,
        "error_lines": error_lines[:20],
        "line_count": len(log_lines),
        "diagnosis_hints": list(dict.fromkeys(hints)) or ["No obvious error patterns found in logs."],
    }


# =============================================================================
# TOOL 7 — Check App Health (comprehensive one-shot diagnosis)
# =============================================================================

def check_app_health(project_id: str, app_name: str) -> dict:
    """
    Comprehensive health check for a Code Engine application.
    Combines status, crash data, and log analysis into a single root-cause
    report with recommended fixes ready to act on.
    This is the FIRST tool to call when an app appears unhealthy.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}

    problems = []
    fixes = []

    # --- App config ---
    details = get_app_details(project_id, app_name)
    if "error" in details:
        return details
    status = details.get("status", "unknown")
    port = details.get("port", 8080)
    env_vars = {e.get("name"): e.get("value", "") for e in details.get("env_vars", [])}

    if status != "ready":
        problems.append(f"App status is '{status}' (expected 'ready').")

    # --- Instances ---
    inst = get_app_instances(project_id, app_name)
    if "summary" in inst:
        s = inst["summary"]
        if s.get("crash_looping"):
            problems.append(
                f"Container crash-looping with {s['total_restarts']} restarts — "
                "failing on every startup attempt."
            )
        elif s.get("failed", 0) > 0:
            problems.append(f"{s['failed']} instance(s) have failed.")
        elif s.get("running", 0) == 0 and s.get("pending", 0) == 0:
            problems.append("No running or pending instances.")

    # --- Logs ---
    logs = get_app_logs(project_id, app_name, lines=150)
    hints = [h for h in logs.get("diagnosis_hints", []) if "No obvious" not in h]
    error_lines = logs.get("error_lines", [])
    problems.extend(hints)

    # --- Recommend fixes ---
    combined = " ".join(problems).lower()
    if "env var" in combined or "missing" in combined or "misconfigured" in combined:
        fixes.append({
            "action": "update_app_env_vars",
            "reason": "Set the missing or wrong environment variables identified in logs.",
        })
    if "port" in combined:
        fixes.append({
            "action": "update_app",
            "params": {"port": "<correct_port>"},
            "reason": "Fix image_port to match the port the container actually binds.",
        })
    if not fixes and problems:
        fixes.append({"action": "restart_app", "reason": "No specific misconfiguration found — try a fresh restart."})

    overall = "healthy" if not problems else ("critical" if len(problems) >= 2 else "degraded")

    return {
        "app_name": app_name,
        "overall_status": overall,
        "app_status": status,
        "current_port": port,
        "current_env_vars": env_vars,
        "problems_detected": problems or ["No problems detected."],
        "recent_error_logs": error_lines[:5],
        "recommended_fixes": fixes,
    }


# =============================================================================
# TOOL 8 — Update App Environment Variables
# =============================================================================

def update_app_env_vars(project_id: str, app_name: str, env_vars: dict) -> dict:
    """
    Add or update environment variables on a Code Engine application.
    A new revision is created automatically. Existing env vars not listed
    here are preserved. Use this to fix missing or incorrect configuration
    without touching the container image.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application to update.
    env_vars : dict
        Key-value pairs to set. Example: {"DATABASE_URL": "postgres://host/db", "LOG_LEVEL": "info"}
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}
    if not env_vars or not isinstance(env_vars, dict):
        return {"error": "env_vars must be a non-empty dict of {NAME: VALUE} pairs."}

    details = get_app_details(project_id, app_name)
    if "error" in details:
        return details

    existing = {e["name"]: e for e in details.get("env_vars", [])}
    for name, value in env_vars.items():
        existing[name] = {"type": "literal", "name": name, "value": str(value)}

    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}"
    response = requests.patch(
        url,
        headers={**auth_headers(), "If-Match": "*"},
        json={"run_env_variables": list(existing.values())},
        timeout=30,
    )
    if response.status_code in (200, 201, 202):
        return {
            "success": True,
            "message": (
                f"Env vars updated on '{app_name}'. New revision deploying. "
                "Verify with check_app_health() in ~60 seconds."
            ),
            "vars_set": list(env_vars.keys()),
        }
    return {"error": f"Failed to update env vars: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 9 — Update App (port, image, resources)
# =============================================================================

def update_app(
    project_id: str,
    app_name: str,
    port: int = None,
    image: str = None,
    cpu: str = None,
    memory: str = None,
    min_instances: int = None,
    max_instances: int = None,
) -> dict:
    """
    Update a Code Engine application's port, image, CPU, memory, or scaling.
    Only the fields you provide are changed — everything else stays as-is.
    A new revision is created and traffic shifts to it automatically.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application to update.
    port : int, optional
        Fix this if port-binding errors appear in logs.
    image : str, optional
        New container image (e.g. "icr.io/ns/app:v2-fixed").
    cpu : str, optional
        CPU limit: "0.25", "0.5", "1", "2".
    memory : str, optional
        Memory limit: "0.5G", "1G", "2G", "4G".
    min_instances : int, optional
        Minimum running instances (0 = scale to zero).
    max_instances : int, optional
        Maximum running instances.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}
    changes = {}
    if port is not None:
        changes["image_port"] = port
    if image is not None:
        changes["image_reference"] = image
    if cpu is not None:
        changes["scale_cpu_limit"] = cpu
    if memory is not None:
        changes["scale_memory_limit"] = memory
    if min_instances is not None:
        changes["scale_min_instances"] = min_instances
    if max_instances is not None:
        changes["scale_max_instances"] = max_instances
    if not changes:
        return {"error": "Provide at least one field to update (port, image, cpu, memory, etc.)."}

    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}"
    response = requests.patch(
        url,
        headers={**auth_headers(), "If-Match": "*"},
        json=changes,
        timeout=30,
    )
    if response.status_code in (200, 201, 202):
        return {
            "success": True,
            "message": (
                f"App '{app_name}' updated. New revision deploying. "
                "Verify with check_app_health() in ~60 seconds."
            ),
            "changes": {k.replace("image_", "").replace("scale_", ""): v for k, v in changes.items()},
        }
    return {"error": f"Failed to update app: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 10 — Restart App
# =============================================================================

def restart_app(project_id: str, app_name: str) -> dict:
    """
    Force a rolling restart of a Code Engine application.
    Creates a new revision so the app picks up any recent config changes
    or recovers from a stuck/degraded state.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application to restart.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}
    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}"
    response = requests.patch(
        url,
        headers={**auth_headers(), "If-Match": "*"},
        json={"scale_initial_instances": 1},
        timeout=30,
    )
    if response.status_code in (200, 201, 202):
        return {
            "success": True,
            "message": (
                f"Restart triggered for '{app_name}'. New revision is being created. "
                "Monitor with check_app_health()."
            ),
        }
    return {"error": f"Failed to restart app: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 11 — Create / Deploy an App
# =============================================================================

def create_app(
    project_id: str,
    app_name: str,
    image: str,
    port: int = 8080,
    min_instances: int = 0,
    max_instances: int = 10,
    cpu: str = "0.25",
    memory: str = "0.5G",
    env_vars: dict = None,
) -> dict:
    """
    Deploy a new application to IBM Cloud Code Engine.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        Unique app name (lowercase letters, numbers, hyphens only).
    image : str
        Container image. Examples:
          "icr.io/my-namespace/my-app:latest"   (IBM Container Registry)
          "docker.io/ibmcom/fluentd:latest"      (Docker Hub)
    port : int
        Port the container listens on. Default: 8080.
    min_instances : int
        0 = scale to zero when idle. Default: 0.
    max_instances : int
        Maximum instances under load. Default: 10.
    cpu : str
        CPU limit: "0.25", "0.5", "1", "2". Default: "0.25".
    memory : str
        Memory limit: "0.5G", "1G", "2G", "4G". Default: "0.5G".
    env_vars : dict, optional
        Environment variables: {"NAME": "value", ...}
    """
    if not project_id or not app_name or not image:
        return {"error": "project_id, app_name, and image are all required."}
    payload = {
        "name": app_name,
        "image_reference": image,
        "image_port": port,
        "scale_min_instances": min_instances,
        "scale_max_instances": max_instances,
        "scale_cpu_limit": cpu,
        "scale_memory_limit": memory,
    }
    if env_vars and isinstance(env_vars, dict):
        payload["run_env_variables"] = [
            {"type": "literal", "name": k, "value": str(v)}
            for k, v in env_vars.items()
        ]
    url = f"{CE_API_BASE}/projects/{project_id}/apps"
    response = requests.post(url, headers=auth_headers(), json=payload, timeout=60)
    if response.status_code in (200, 201):
        app = response.json()
        return {
            "success": True,
            "message": f"App '{app_name}' is deploying.",
            "name": app.get("name"),
            "status": app.get("status"),
            "url": app.get("endpoint"),
            "note": "Allow 1–2 minutes to become fully ready.",
        }
    return {"error": f"Failed to create app: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 12 — Delete an App
# =============================================================================

def delete_app(project_id: str, app_name: str) -> dict:
    """
    Delete a Code Engine application and all its revisions.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    app_name : str
        The name of the application to delete.
    """
    if not project_id or not app_name:
        return {"error": "Both project_id and app_name are required."}
    url = f"{CE_API_BASE}/projects/{project_id}/apps/{app_name}"
    response = requests.delete(url, headers=auth_headers(), timeout=30)
    if response.status_code == 202:
        return {"success": True, "message": f"App '{app_name}' is being deleted."}
    if response.status_code == 404:
        return {"error": f"App '{app_name}' not found."}
    return {"error": f"Failed to delete app: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 13 — List Jobs
# =============================================================================

def list_jobs(project_id: str) -> dict:
    """
    List all batch job definitions in a Code Engine project.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    """
    if not project_id:
        return {"error": "project_id is required."}
    url = f"{CE_API_BASE}/projects/{project_id}/jobs"
    response = requests.get(url, headers=auth_headers(), timeout=30)
    if response.status_code != 200:
        return {"error": f"Failed to list jobs: {response.status_code} — {response.text}"}
    data = response.json()
    jobs = [
        {
            "name": j.get("name"),
            "image": j.get("image_reference"),
            "cpu": j.get("scale_cpu_limit"),
            "memory": j.get("scale_memory_limit"),
            "created_at": j.get("created_at"),
        }
        for j in data.get("jobs", [])
    ]
    return {"jobs": jobs, "count": len(jobs)}


# =============================================================================
# TOOL 14 — Create a Job Run
# =============================================================================

def create_job_run(project_id: str, job_name: str, array_indices: str = "0") -> dict:
    """
    Trigger a run of a Code Engine batch job.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    job_name : str
        The name of the job definition to run.
    array_indices : str
        "0" runs one instance; "0-4" runs five in parallel. Default: "0".
    """
    if not project_id or not job_name:
        return {"error": "project_id and job_name are required."}
    payload = {"job_name": job_name, "scale_array_spec": array_indices}
    url = f"{CE_API_BASE}/projects/{project_id}/job_runs"
    response = requests.post(url, headers=auth_headers(), json=payload, timeout=30)
    if response.status_code in (200, 201):
        run = response.json()
        return {
            "success": True,
            "job_run_name": run.get("name"),
            "status": run.get("status"),
            "message": f"Job '{job_name}' triggered. Poll with get_job_run_status().",
        }
    return {"error": f"Failed to create job run: {response.status_code} — {response.text}"}


# =============================================================================
# TOOL 15 — Get Job Run Status
# =============================================================================

def get_job_run_status(project_id: str, job_run_name: str) -> dict:
    """
    Check the status of a Code Engine batch job run.

    Parameters
    ----------
    project_id : str
        The ID of the Code Engine project.
    job_run_name : str
        The job run name returned by create_job_run().
    """
    if not project_id or not job_run_name:
        return {"error": "project_id and job_run_name are required."}
    url = f"{CE_API_BASE}/projects/{project_id}/job_runs/{job_run_name}"
    response = requests.get(url, headers=auth_headers(), timeout=30)
    if response.status_code == 404:
        return {"error": f"Job run '{job_run_name}' not found."}
    if response.status_code != 200:
        return {"error": f"Failed to get job run: {response.status_code} — {response.text}"}
    run = response.json()
    s = run.get("status_details", {})
    return {
        "job_run_name": run.get("name"),
        "job_name": run.get("job_name"),
        "status": run.get("status"),
        "instances": {
            "succeeded": s.get("succeeded", 0),
            "failed": s.get("failed", 0),
            "pending": s.get("pending", 0),
            "running": s.get("running", 0),
        },
        "started_at": s.get("start_time"),
        "completed_at": s.get("completion_time"),
    }


# =============================================================================
# ADK Tool Registration
# =============================================================================

CODE_ENGINE_TOOLS = [
    {
        "name": "list_code_engine_projects",
        "description": "List all IBM Cloud Code Engine projects in the account.",
        "function": list_code_engine_projects,
        "parameters": {},
    },
    {
        "name": "list_code_engine_apps",
        "description": "List all apps in a Code Engine project with health status. Shows which apps are unhealthy.",
        "function": list_code_engine_apps,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
        },
    },
    {
        "name": "get_app_details",
        "description": "Get full config of a Code Engine app: image, port, env vars, scaling settings.",
        "function": get_app_details,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
        },
    },
    {
        "name": "get_app_revisions",
        "description": "List revision history for a Code Engine app to see what changed recently.",
        "function": get_app_revisions,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
        },
    },
    {
        "name": "get_app_instances",
        "description": "Check pod/instance status. Reveals crash-loops, OOM kills, and pending pods with restart counts.",
        "function": get_app_instances,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
        },
    },
    {
        "name": "get_app_logs",
        "description": "Pull recent stdout/stderr logs. Primary tool for diagnosing startup errors, missing env vars, and exceptions.",
        "function": get_app_logs,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
            "lines": {"type": "integer", "description": "Number of recent log lines. Default 100."},
        },
    },
    {
        "name": "check_app_health",
        "description": "One-shot health check combining status, crashes, and logs into a root-cause report with recommended fixes. Call this first for any unhealthy app.",
        "function": check_app_health,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
        },
    },
    {
        "name": "update_app_env_vars",
        "description": "Set or update environment variables on a Code Engine app. Creates a new revision automatically. Fixes missing-config errors without touching the image.",
        "function": update_app_env_vars,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
            "env_vars": {"type": "object", "description": "Dict of {NAME: VALUE} env vars to set. E.g. {\"DATABASE_URL\": \"postgres://host/db\"}"},
        },
    },
    {
        "name": "update_app",
        "description": "Patch a Code Engine app's port, image, CPU, memory, or scaling. Use to fix port mismatches or deploy a corrected image.",
        "function": update_app,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
            "port": {"type": "integer", "description": "Optional: new port the container listens on."},
            "image": {"type": "string", "description": "Optional: new container image."},
            "cpu": {"type": "string", "description": "Optional: CPU limit e.g. '0.5'."},
            "memory": {"type": "string", "description": "Optional: memory limit e.g. '1G'."},
            "min_instances": {"type": "integer", "description": "Optional: minimum running instances."},
            "max_instances": {"type": "integer", "description": "Optional: maximum running instances."},
        },
    },
    {
        "name": "restart_app",
        "description": "Force a rolling restart of a Code Engine app to pick up config changes or recover from a stuck state.",
        "function": restart_app,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The application name."},
        },
    },
    {
        "name": "create_app",
        "description": "Deploy a new containerized application to Code Engine.",
        "function": create_app,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "Unique app name (lowercase, hyphens allowed)."},
            "image": {"type": "string", "description": "Container image (e.g. icr.io/ns/app:latest)."},
            "port": {"type": "integer", "description": "Port the container listens on. Default 8080."},
            "min_instances": {"type": "integer", "description": "Min instances (0 = scale to zero). Default 0."},
            "max_instances": {"type": "integer", "description": "Max instances. Default 10."},
            "cpu": {"type": "string", "description": "CPU limit e.g. '0.25'. Default '0.25'."},
            "memory": {"type": "string", "description": "Memory limit e.g. '0.5G'. Default '0.5G'."},
            "env_vars": {"type": "object", "description": "Optional env vars as {NAME: VALUE} dict."},
        },
    },
    {
        "name": "delete_app",
        "description": "Delete a Code Engine application and all its revisions.",
        "function": delete_app,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "app_name": {"type": "string", "description": "The app to delete."},
        },
    },
    {
        "name": "list_jobs",
        "description": "List all batch job definitions in a Code Engine project.",
        "function": list_jobs,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
        },
    },
    {
        "name": "create_job_run",
        "description": "Trigger a Code Engine batch job run.",
        "function": create_job_run,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "job_name": {"type": "string", "description": "Job definition to run."},
            "array_indices": {"type": "string", "description": "Indices to run (e.g. '0' or '0-4'). Default '0'."},
        },
    },
    {
        "name": "get_job_run_status",
        "description": "Check the status of a Code Engine job run.",
        "function": get_job_run_status,
        "parameters": {
            "project_id": {"type": "string", "description": "The Code Engine project ID."},
            "job_run_name": {"type": "string", "description": "Job run name from create_job_run()."},
        },
    },
]

if __name__ == "__main__":
    print("Testing Code Engine Tools...")
    result = list_code_engine_projects()
    print(json.dumps(result, indent=2))
