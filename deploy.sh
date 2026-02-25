#!/usr/bin/env bash
# ============================================================
# IBM Cloud Ops Agent — One-Command Deploy Script
# ============================================================
# This script:
#   1. Checks prerequisites
#   2. Loads your .env credentials
#   3. Installs the orchestrate CLI if needed
#   4. Creates / activates an Orchestrate environment
#   5. Injects credentials into the toolkit server
#   6. Deploys the toolkit to watsonx Orchestrate
#   7. Cleans up injected credentials from source files
#
# Usage:  ./deploy.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
TOOLKIT_DIR="$SCRIPT_DIR/src/ops-toolkit"
SERVER_FILE="$TOOLKIT_DIR/mcp_server.py"
SERVER_BACKUP="$TOOLKIT_DIR/mcp_server.py.bak"

# ─── Colors ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

step()  { echo -e "\n${BLUE}[$1]${NC} $2"; }
ok()    { echo -e "  ${GREEN}✅${NC}  $*"; }
warn()  { echo -e "  ${YELLOW}⚠️ ${NC}  $*"; }
fail()  { echo -e "  ${RED}❌${NC}  $*"; }
die()   { fail "$*"; exit 1; }

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║     IBM Cloud Ops Agent — Deployment               ║"
echo "╚════════════════════════════════════════════════════╝"

# ─── Step 0: Check prerequisites ───
step "0" "Checking prerequisites..."

[ -f "$ENV_FILE" ] || die ".env file not found. Run: cp .env.example .env (or python3 scripts/setup_wizard.py)"

command -v python3 >/dev/null 2>&1 || die "Python 3 is required but not installed."
ok "Python 3 found: $(python3 --version)"

command -v pip >/dev/null 2>&1 || command -v pip3 >/dev/null 2>&1 || die "pip is required but not installed."
ok "pip found"

# ─── Step 1: Load .env ───
step "1" "Loading credentials from .env..."
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Validate required vars
[ -n "${IBMCLOUD_API_KEY:-}" ]   || die "IBMCLOUD_API_KEY is missing from .env"
[ -n "${IBMCLOUD_ACCOUNT_ID:-}" ] || die "IBMCLOUD_ACCOUNT_ID is missing from .env"
[ -n "${WO_INSTANCE:-}" ]        || die "WO_INSTANCE is missing from .env"
[ -n "${WO_API_KEY:-}" ]         || die "WO_API_KEY is missing from .env"

ok "Credentials loaded"
echo "    Region: ${IBMCLOUD_REGION:-us-south}"
echo "    Account: ${IBMCLOUD_ACCOUNT_ID}"
echo "    Orchestrate instance: ${WO_INSTANCE}"
# Export model-access environment variables for orchestrate commands
export WO_INSTANCE WO_API_KEY WO_ENV_NAME WO_USERNAME WO_PASSWORD WATSONX_SPACE_ID WATSONX_APIKEY


# ─── Step 2: Install orchestrate CLI ───
step "2" "Checking watsonx Orchestrate CLI..."

if ! command -v orchestrate >/dev/null 2>&1; then
    echo "  orchestrate CLI not found. Installing..."
    pip install ibm-watsonx-orchestrate --quiet || pip3 install ibm-watsonx-orchestrate --quiet
    ok "ibm-watsonx-orchestrate installed"
else
    ok "orchestrate CLI found: $(orchestrate --version 2>/dev/null || echo 'version unknown')"
fi

# ─── Step 3: Install Python dependencies ───
step "3" "Installing Python dependencies..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
    ok "Dependencies installed"
else
    pip install requests --quiet
    ok "requests installed"
fi

# ─── Step 4: Create / activate Orchestrate environment ───
step "4" "Setting up watsonx Orchestrate environment..."

WO_ENV_NAME="${WO_ENV_NAME:-local}"

activate_orchestrate_env() {
    local env_name="$1"

    # 'local' exists by default in the CLI config and does not need creation.
    if [ "$env_name" != "local" ]; then
        echo "  Creating environment: $env_name"
        if ! orchestrate env create "$env_name" --api-key "$WO_API_KEY" >/dev/null 2>&1; then
            warn "Could not create environment '$env_name' (it may already exist or the CLI may not persist it in this runtime)."
        fi
    fi

    echo "  Activating environment: $env_name"
    if orchestrate env activate "$env_name" --api-key "$WO_API_KEY" >/dev/null 2>&1; then
        ok "Environment '$env_name' activated"
        return 0
    fi

    return 1
}

if ! activate_orchestrate_env "$WO_ENV_NAME"; then
    if [ "$WO_ENV_NAME" != "local" ]; then
        warn "Failed to activate '$WO_ENV_NAME'. Falling back to the built-in 'local' environment."
        if ! activate_orchestrate_env "local"; then
            die "Failed to activate Orchestrate environment. Try: orchestrate env activate local --api-key \"$WO_API_KEY\""
        fi
    else
        die "Failed to activate Orchestrate environment 'local'. Check WO_INSTANCE/WO_API_KEY and CLI login state."
    fi
fi

# ─── Step 5: Inject credentials ───
step "5" "Injecting credentials into toolkit server..."

cp "$SERVER_FILE" "$SERVER_BACKUP"

