# Tools Reference — IBM Cloud Ops Agent

All 25 tools available to the agent, organized by service.

---

## Code Engine Tools (8 tools)

### `list_apps`
Lists all applications in your Code Engine project.

**Parameters:** none (uses `CODE_ENGINE_PROJECT_ID` from `.env`)

**Example prompt:** "Show me all my Code Engine apps"

---

### `get_app_status`
Gets detailed status and configuration for a single app.

**Parameters:**
- `app_name` (required): Name of the Code Engine application

**Example prompt:** "What's the status of payments-api?"

---

### `scale_app`
Scales an app to a specific number of instances.

**Parameters:**
- `app_name` (required): Name of the app
- `instances` (required): Target number of instances (integer)

**Example prompt:** "Scale payments-api to 5 instances"

---

### `restart_app`
Restarts an application by triggering a new revision.

**Parameters:**
- `app_name` (required): Name of the app

**Example prompt:** "Restart the frontend app"

---

### `update_app_memory`
Updates the memory allocation for an app.

**Parameters:**
- `app_name` (required): Name of the app
- `memory` (required): Memory limit string, e.g. `512M`, `1G`, `2G`

**Example prompt:** "Give payments-api 2GB of memory"

---

### `list_ce_jobs`
Lists all Code Engine batch jobs in the project.

**Parameters:** none

**Example prompt:** "What batch jobs do I have?"

---

### `list_ce_builds`
Lists all Code Engine builds in the project.

**Parameters:** none

**Example prompt:** "Show me my build configurations"

---

### `get_ce_project_info`
Gets summary information about the Code Engine project.

**Parameters:** none

**Example prompt:** "Tell me about my Code Engine project"

---

## Cloud Logs Tools (4 tools)

### `get_app_logs`
Gets recent logs for a specific application.

**Parameters:**
- `app_name` (required): Name of the app
- `hours` (optional, default 1): How many hours back to look
- `severity` (optional): `debug`, `info`, `warning`, `error`, or `critical`

**Example prompt:** "Show me errors from payments-api in the last 2 hours"

---

### `query_cloud_logs`
Runs a custom DataPrime query against Cloud Logs.

**Parameters:**
- `query` (required): A DataPrime query string
- `hours` (optional, default 1): Time window

**Example prompts:**
- "Query logs where severity is critical"
- "Find logs containing 'timeout' in the last 3 hours"

**DataPrime examples:**
```
source logs | filter $l.severity >= 4 | limit 50
source logs | filter $d.message.contains("NullPointerException") | limit 20
source logs | filter $d.kubernetes.labels.app == "payments-api" | limit 100
```

---

### `get_error_logs`
Gets all error and critical severity logs across all services.

**Parameters:**
- `hours` (optional, default 1): How many hours back

**Example prompt:** "Are there any errors right now?"

---

### `get_logs_summary`
Gets a count of log entries grouped by severity level.

**Parameters:**
- `hours` (optional, default 1): Time window

**Example prompt:** "Give me a log summary for today"

---

## Cloud Monitoring Tools (6 tools)

### `get_metrics`
Gets any metric from IBM Cloud Monitoring.

**Parameters:**
- `metric_name` (required): e.g. `cpu.used.percent`, `memory.used.percent`
- `app_name` (optional): Filter by app name
- `minutes` (optional, default 60): Time window

---

### `get_cpu_usage`
Gets CPU usage percentage for an app or all apps.

**Parameters:**
- `app_name` (optional)
- `minutes` (optional, default 60)

**Example prompt:** "What's the CPU usage for payments-api?"

---

### `get_memory_usage`
Gets memory usage percentage for an app or all apps.

**Parameters:**
- `app_name` (optional)
- `minutes` (optional, default 60)

**Example prompt:** "How much memory is my app using?"

---

### `get_network_usage`
Gets network I/O metrics.

**Parameters:**
- `app_name` (optional)
- `minutes` (optional, default 60)

---

### `list_alerts`
Lists all currently configured monitoring alerts and their states.

**Parameters:** none

**Example prompt:** "Are there any active alerts I should know about?"

---

### `get_dashboards`
Lists all available monitoring dashboards.

**Parameters:** none

---

## IBM Cloud Databases Tools (5 tools)

### `list_database_instances`
Lists all IBM Cloud Database instances across all types (PostgreSQL, MongoDB, Redis, MySQL, etc.).

**Parameters:** none

**Example prompt:** "What databases do I have?"

---

### `get_database_details`
Gets detailed information about a specific database deployment.

**Parameters:**
- `deployment_id` (required): The CRN or ID from `list_database_instances`

**Example prompt:** "Tell me about my postgres database"

---

### `get_database_connection_info`
Gets connection strings and endpoint information for a database.

**Parameters:**
- `deployment_id` (required)

**Example prompt:** "How do I connect to my MongoDB instance?"

---

### `list_database_backups`
Lists available backups for a database.

**Parameters:**
- `deployment_id` (required)

**Example prompt:** "When was my postgres database last backed up?"

---

### `get_database_scaling`
Gets the current resource scaling (vCPU, memory, disk) for a database.

**Parameters:**
- `deployment_id` (required)

---

## General Tools (2 tools)

### `list_resource_groups`
Lists all resource groups in the IBM Cloud account.

**Parameters:** none

---

### `get_account_summary`
Gets a high-level count of all active resources by service type.

**Parameters:** none

**Example prompt:** "Give me an overview of what's running in my account"

---

## Multi-Service Example Prompts

```
"My payments-api is slow — check its logs and CPU for the last hour"
"Scale up frontend to handle more load and confirm the new instance count"
"Are there any errors or alerts I should know about right now?"
"List all my databases and show me the connection string for my postgres instance"
"What's the overall health of my Code Engine project?"
```
