# IBM Cloud Ops Agent for watsonx Orchestrate

An autonomous IBM Cloud operations agent built with the watsonx Orchestrate ADK. Talk to your IBM Cloud account in plain English — the agent calls the right APIs and acts on your behalf.

> "Check the health of my Code Engine apps and fix anything broken."  
> "Show me all error logs from the last hour."  
> "Scale my PostgreSQL database to 8 GB memory."

**No credentials in chat. No API keys at runtime. Run `./deploy.sh` once — it works.**

---

## Demo Video

[![Demo preview](docs/demo-preview.png)](https://github.com/rachvis/Building-IBM-Cloud-Ops-Agent)

---

## How It Works

```
You (plain English)
      │
      ▼
watsonx Orchestrate
      │   looks up ibmcloud_creds connection
      │   (registered by deploy.sh — never asked in chat)
      ▼
Python tool function runs inside Orchestrate runtime
      │
      │  IBM Cloud IAM → Bearer token
      │  requests.get / post / patch
      ▼
IBM Cloud REST APIs
  ├── Code Engine      api.<region>.codeengine.cloud.ibm.com
  ├── Cloud Logs       <guid>.api.<region>.logs.cloud.ibm.com
  ├── Cloud Monitoring <region>.monitoring.cloud.ibm.com
  └── IBM Cloud Databases  api.<region>.databases.cloud.ibm.com
```

Tools are plain Python functions decorated with `@tool`. They run inside Orchestrate's own runtime — no external server needed. Credentials are stored in a **team connection** (`ibmcloud_creds`) that is registered once by `deploy.sh`. The agent reads them automatically; users are never prompted.

---

## Repository Structure

```
Building-IBM-Cloud-Ops-Agent/
│
├── src/tools/
│   ├── ibm_auth.py               ← Shared IAM auth (reads from ibmcloud_creds connection)
│   ├── code_engine_tools.py      ← 15 tools: list, diagnose, fix Code Engine apps & jobs
│   ├── cloud_logs_tools.py       ←  6 tools: search, tail, filter, count errors
│   ├── cloud_monitoring_tools.py ←  6 tools: metrics, alerts, dashboards
│   ├── databases_tools.py        ←  8 tools: list, backup, scale, connection strings
│   └── requirements.txt          ← Tool runtime dependencies
│
├── agents/
│   └── ibm_cloud_ops_agent.yaml  ← Agent definition (system prompt + tool list)
│
├── docs/
│   └── demo-preview.png
│
├── deploy.sh                     ← One script: credentials → tools → agent
├── .env.example                  ← Copy to .env and fill in your values
├── .gitignore
├── requirements.txt              ← Local dev dependencies
└── README.md
```

---

## Prerequisites

| Requirement | Where to get it |
|---|---|
| IBM Cloud account | [cloud.ibm.com/registration](https://cloud.ibm.com/registration) |
| IBM Cloud API key | Console → Manage → Access (IAM) → API Keys → Create |
| watsonx Orchestrate instance | IBM Cloud Catalog → watsonx Orchestrate |
| Orchestrate API key | Orchestrate UI → avatar → Settings → API details → Generate API key |
| Python 3.11+ | [python.org](https://python.org) |

---

## Setup

### 1 — Clone the repo

```bash
git clone https://github.com/rachvis/Building-IBM-Cloud-Ops-Agent.git
cd Building-IBM-Cloud-Ops-Agent
```

### 2 — Install the ADK

```bash
pip install ibm-watsonx-orchestrate
```

### 3 — Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in these four required values:

```bash
IBMCLOUD_API_KEY=your-ibm-cloud-api-key
IBMCLOUD_REGION=us-south
ORCHESTRATE_INSTANCE_URL=https://your-instance.orchestrate.cloud.ibm.com
ORCHESTRATE_API_KEY=your-orchestrate-api-key
```

Where to find the Orchestrate values:  
Open your Orchestrate instance → click your **avatar** (top right) → **Settings** → **API details**

Optional — add these for specific services:

```bash
CODE_ENGINE_PROJECT_ID=       # your default Code Engine project ID
CLOUD_LOGS_INSTANCE_GUID=     # from: ibmcloud resource service-instance <name> --output json | grep guid
CLOUD_MONITORING_INSTANCE_GUID=
```

Getting GUIDs via IBM Cloud CLI:
```bash
# Install IBM Cloud CLI if needed
curl -fsSL https://clis.cloud.ibm.com/install/osx | sh
ibmcloud login --apikey $IBMCLOUD_API_KEY -r us-south

# Code Engine project ID
ibmcloud ce project list

# Cloud Logs GUID
ibmcloud resource service-instances --service-name logs
ibmcloud resource service-instance YOUR_LOGS_NAME --output json | grep '"guid"'

# Monitoring GUID
ibmcloud resource service-instances --service-name sysdig-monitor
ibmcloud resource service-instance YOUR_MONITOR_NAME --output json | grep '"guid"'
```

### 4 — Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

That's it. The script:
- Logs in to your Orchestrate instance
- Registers `ibmcloud_creds` as a **team connection** (your IBM Cloud API key and all service IDs are stored there — the agent reads them at runtime, they are never surfaced in chat)
- Imports all 35 tools
- Imports the agent

### 5 — Chat

Open watsonx Orchestrate and start talking to **IBM Cloud Ops Agent**:

```
"List all my Code Engine projects"
"Check the health of all my apps and fix anything broken"
"Show me error logs from the last hour"
"How many critical events in the last 30 minutes?"
"Scale my postgres-prod database to 8 GB memory"
"Create a backup of my Redis instance"
```

---

## Available Tools

### IBM Cloud Code Engine (15 tools)

| Tool | What it does |
|---|---|
| `list_code_engine_projects` | List all projects in the account |
| `list_code_engine_apps` | List apps in a project with health status |
| `get_app_details` | Full config: image, port, env vars, scaling |
| `get_app_instances` | Pod status, restart counts, crash-loop detection |
| `get_app_logs` | Recent stdout/stderr with error highlighting |
| `check_app_health` | **One-shot diagnosis**: status + crashes + logs + root-cause hints |
| `update_app_env_vars` | Set/update environment variables (triggers new revision) |
| `update_app` | Fix port, image, CPU, memory, or scaling |
| `restart_app` | Force a rolling restart |
| `create_app` | Deploy a new containerised app |
| `delete_app` | Delete an app and all revisions |
| `get_app_revisions` | Revision history — see what changed |
| `list_jobs` | List batch job definitions |
| `create_job_run` | Trigger a batch job run |
| `get_job_run_status` | Check job run progress |

### IBM Cloud Logs (6 tools)

| Tool | What it does |
|---|---|
| `list_log_instances` | List all Cloud Logs instances |
| `search_logs` | Search by text query and time window |
| `get_recent_logs` | Get the most recent log lines |
| `get_logs_by_severity` | Filter by debug / info / warning / error / critical |
| `count_errors` | Count errors and return a health label |
| `get_log_alerts` | List configured alert rules |

### IBM Cloud Monitoring (6 tools)

| Tool | What it does |
|---|---|
| `list_monitoring_instances` | List all monitoring instances |
| `query_metric` | Query CPU, memory, network or custom metrics |
| `get_platform_metrics` | Query platform metrics for a specific IBM service |
| `list_alerts` | List configured alert rules |
| `get_alert_events` | Get recent alert firings |
| `get_team_dashboards` | List available dashboards |

### IBM Cloud Databases (8 tools)

| Tool | What it does |
|---|---|
| `list_database_instances` | List all ICD instances (optional type filter) |
| `get_database_details` | Version, state, member info |
| `list_database_backups` | List available backups |
| `create_manual_backup` | Trigger an immediate backup |
| `get_connection_strings` | Host, port, TLS info (no passwords) |
| `scale_database` | Change memory, disk, or CPU allocation |
| `list_database_tasks` | Monitor ongoing operations |
| `get_database_whitelist` | View IP allowlist rules |

**Total: 35 tools across 4 IBM Cloud services**

---

## How Credentials Flow (Why Orchestrate Never Asks in Chat)

```
.env  ──────────────┐
                    │  deploy.sh runs once:
                    │  orchestrate connections set-credentials -a ibmcloud_creds
                    │       -e IBMCLOUD_API_KEY=...
                    │       -e CODE_ENGINE_PROJECT_ID=...
                    ▼
         Orchestrate team connection: ibmcloud_creds
                    │
         (stored securely — not surfaced to users)
                    │
         Tool runs at request time:
                    │  os.environ["IBMCLOUD_API_KEY"]  ← injected from connection
                    │  POST iam.cloud.ibm.com/identity/token  → Bearer token
                    │  GET  api.us-south.codeengine.cloud.ibm.com/v2/...
                    ▼
         JSON result returned to Orchestrate → natural language response to user
```

The `--type team` flag in the connection means **all users share the same credentials** — no per-user setup, no prompts in chat, no API key visible to anyone after `deploy.sh` runs.

---

## Adding a Custom Tool

### 1. Write the function

```python
# src/tools/my_tools.py
import os, sys, requests
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, region

@tool(permission=ToolPermission.READ_ONLY)
def get_my_resource(resource_id: str) -> dict:
    """Get details of a specific resource from My IBM Cloud Service.

    Args:
        resource_id: The ID of the resource to look up.
    """
    resp = requests.get(
        f"https://api.{region()}.myservice.cloud.ibm.com/v1/resources/{resource_id}",
        headers=auth_headers(),
        timeout=30,
    )
    if resp.status_code != 200:
        return {"error": f"{resp.status_code}: {resp.text}"}
    return resp.json()
```

### 2. Add it to `deploy.sh`

```bash
import_tool "${TOOL_DIR}/my_tools.py"
```

### 3. Add it to `agents/ibm_cloud_ops_agent.yaml`

```yaml
tools:
  - get_my_resource      # ← add here
```

### 4. Re-deploy

```bash
./deploy.sh
```

---

## Troubleshooting

**`orchestrate` command not found**
```bash
pip install ibm-watsonx-orchestrate
```

**`deploy.sh` fails at login**  
Verify your `ORCHESTRATE_INSTANCE_URL` and `ORCHESTRATE_API_KEY` in `.env`.  
The URL comes from: Orchestrate UI → avatar → Settings → API details → Service instance URL  
The API key from the same page → Generate API key.

**Agent asks for credentials in chat**  
This means `--type team` wasn't set on the connection. Re-run `./deploy.sh` — it reconfigures the connection correctly.

**Tool returns `IBMCLOUD_API_KEY is not set`**  
The connection wasn't linked to the tools at import time. Re-run `./deploy.sh` — it passes `--app-id ibmcloud_creds` on every `orchestrate tools import`.

**401 / 403 from IBM Cloud APIs**  
Your API key doesn't have IAM access to that service. Add a policy:  
IBM Cloud Console → Manage → Access (IAM) → Users → your user → Access policies → Add.

**Empty results from Code Engine / Logs / Monitoring**  
The optional GUIDs in `.env` may be missing. Add them and re-run `./deploy.sh`.  
Or ask the agent: *"List my Cloud Logs instances"* — it will discover GUIDs dynamically.

---

## Links

| | |
|---|---|
| watsonx Orchestrate ADK docs | https://developer.watson-orchestrate.ibm.com |
| IBM Cloud Code Engine | https://cloud.ibm.com/docs/codeengine |
| IBM Cloud Logs | https://cloud.ibm.com/docs/cloud-logs |
| IBM Cloud Monitoring | https://cloud.ibm.com/docs/monitoring |
| IBM Cloud Databases | https://cloud.ibm.com/docs/databases-for-postgresql |
| IBM Cloud IAM API keys | https://cloud.ibm.com/iam/apikeys |
