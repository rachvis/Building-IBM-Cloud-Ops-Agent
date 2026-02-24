# Credentials Guide — IBM Cloud Ops Agent

This guide walks you through finding every credential needed.
Each section includes step-by-step screenshots instructions.

---

## IBM Cloud API Key (`IBMCLOUD_API_KEY`)

**What it is:** A password-like token that lets the agent call IBM Cloud APIs on your behalf.

**How to get it:**
1. Go to [https://cloud.ibm.com](https://cloud.ibm.com) and log in
2. Click your **profile/avatar icon** in the top-right corner
3. Select **"IBM Cloud API keys"** from the dropdown
4. Click **"Create an IBM Cloud API key"** (blue button)
5. Enter a name: `ibm-cloud-ops-agent`
6. Click **Create**
7. ⚠️ **COPY THE KEY NOW** — it will never be shown again!
8. Paste it as `IBMCLOUD_API_KEY` in your `.env` file

> 🔒 Treat this like a password. It grants access to all your IBM Cloud resources.

---

## Account ID (`IBMCLOUD_ACCOUNT_ID`)

**What it is:** Your unique IBM Cloud account identifier.

**How to get it:**
1. In IBM Cloud, click your **profile icon**
2. Select **"Profile and settings"**
3. Your **Account ID** is shown at the top of the page (32-character string)
4. Copy it and paste as `IBMCLOUD_ACCOUNT_ID`

---

## watsonx Orchestrate API Key (`WO_API_KEY`)

**What it is:** The API key specific to your watsonx Orchestrate instance.

**How to get it:**
1. Go to [IBM Cloud Resource List](https://cloud.ibm.com/resources)
2. Expand **"AI / Machine Learning"**
3. Click on your **watsonx Orchestrate** instance
4. Click the **"Service credentials"** tab
5. Click **"New credential +"**
   - Name: `ops-agent-cred`
   - Role: `Manager`
6. Click **"Add"**
7. Expand the new credential entry
8. Copy the `apikey` value → paste as `WO_API_KEY`

---

## Code Engine Project ID (`CODE_ENGINE_PROJECT_ID`)

**What it is:** The unique ID of your Code Engine project.

**How to get it:**
1. Go to [Code Engine Projects](https://cloud.ibm.com/codeengine/projects)
2. Click on your project name
3. The **Project ID** is shown at the top of the project details page
4. Copy it → paste as `CODE_ENGINE_PROJECT_ID`

Also note the **region** shown on this page (e.g., `us-south`) → paste as `CODE_ENGINE_REGION`

---

## Cloud Logs Instance ID (`CLOUD_LOGS_INSTANCE_ID` / `CLOUD_LOGS_INSTANCE_GUID`)

**What it is:** The GUID of your IBM Cloud Logs instance.

**How to get it:**
1. Go to [IBM Cloud Resource List](https://cloud.ibm.com/resources)
2. Expand **"Logging and monitoring"**
3. Click on your **IBM Cloud Logs** instance
4. In the right panel, find **"GUID"** — this is a UUID like `a1b2c3d4-e5f6-...`
5. Copy it → paste as BOTH `CLOUD_LOGS_INSTANCE_ID` AND `CLOUD_LOGS_INSTANCE_GUID`

Also copy the **region** from the instance details → paste as `CLOUD_LOGS_REGION`

---

## Cloud Monitoring API Token (`MONITORING_API_TOKEN`)

**What it is:** The Sysdig API token for your IBM Cloud Monitoring instance.

**How to get it:**
1. Go to [IBM Cloud Resource List](https://cloud.ibm.com/resources)
2. Find your **IBM Cloud Monitoring** instance (may be listed as "Monitoring")
3. Click on it → go to **"Service credentials"** tab
4. Click **"New credential +"** if none exist → name it `ops-agent-cred`
5. Expand the credential
6. Copy **`Sysdig Monitor API Token`** → paste as `MONITORING_API_TOKEN`
7. Copy **`Sysdig Endpoint`** → paste as `MONITORING_ENDPOINT`
   - Looks like: `https://us-south.monitoring.cloud.ibm.com`

---

## IBM Cloud Databases

**How it works:** Databases integration uses your main `IBMCLOUD_API_KEY` — no extra token needed!

Just set:
- `ICD_REGION` = the region where your databases are (e.g., `us-south`)
- `ICD_RESOURCE_GROUP` = the resource group name (usually `default`)

The agent will automatically discover all your database instances (PostgreSQL, MongoDB, Redis, MySQL, Elasticsearch, etc.)

---

## Quick Credential Check

After filling in your `.env`, run:
```bash
python3 scripts/verify_credentials.py
```

This will test each credential and tell you exactly what's wrong if something fails.
