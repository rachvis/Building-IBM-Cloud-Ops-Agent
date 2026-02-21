# IBM Cloud Ops Agent — End-to-End Demo
## Detecting and Auto-Fixing a Broken Code Engine App

---

## Overview

This walkthrough demonstrates an **IBM Cloud Ops Agent** built on
**watsonx Orchestrate on IBM Cloud** autonomously detecting errors
in a live IBM Cloud Code Engine application and fixing them — without
any human intervention beyond the initial prompt.

**Total demo time:** ~15 minutes  
**Skill level required:** Beginner — no coding during the demo

---

## What the Agent Does

```
You say:   "Check the health of faulty-api and fix any issues."
           ↓
Agent:  1. Scans all apps → spots faulty-api is not 'ready'
        2. Runs health check → sees crash-looping + port mismatch + missing env var
        3. Reads logs → confirms DATABASE_URL KeyError and port 3000 vs 5000
        4. Patches the port from 3000 → 5000
        5. Sets DATABASE_URL environment variable
        6. Waits ~60s and re-runs health check → confirms status is now 'ready'
        7. Reports back: "All issues resolved. App is healthy."
```

---

## The Three Bugs

The demo app `faulty-api` is deliberately deployed with three faults:

| # | Bug | Symptom | Root Cause |
|---|-----|---------|------------|
| 1 | **Wrong port** | 502 Bad Gateway on every request | App binds port `5000`; Code Engine is configured with `image_port=3000` |
| 2 | **Missing env var** | `/api/data` returns HTTP 500 | `DATABASE_URL` env var not set; code uses `os.environ["DATABASE_URL"]` (no fallback) |
| 3 | **Crash route** | `/api/crash` always 500 | Intentional `ZeroDivisionError` — generates tracebacks in logs for the agent to read |

---

## Prerequisites

Before running the demo, complete these one-time setup steps.

### 1. IBM Cloud Account

- IBM Cloud account with a Code Engine project created
- IBM Cloud API key with Code Engine access

### 2. Toolkit installed

```bash
cd ibm-cloud-toolkit
./install.sh
```

### 3. watsonx Orchestrate on IBM Cloud

- watsonx Orchestrate instance provisioned on IBM Cloud
- IBM Cloud toolkit OpenAPI spec imported into Orchestrate
  (see `docs/GUIDE.md` → "Importing into watsonx Orchestrate")

### 4. Docker installed (for building the demo image)

```bash
docker --version
# Docker version 24.x or later
```

---

## Step 1 — Build the Faulty App Container Image

```bash
cd demo/faulty_app
docker build -t faulty-api:demo .
```

Verify it built:
```bash
docker images | grep faulty-api
# faulty-api   demo   abc123def456   10 seconds ago   145MB
```

---

## Step 2 — Push the Image to a Registry

### Option A — IBM Container Registry (Recommended)

```bash
# Log in to IBM Container Registry
ibmcloud cr login

# Create a namespace if you don't have one
ibmcloud cr namespace-add my-demo-namespace

# Tag and push
docker tag faulty-api:demo icr.io/my-demo-namespace/faulty-api:demo
docker push icr.io/my-demo-namespace/faulty-api:demo

# Verify
ibmcloud cr images --restrict my-demo-namespace
```

### Option B — Docker Hub

```bash
docker tag faulty-api:demo YOUR_DOCKERHUB_USERNAME/faulty-api:demo
docker push YOUR_DOCKERHUB_USERNAME/faulty-api:demo
```

> **Note your full image name** — you'll need it in Step 3.  
> Example: `icr.io/my-demo-namespace/faulty-api:demo`

---

## Step 3 — Deploy the Faulty App to Code Engine

This deploys the app **with its bugs intact** — wrong port, no DATABASE_URL.

### Option A — IBM Cloud CLI (Recommended)

```bash
# Log in
ibmcloud login --apikey $IBM_CLOUD_API_KEY -r us-south

# Target your Code Engine project
ibmcloud ce project select --name YOUR_PROJECT_NAME

# Deploy with INTENTIONALLY WRONG port (3000 instead of 5000)
# and WITHOUT DATABASE_URL — these are the bugs the agent will fix
ibmcloud ce application create \
  --name faulty-api \
  --image icr.io/my-demo-namespace/faulty-api:demo \
  --port 3000 \
  --min-scale 1 \
  --max-scale 3 \
  --cpu 0.25 \
  --memory 0.5G
```

> ⚠️  **Do NOT set DATABASE_URL** — its absence is Bug #2.  
> ⚠️  **Port 3000 is intentional** — the mismatch with the app's actual port 5000 is Bug #1.

