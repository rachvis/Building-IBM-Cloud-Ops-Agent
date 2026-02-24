# Troubleshooting — IBM Cloud Ops Agent

## Quick Diagnosis

First, run the credential checker:
```bash
python3 scripts/verify_credentials.py
```

This will catch 80% of issues automatically.

---

## Common Issues

### "Authentication failed" / IAM Token Error

**Symptom:** Tools return `Failed to get IAM token`

**Cause:** `IBMCLOUD_API_KEY` is wrong or expired.

**Fix:**
1. Go to IBM Cloud → Profile icon → "IBM Cloud API keys"
2. Check if your key still exists (it may have been deleted or expired)
3. Create a new key, copy it, and update `.env`
4. Re-run `./deploy.sh`

---

### "orchestrate command not found"

**Symptom:** `deploy.sh` fails saying orchestrate is not installed.

**Fix:**
```bash
pip install ibm-watsonx-orchestrate
# or
pip3 install ibm-watsonx-orchestrate
```

Then re-run `./deploy.sh`.

---

### "Tool not found in agent"

**Symptom:** The agent says it doesn't know a tool.

**Fix:** Re-deploy the toolkit:
```bash
./deploy.sh
```

---

### "Code Engine: HTTP 404"

**Symptom:** Code Engine tools return HTTP 404.

**Cause:** Wrong `CODE_ENGINE_PROJECT_ID` or `CODE_ENGINE_REGION`.

**Fix:**
1. Go to [cloud.ibm.com/codeengine/projects](https://cloud.ibm.com/codeengine/projects)
2. Click your project
3. Copy the exact **Project ID** from the page
4. Check the region in the URL or project details
5. Update `.env` and re-run `./deploy.sh`

---

### "Cloud Logs: No entries returned"

**Symptom:** Log queries return 0 results.

**Possible causes:**
- No logs in the selected time window — try a wider window (increase `hours`)
- Wrong `CLOUD_LOGS_INSTANCE_ID` — verify it matches your instance's GUID exactly
- Wrong region — make sure `CLOUD_LOGS_REGION` matches where your Logs instance is deployed

---

### "Monitoring: 403 Forbidden"

**Symptom:** Monitoring tools return HTTP 403.

**Fix:**
1. Go to your Monitoring instance → Service credentials
2. Make sure the credential role is `Manager` or `Writer`
3. Copy the **Sysdig Monitor API Token** (not the IAM key)
4. Update `MONITORING_API_TOKEN` in `.env` and re-run `./deploy.sh`

---

### "Permission denied: ./deploy.sh"

**Symptom:** Can't execute `deploy.sh`

**Fix:**
```bash
chmod +x deploy.sh
./deploy.sh
```

---

### "sed: illegal option" on macOS

**Symptom:** `deploy.sh` fails with a `sed` error on macOS.

The deploy script auto-detects your OS and uses the correct `sed` syntax. If you still see this:
```bash
brew install gnu-sed
# Then open deploy.sh and change `sed` to `gsed`
```

---

### Databases show 0 results

**Symptom:** `list_database_instances` returns empty list.

**Fix:**
1. Make sure your databases are in the same account
2. Check that `ICD_RESOURCE_GROUP` matches where your databases live
3. The resource controller API requires IAM token with `Viewer` role on the resource group

---

## Getting Help

1. Run the verifier: `python3 scripts/verify_credentials.py`
2. Check that your `.env` has no trailing spaces or quote marks around values
3. Make sure you haven't accidentally committed or edited `.env` with placeholder values

If an issue persists, open a GitHub issue with:
- The exact error message
- Which step failed
- Output from `python3 scripts/verify_credentials.py` (with any API keys redacted)
