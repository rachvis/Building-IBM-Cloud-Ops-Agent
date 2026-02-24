#!/bin/bash
# =============================================================================
# deploy.sh — IBM Cloud Ops Agent — one-command deploy to watsonx Orchestrate
# =============================================================================
# What this script does:
#   1. Loads your credentials from .env
#   2. Logs in to your Orchestrate environment
#   3. Creates a team connection "ibmcloud_creds" and injects your IBM Cloud
#      API key + config — tools read this at runtime, never asked in chat
#   4. Imports all Python tools (Code Engine, Logs, Monitoring, Databases)
#   5. Imports the agent YAML
#
# Before running:
#   cp .env.example .env        # fill in all values
#   pip install ibm-watsonx-orchestrate
#   chmod +x deploy.sh
#   ./deploy.sh
# =============================================================================
set -euo pipefail

BOLD='\033[1m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

step()  { echo -e "\n${CYAN}▶  $1${NC}"; }
ok()    { echo -e "${GREEN}✅  $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️   $1${NC}"; }
fail()  { echo -e "${RED}❌  $1${NC}"; exit 1; }

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║     IBM Cloud Ops Agent  —  watsonx Orchestrate Deploy   ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Load .env ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    fail ".env not found. Copy .env.example to .env and fill in your values."
fi
set -a; source .env; set +a
ok ".env loaded"

# ─── Validate required variables ──────────────────────────────────────────────
REQUIRED_VARS=(
    IBMCLOUD_API_KEY
    IBMCLOUD_REGION
    ORCHESTRATE_INSTANCE_URL
    ORCHESTRATE_API_KEY
)
MISSING=0
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        warn "Missing required variable: $var"
        MISSING=1
    fi
done
[ $MISSING -eq 1 ] && fail "Fill in all required variables in .env and re-run."
ok "All required variables present"

# ─── Check orchestrate CLI ────────────────────────────────────────────────────
if ! command -v orchestrate &>/dev/null; then
    fail "orchestrate CLI not found. Install it with:\n  pip install ibm-watsonx-orchestrate"
fi
ok "orchestrate CLI found ($(orchestrate --version 2>/dev/null || echo 'version unknown'))"

# ─── Step 1: Login to Orchestrate ─────────────────────────────────────────────
step "Step 1/5 — Logging in to watsonx Orchestrate"

# Create or update the environment
orchestrate env add \
    --name ibmcloud_ops_env \
    --url "${ORCHESTRATE_INSTANCE_URL}" \
    --api-key "${ORCHESTRATE_API_KEY}" 2>/dev/null || true

orchestrate env activate ibmcloud_ops_env \
    --url "${ORCHESTRATE_INSTANCE_URL}" \
    --api-key "${ORCHESTRATE_API_KEY}"

ok "Logged in to ${ORCHESTRATE_INSTANCE_URL}"

# ─── Step 2: Register the IBM Cloud credential connection ─────────────────────
step "Step 2/5 — Registering IBM Cloud credentials as a team connection"

# Create the connection app (idempotent — ok if already exists)
orchestrate connections add -a ibmcloud_creds 2>/dev/null || true

orchestrate connections configure \
    -a ibmcloud_creds \
    --env draft \
    --type team \
    --kind key_value

# Inject all IBM Cloud vars from .env into the connection
# Tools read these at runtime — the agent NEVER asks the user for them in chat
CRED_ARGS=""
CRED_ARGS+=" -e IBMCLOUD_API_KEY=${IBMCLOUD_API_KEY}"
CRED_ARGS+=" -e IBMCLOUD_REGION=${IBMCLOUD_REGION:-us-south}"
CRED_ARGS+=" -e CODE_ENGINE_PROJECT_ID=${CODE_ENGINE_PROJECT_ID:-}"
CRED_ARGS+=" -e CLOUD_LOGS_INSTANCE_GUID=${CLOUD_LOGS_INSTANCE_GUID:-}"
CRED_ARGS+=" -e CLOUD_LOGS_REGION=${CLOUD_LOGS_REGION:-${IBMCLOUD_REGION:-us-south}}"
CRED_ARGS+=" -e CLOUD_MONITORING_INSTANCE_GUID=${CLOUD_MONITORING_INSTANCE_GUID:-}"

# shellcheck disable=SC2086
orchestrate connections set-credentials \
    -a ibmcloud_creds \
    --env draft \
    $CRED_ARGS

ok "ibmcloud_creds connection registered with all service credentials"

# ─── Step 3: Import Python tools ──────────────────────────────────────────────
step "Step 3/5 — Importing tools into Orchestrate"

TOOL_DIR="src/tools"
REQ_FILE="${TOOL_DIR}/requirements.txt"

import_tool() {
    local file="$1"
    local name="$(basename "$file" .py)"
    echo "    Importing ${name}..."
    orchestrate tools import \
        -k python \
        -f "${file}" \
        -p "${TOOL_DIR}" \
        -r "${REQ_FILE}" \
        --app-id ibmcloud_creds 2>&1 | tail -3
}

import_tool "${TOOL_DIR}/code_engine_tools.py"
import_tool "${TOOL_DIR}/cloud_logs_tools.py"
import_tool "${TOOL_DIR}/cloud_monitoring_tools.py"
import_tool "${TOOL_DIR}/databases_tools.py"

ok "All tools imported"

# ─── Step 4: Import the agent ─────────────────────────────────────────────────
step "Step 4/5 — Importing agent"

orchestrate agents import -f agents/ibm_cloud_ops_agent.yaml

ok "Agent 'ibm_cloud_ops_agent' imported"

# ─── Step 5: Verify ───────────────────────────────────────────────────────────
step "Step 5/5 — Verifying deployment"

echo ""
echo "  Tools deployed:"
orchestrate tools list 2>/dev/null | grep -E "(list_code_engine|get_app|check_app|update_app|search_logs|count_errors|query_metric|list_database)" | sed 's/^/    /' || true

echo ""
echo "  Agent deployed:"
orchestrate agents list 2>/dev/null | grep ibm_cloud_ops_agent | sed 's/^/    /' || true

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║   ✅  Deployment complete!                               ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "  Open watsonx Orchestrate and start chatting with your agent:"
echo ""
echo "  💬  \"List all my Code Engine projects\""
echo "  💬  \"Check the health of my apps and fix anything broken\""
echo "  💬  \"Show me error logs from the last hour\""
echo "  💬  \"What's the CPU usage of my monitoring instance?\""
echo "  💬  \"List my PostgreSQL databases\""
echo ""
echo "  To re-deploy after changes:  ./deploy.sh"
echo "  To remove the agent:         orchestrate agents delete ibm_cloud_ops_agent"
echo "  To remove all tools:         orchestrate tools delete --all"
echo ""