### Option B — IBM Cloud Console UI

1. Go to [IBM Cloud Console](https://cloud.ibm.com)
2. Navigate to **Code Engine** → your project → **Applications**
3. Click **Create application**
4. Fill in:
   - **Name:** `faulty-api`
   - **Image:** `icr.io/my-demo-namespace/faulty-api:demo`
   - **Listening port:** `3000`  ← intentionally wrong
   - **Min instances:** `1`
   - Leave all environment variables **empty** ← no DATABASE_URL
5. Click **Create**

### Option C — Ops Agent Itself (Meta Demo!)

You can use the Ops Agent to deploy the faulty app:

```
Tell the agent:
"Deploy a new Code Engine app called 'faulty-api' using image
icr.io/my-demo-namespace/faulty-api:demo with port 3000 and
min 1 instance. Do not set any environment variables."
```

The agent will call `create_app()` with those parameters.

---

## Step 4 — Verify the App is Broken

Wait 2 minutes for the deployment to stabilise, then confirm it's broken:

### Via IBM Cloud CLI

```bash
ibmcloud ce application get --name faulty-api
# STATUS: ready (the process is up, but serving 502s due to port bug)

# Grab the URL and test it
APP_URL=$(ibmcloud ce application get --name faulty-api --output json | jq -r '.status.url')
curl -s $APP_URL/health
# curl: (52) Empty reply from server   ← Bug 1: port mismatch
curl -s $APP_URL/api/data
# curl: (52) Empty reply from server
```

### Via IBM Cloud Console

- Code Engine → Applications → `faulty-api` → Status shows **Ready** (app runs) 
- Click the app URL → browser shows **502 Bad Gateway** ← Bug #1 visible

---

## Step 5 — Run the Demo

Open your watsonx Orchestrate chat and use one of these prompts.

---

### 🎯 Demo Prompt 1 — Minimal (Recommended for first demo)

```
Check the health of the app "faulty-api" in my Code Engine project
and automatically fix any issues you find.
```

**Expected agent flow:**

```
Agent → list_code_engine_projects()
        "Found project: ops-demo-project (id: abc123)"

Agent → list_code_engine_apps(project_id="abc123")
        "faulty-api — status: ready, port: 3000"
        "No apps flagged unhealthy by status alone..."

Agent → check_app_health(project_id="abc123", app_name="faulty-api")
        "Problems detected:
           • Port mismatch: configured port=3000, app binds port=5000
           • crash-looping on /api/data: KeyError 'DATABASE_URL'
         Recommended fixes:
           • update_app (port: 5000)
           • update_app_env_vars (DATABASE_URL: sqlite:///demo.db)"

Agent → update_app(project_id="abc123", app_name="faulty-api", port=5000)
        "✅ Port updated to 5000. New revision deploying."

Agent → update_app_env_vars(
            project_id="abc123",
            app_name="faulty-api",
            env_vars={"DATABASE_URL": "sqlite:///demo.db"}
        )
        "✅ DATABASE_URL set. New revision deploying."

Agent → [waits ~60 seconds for revision to stabilise]

Agent → check_app_health(project_id="abc123", app_name="faulty-api")
        "✅ App status: ready
         ✅ No crash-looping detected
         ✅ No missing env var errors in logs
         Overall status: healthy"

Agent → "I've fixed faulty-api. Here's what I changed:
          1. Port updated: 3000 → 5000 (matches what the container binds)
          2. DATABASE_URL set to sqlite:///demo.db (resolves /api/data 500 errors)
         The app is now healthy and serving traffic."
```

---

### 🎯 Demo Prompt 2 — Full Scan (Good for showing proactive monitoring)

```
Scan all Code Engine apps in my account for any that are unhealthy
or have errors. For each one, diagnose the root cause and apply fixes.
```

**Expected agent flow:**

```
Agent → list_code_engine_projects()   → finds all projects
Agent → list_code_engine_apps()       → for each project, lists apps
Agent → check_app_health("faulty-api") → finds issues
Agent → [fixes port + env var as above]
Agent → "Scanned 3 apps across 1 project.
          • my-good-app:  ✅ Healthy
          • api-gateway:  ✅ Healthy
          • faulty-api:   ⚠️  Fixed — port mismatch + missing env var resolved."
```

---

### 🎯 Demo Prompt 3 — Conversational Step-by-Step

Good for live demos where you want to narrate each agent action:

```
Step 1: "List all my Code Engine projects"
Step 2: "List the apps in project [project-id]"
Step 3: "Run a health check on faulty-api"
Step 4: "What logs is faulty-api producing?"
Step 5: "Fix the port issue on faulty-api"
Step 6: "Set the DATABASE_URL environment variable on faulty-api"
Step 7: "Check the health of faulty-api again to confirm it's fixed"
```

This step-by-step style is ideal for showing each tool call individually.

---

### 🎯 Demo Prompt 4 — Simulated Alert Response

```
We just received an alert that faulty-api is returning 502 errors.
Please investigate, find the root cause, and remediate immediately.
```

This mirrors a real on-call scenario. The agent will:
1. Triage (check_app_health)
2. Deep-dive into logs (get_app_logs)
3. Apply fixes (update_app + update_app_env_vars)
4. Confirm resolution (check_app_health again)
5. Produce an incident summary

---

## Step 6 — Verify the Fix

After the agent completes, confirm the app is healthy:

```bash
# Check status
ibmcloud ce application get --name faulty-api
# STATUS: ready

# Test the endpoints
APP_URL=$(ibmcloud ce application get --name faulty-api --output json | jq -r '.status.url')

curl -s $APP_URL/health | python3 -m json.tool
# { "service": "faulty-api", "status": "ok" }

curl -s $APP_URL/api/data | python3 -m json.tool
# { "database": "sqlite:///demo.db", "records": [...], "status": "ok" }
```

---

## Understanding the Tool Chain

This diagram shows which tools the agent uses at each stage:

```
DETECT ─────────────────────────────────────────────────────────
  list_code_engine_projects()     Find which project to look in
  list_code_engine_apps()         Spot unhealthy apps

DIAGNOSE ────────────────────────────────────────────────────────
  check_app_health()              One-shot root cause analysis
    └─ get_app_details()          Read port, image, env vars
    └─ get_app_instances()        Detect crash-loops & restarts
    └─ get_app_logs()             Read error messages from stdout

REMEDIATE ───────────────────────────────────────────────────────
  update_app()                    Fix port, image, or resources
  update_app_env_vars()           Set missing env vars
  restart_app()                   Force new revision if needed

VERIFY ──────────────────────────────────────────────────────────
  check_app_health()              Confirm fix worked
  get_app_revisions()             Show before/after revision history
```

---

## Troubleshooting the Demo

### App shows "ready" but URL returns 502

This is expected — Bug #1 (port mismatch) means the process starts fine
but is unreachable. The agent will fix this via `update_app(port=5000)`.

### Agent says "no unhealthy apps found"

Code Engine may report status `ready` even with the port bug (the process
is alive). The agent should then use `check_app_health()` which catches
the port mismatch via log analysis. Try the prompt:

```
Run check_app_health on faulty-api — I suspect it has configuration issues.
```

### "Image pull failed" error

Your Code Engine project doesn't have access to the registry. Fix:

```bash
# For IBM Container Registry — create an image pull secret
ibmcloud ce secret create --format registry \
  --name icr-pull-secret \
  --server icr.io \
  --username iamapikey \
  --password $IBM_CLOUD_API_KEY

# Attach it to your app
ibmcloud ce application update --name faulty-api \
  --registry-secret icr-pull-secret
```

### Logs are empty

The app may not have started yet. Wait 30 seconds and try again, or check:
```bash
ibmcloud ce application events --name faulty-api
```

### Agent can't find the project

Make sure `IBM_CLOUD_API_KEY` in your `.env` has Code Engine access. Test:
```bash
source venv/bin/activate
python3 tools/test_connection.py
python3 -c "from tools.code_engine_tools import list_code_engine_projects; import json; print(json.dumps(list_code_engine_projects(), indent=2))"
```

---

## Clean Up

After the demo, delete the app to avoid ongoing charges:

```bash
# Via CLI
ibmcloud ce application delete --name faulty-api --force

# Or ask the agent:
# "Delete the faulty-api application from my Code Engine project"
```

---

## Re-Running the Demo

To reset and run the demo again:

```bash
# Delete the fixed app
ibmcloud ce application delete --name faulty-api --force

# Re-deploy with the bugs
ibmcloud ce application create \
  --name faulty-api \
  --image icr.io/my-demo-namespace/faulty-api:demo \
  --port 3000 \
  --min-scale 1

# Run the demo again!
```

---

## What This Demo Proves

| Capability | How It's Demonstrated |
|------------|----------------------|
| **Autonomous error detection** | Agent finds app is broken without being told what's wrong |
| **Multi-signal diagnosis** | Combines status API + instance data + log parsing |
| **Targeted remediation** | Applies minimum change needed (patch port + set env var) |
| **Verification loop** | Confirms fix worked before declaring success |
| **Natural language interface** | Plain English prompts drive IBM Cloud API calls |
| **Zero-touch ops** | Human provides intent; agent handles all API interactions |
