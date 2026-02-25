# IBM Cloud Ops Agent 🤖

An AI-powered operations agent built on **watsonx Orchestrate** that can manage **IBM Cloud Code Engine**, **IBM Cloud Logs**, **IBM Cloud Monitoring**, and **IBM Cloud Databases** — all from natural language commands.

---

## Architecture & Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         YOU (the operator)                          │
│              "Scale my app to 5 instances"                          │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    watsonx Orchestrate (on IBM Cloud)               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    IBM Cloud Ops Agent                        │   │
│  │  • Understands your intent                                   │   │
│  │  • Picks the right tool(s)                                   │   │
│  │  • Chains operations automatically                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────┬─────────────┬────────────────┬──────────────────┬────────────┘
       │             │                │                  │
       ▼             ▼                ▼                  ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────┐
│   Code   │  │  Cloud   │  │    Cloud     │  │   Databases   │
│  Engine  │  │   Logs   │  │  Monitoring  │  │   for Cloud   │
│          │  │          │  │  (Sysdig)    │  │  (PostgreSQL, │
│ • Scale  │  │ • Query  │  │              │  │   MongoDB,    │
│ • Deploy │  │ • Filter │  │ • Metrics    │  │   Redis, etc) │
│ • Restart│  │ • Export │  │ • Alerts     │  │               │
│ • Rebuild│  │          │  │ • Dashboards │  │ • List DBs    │
└──────────┘  └──────────┘  └──────────────┘  │ • Credentials │
                                               │ • Backups     │
                                               └───────────────┘
```

**How it works:**
1. You type a natural language command to the Orchestrate agent
2. The agent identifies which service(s) to call
3. The agent's MCP (Model Context Protocol) toolkit makes IBM Cloud REST API calls
4. Results come back in plain English

---

## What the Agent Can Do

| Service | Example Commands |
|---|---|
| **Code Engine** | "Scale my-app to 3 instances", "Restart the payments service", "Show me all apps in my project" |
| **Cloud Logs** | "Show errors in the last hour", "Query logs where severity is critical", "Get logs for my-app" |
| **Cloud Monitoring** | "Show CPU usage for my-app", "List active alerts", "What's the memory usage trend?" |
| **Databases** | "List all my database instances", "Show connection info for my-postgres-db", "List recent backups" |

---

## Prerequisites

Before you begin, make sure you have:

- [ ] An **IBM Cloud account** — [Sign up free](https://cloud.ibm.com/registration)
- [ ] A **watsonx Orchestrate** instance on IBM Cloud — [Get access](https://www.ibm.com/products/watsonx-orchestrate)
- [ ] **Python 3.9+** installed on your machine — `python3 --version`
- [ ] **pip** installed — `pip --version`
- [ ] Basic comfort with a terminal/command line

That's it! No IBM Cloud CLI required — everything uses REST APIs.

---

## Quick Start (5 Steps)

```bash
# 1. Clone this repo
git clone https://github.com/YOUR_USERNAME/ibm-cloud-ops-agent.git
cd ibm-cloud-ops-agent

# 2. Create your local env file
cp .env.example .env
# Then edit .env and add your real credential values

# 3. (Optional) use the interactive setup wizard instead of manual editing
python3 scripts/setup_wizard.py

# 4. Install dependencies
pip install -r requirements.txt

# 5. Test your credentials
python3 scripts/verify_credentials.py

# 6. Deploy the agent
./deploy.sh
```

Done! Open watsonx Orchestrate and talk to your agent.

---

## Step-by-Step Setup Guide

### Step 1: Get Your IBM Cloud API Key

1. Go to [IBM Cloud Console](https://cloud.ibm.com)
2. Click your **profile icon** (top right) → **"IBM Cloud API keys"**
3. Click **"Create an IBM Cloud API key"**
4. Give it a name like `ops-agent-key`
5. Click **Create**, then **Copy** the key immediately (you won't see it again!)

> 💡 **Keep this key safe** — it's like a password to your IBM Cloud account.

### Step 2: Get Your Account ID

1. In IBM Cloud, click your **profile icon** → **"Profile and settings"**
2. Your **Account ID** is shown at the top of the page — copy it

### Step 3: Get Your watsonx Orchestrate Credentials

1. Go to [IBM Cloud Catalog](https://cloud.ibm.com/catalog) and search for **watsonx Orchestrate**
2. If you have an existing instance:
   - Go to [Resource List](https://cloud.ibm.com/resources)
   - Find your Orchestrate instance under **AI / Machine Learning**
   - Click on it → go to **"Service credentials"** tab
   - Click **"New credential"** → name it `ops-agent-cred` → click **Add**
   - Expand the credential and copy the **`apikey`** value
3. Copy the **instance URL** from the **Manage** tab (looks like `https://api.us-south.watson-orchestrate.watson.cloud.ibm.com/instances/YOUR_INSTANCE_ID`)