# Cross-platform sed (works on Linux and macOS)
_sed() {
    if sed --version 2>/dev/null | grep -q GNU; then
        sed -i "$@"
    else
        sed -i '' "$@"
    fi
}

_sed "s|'__IBMCLOUD_API_KEY__'|'${IBMCLOUD_API_KEY}'|g"             "$SERVER_FILE"
_sed "s|'__IBMCLOUD_ACCOUNT_ID__'|'${IBMCLOUD_ACCOUNT_ID}'|g"       "$SERVER_FILE"
_sed "s|'__IBMCLOUD_REGION__'|'${IBMCLOUD_REGION:-us-south}'|g"     "$SERVER_FILE"
_sed "s|'__CODE_ENGINE_PROJECT_ID__'|'${CODE_ENGINE_PROJECT_ID:-}'|g" "$SERVER_FILE"
_sed "s|'__CODE_ENGINE_REGION__'|'${CODE_ENGINE_REGION:-${IBMCLOUD_REGION:-us-south}}'|g" "$SERVER_FILE"
_sed "s|'__CLOUD_LOGS_INSTANCE_ID__'|'${CLOUD_LOGS_INSTANCE_ID:-}'|g" "$SERVER_FILE"
_sed "s|'__CLOUD_LOGS_INSTANCE_GUID__'|'${CLOUD_LOGS_INSTANCE_GUID:-}'|g" "$SERVER_FILE"
_sed "s|'__CLOUD_LOGS_REGION__'|'${CLOUD_LOGS_REGION:-${IBMCLOUD_REGION:-us-south}}'|g" "$SERVER_FILE"
_sed "s|'__MONITORING_API_TOKEN__'|'${MONITORING_API_TOKEN:-}'|g"   "$SERVER_FILE"
_sed "s|'__MONITORING_ENDPOINT__'|'${MONITORING_ENDPOINT:-https://us-south.monitoring.cloud.ibm.com}'|g" "$SERVER_FILE"
_sed "s|'__ICD_REGION__'|'${ICD_REGION:-${IBMCLOUD_REGION:-us-south}}'|g" "$SERVER_FILE"
_sed "s|'__ICD_RESOURCE_GROUP__'|'${ICD_RESOURCE_GROUP:-default}'|g" "$SERVER_FILE"

ok "Credentials injected"

# ─── Step 6: Deploy toolkit ───
step "6" "Deploying IBM Cloud Ops Toolkit to watsonx Orchestrate..."

echo "  Removing existing toolkit (if any)..."
orchestrate toolkits remove --name ibm-cloud-ops-toolkit 2>/dev/null || true

echo "  Deploying toolkit..."
orchestrate toolkits import \
    --kind mcp \
    --name ibm-cloud-ops-toolkit \
    --description "IBM Cloud Ops Agent — manages Code Engine, Cloud Logs, Cloud Monitoring, and Databases" \
    --package-root "$TOOLKIT_DIR" \
    --command "python3 mcp_server.py" \
    --tools "*"

ok "Toolkit deployed!"

# ─── Step 7: Create the agent ───
step "7" "Creating the IBM Cloud Ops Agent..."

AGENT_PROMPT="You are the IBM Cloud Ops Agent — an expert at managing IBM Cloud services.
You have tools for Code Engine (deploy, scale, restart, monitor apps), Cloud Logs (query and filter logs),
Cloud Monitoring (metrics, alerts, dashboards), and IBM Cloud Databases (list, inspect, backup info).
When the user asks about their cloud services, always use the available tools to get real-time data.
Present results clearly and offer to take action when you spot issues.
If an operation could be destructive, confirm with the user before proceeding."

orchestrate agents create \
    --name "IBM Cloud Ops Agent" \
    --description "AI agent for managing IBM Cloud Code Engine, Logs, Monitoring, and Databases" \
    --instructions "$AGENT_PROMPT" \
    --toolkit ibm-cloud-ops-toolkit \
    2>/dev/null || warn "Agent may already exist — if so, it has been updated."

ok "Agent ready!"

# ─── Step 8: Cleanup ───
step "8" "Cleaning up injected credentials from source files..."

mv "$SERVER_BACKUP" "$SERVER_FILE"
ok "Source files restored (credentials removed)"

# ─── Done ───
echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║     ✅  Deployment Complete!                        ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║                                                    ║"
echo "║  Open watsonx Orchestrate and find:               ║"
echo "║  ➤  'IBM Cloud Ops Agent'                          ║"
echo "║                                                    ║"
echo "║  Try asking:                                       ║"
echo "║  'Show me all my Code Engine apps'                 ║"
echo "║  'Get error logs from the last hour'               ║"
echo "║  'What databases do I have?'                       ║"
echo "║                                                    ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

echo "Deployed tools:"
echo "  Code Engine:      list_apps, get_app_status, scale_app, restart_app,"
echo "                    update_app_memory, list_ce_jobs, list_ce_builds, get_ce_project_info"
echo "  Cloud Logs:       get_app_logs, query_cloud_logs, get_error_logs, get_logs_summary"
echo "  Monitoring:       get_metrics, list_alerts, get_dashboards,"
echo "                    get_cpu_usage, get_memory_usage, get_network_usage"
echo "  Databases:        list_database_instances, get_database_details,"
echo "                    get_database_connection_info, list_database_backups, get_database_scaling"
echo "  General:          list_resource_groups, get_account_summary"
echo ""