### Step 4: Get Service-Specific Credentials

**For Code Engine:**
1. Go to [Code Engine](https://cloud.ibm.com/codeengine/projects) on IBM Cloud
2. Click on your project name
3. The **Project ID** is shown at the top — copy it
4. Note the **region** (e.g., `us-south`, `eu-de`)

**For Cloud Logs:**
1. Go to [Resource List](https://cloud.ibm.com/resources)
2. Find your **IBM Cloud Logs** instance
3. Click on it → **"Details"** panel shows the **Instance ID** (also called CRN)
4. The **GUID** is the part of the CRN after `::logs:`
5. Note the region (e.g., `us-south`)

**For Cloud Monitoring:**
1. Go to [Resource List](https://cloud.ibm.com/resources)
2. Find your **IBM Cloud Monitoring** instance (formerly Sysdig)
3. Click on it → **"Service credentials"** → click your credential
4. Copy the **`Sysdig Monitor API Token`** (also called `iam_apikey`)
5. Copy the **`Sysdig Endpoint`** value

**For IBM Cloud Databases:**
1. Go to [Resource List](https://cloud.ibm.com/resources)
2. Find your database instance (PostgreSQL, MongoDB, Redis, etc.)
3. Click on it → **"Service credentials"**
4. Click **"New credential"** → name it `ops-agent-cred`
5. Copy the entire JSON credential block

> 💡 You don't need ALL services. The agent works with whatever services you configure. Leave unused ones blank.

### Step 5: Configure Your Environment

Create your `.env` from `.env.example`, fill in your values, and then you can deploy with one script (`./deploy.sh`):

```bash
cp .env.example .env
# Then open .env in any text editor and fill in your values
```

If you prefer, you can still use the interactive wizard to generate `.env`:

```bash
python3 scripts/setup_wizard.py
```

### Step 6: Verify Everything Works

```bash
python3 scripts/verify_credentials.py
```

You'll see green checkmarks ✅ for connected services and red ✗ for any issues with instructions on how to fix them.

### Step 7: Deploy

```bash
./deploy.sh
```

This script:
1. Installs the `ibm-watsonx-orchestrate` CLI tool
2. Authenticates with your Orchestrate instance
3. Deploys the toolkit (all the tools the agent can use)
4. Creates the agent with a system prompt

---

## Using the Agent

Once deployed, open your watsonx Orchestrate workspace and you'll find **"IBM Cloud Ops Agent"** in your agents list.

Try these example commands:

```
# Code Engine
"Show me all apps in my Code Engine project"
"Scale payments-api to 5 instances"
"Restart the frontend app"
"What's the status of all my running apps?"

# Cloud Logs
"Show me error logs from the last 2 hours"
"Get logs for payments-api from today"
"Are there any critical errors right now?"

# Cloud Monitoring
"What's the CPU usage for my apps?"
"Show me memory metrics for the last hour"
"Are there any active alerts?"

# Databases
"List all my database instances"
"Show connection details for my postgres database"
"What databases do I have in us-south?"

# Multi-service
"My app seems slow — check logs and CPU metrics for payments-api"
"Scale my app to handle more load and show me the current metrics"
```

---

## File Structure

```
ibm-cloud-ops-agent/
├── README.md                    ← You are here
├── deploy.sh                    ← One-command deploy script
├── requirements.txt             ← Python dependencies
├── .env.example                 ← Template for your credentials
├── .gitignore                   ← Keeps secrets out of git
│
├── src/
│   └── ops-toolkit/
│       ├── mcp_server.py        ← Main agent toolkit (all tools)
│       ├── code_engine_tools.py ← Code Engine operations
│       ├── cloud_logs_tools.py  ← Cloud Logs operations
│       ├── monitoring_tools.py  ← Cloud Monitoring operations
│       └── databases_tools.py  ← IBM Cloud Databases operations
│
├── scripts/
│   ├── setup_wizard.py          ← Interactive credential setup
│   └── verify_credentials.py   ← Test all your credentials
│
└── docs/
    ├── CREDENTIALS_GUIDE.md     ← Detailed credential instructions
    ├── TOOLS_REFERENCE.md       ← All 28 tools documented
    └── TROUBLESHOOTING.md       ← Common issues & fixes
```

---

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues.

Quick checks:
- **"Authentication failed"** → Run `python3 scripts/verify_credentials.py` to identify which credential is wrong
- **"Tool not found"** → Re-run `./deploy.sh` to redeploy the toolkit
- **"Connection refused"** → Check that you're using the correct region in your `.env` file

---

## Contributing

PRs welcome! Please open an issue first to discuss major changes.

---

## License

MIT License — see [LICENSE](LICENSE)
