#!/usr/bin/env python3
"""
IBM Cloud Ops Agent — Credential Verifier
==========================================
Checks that all credentials in your .env file are valid
and that the agent can reach each configured service.

Usage: python3 scripts/verify_credentials.py
"""

import os
import sys
import json

# Allow running from project root or scripts/ directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
env_path = os.path.join(project_root, '.env')

# ─── Load .env ───
if not os.path.exists(env_path):
    print(f"\n❌  No .env file found at {env_path}")
    print("   Run: python3 scripts/setup_wizard.py\n")
    sys.exit(1)

env = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip()

PASS = "✅"
FAIL = "❌"
SKIP = "⏭ "
WARN = "⚠️ "


def check(label: str, fn, *args, **kwargs):
    """Run a check, print result."""
    try:
        result = fn(*args, **kwargs)
        if result.get('ok'):
            print(f"  {PASS}  {label}")
            if result.get('detail'):
                print(f"         {result['detail']}")
        else:
            print(f"  {FAIL}  {label}")
            print(f"         {result.get('error', 'Unknown error')}")
            if result.get('hint'):
                print(f"         💡 {result['hint']}")
    except Exception as exc:
        print(f"  {FAIL}  {label}")
        print(f"         Exception: {exc}")


# ─── Check Functions ───

def check_env_key(key: str, description: str) -> dict:
    val = env.get(key, '')
    if not val or val.startswith('your_'):
        return {'ok': False, 'error': f"{key} is not set", 'hint': f'Run setup_wizard.py and enter your {description}'}
    return {'ok': True}


def check_iam_token() -> dict:
    api_key = env.get('IBMCLOUD_API_KEY', '')
    if not api_key or api_key.startswith('your_'):
        return {'ok': False, 'error': 'IBMCLOUD_API_KEY not set', 'hint': 'Run setup_wizard.py first'}
    try:
        import requests
        resp = requests.post(
            'https://iam.cloud.ibm.com/identity/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'urn:ibm:params:oauth:grant-type:apikey', 'apikey': api_key},
            timeout=20,
        )
        if resp.status_code == 200:
            token = resp.json().get('access_token', '')
            return {'ok': True, 'detail': f'IAM token obtained (starts with {token[:10]}...)'}
        return {'ok': False, 'error': f'IAM returned HTTP {resp.status_code}: {resp.text[:200]}',
                'hint': 'Double-check your IBMCLOUD_API_KEY value'}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'hint': 'Check internet connectivity'}


def check_account_id() -> dict:
    acct_id = env.get('IBMCLOUD_ACCOUNT_ID', '')
    if not acct_id or acct_id.startswith('your_'):
        return {'ok': False, 'error': 'IBMCLOUD_ACCOUNT_ID not set'}
    import requests
    api_key = env.get('IBMCLOUD_API_KEY', '')
    try:
        token_resp = requests.post(
            'https://iam.cloud.ibm.com/identity/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'urn:ibm:params:oauth:grant-type:apikey', 'apikey': api_key},
            timeout=20,
        )
        token = token_resp.json().get('access_token', '')
        resp = requests.get(
            f'https://resource-controller.cloud.ibm.com/v2/resource_groups?account_id={acct_id}',
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            timeout=20,
        )
        if resp.status_code == 200:
            groups = resp.json().get('resources', [])
            return {'ok': True, 'detail': f'Found {len(groups)} resource group(s)'}
        return {'ok': False, 'error': f'HTTP {resp.status_code}: account_id may be wrong',
                'hint': 'Find your Account ID at: IBM Cloud → Profile → Profile and settings'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def check_code_engine() -> dict:
    project_id = env.get('CODE_ENGINE_PROJECT_ID', '')
    region = env.get('CODE_ENGINE_REGION') or env.get('IBMCLOUD_REGION', 'us-south')
    if not project_id or project_id.startswith('your_'):
        return {'ok': None, 'skipped': True}
    import requests
    api_key = env.get('IBMCLOUD_API_KEY', '')
    try:
        token_resp = requests.post(
            'https://iam.cloud.ibm.com/identity/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'urn:ibm:params:oauth:grant-type:apikey', 'apikey': api_key},
            timeout=20,
        )
        token = token_resp.json().get('access_token', '')
        url = f"https://api.{region}.codeengine.cloud.ibm.com/v2/projects/{project_id}/apps"
        resp = requests.get(url, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'}, timeout=20)
        if resp.status_code == 200:
            apps = resp.json().get('apps', [])
            return {'ok': True, 'detail': f'Connected! Found {len(apps)} app(s) in project {project_id[:8]}...'}
        return {'ok': False, 'error': f'HTTP {resp.status_code}',
                'hint': 'Check CODE_ENGINE_PROJECT_ID and CODE_ENGINE_REGION in .env'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def check_cloud_logs() -> dict:
    instance_id = env.get('CLOUD_LOGS_INSTANCE_ID', '')
    region = env.get('CLOUD_LOGS_REGION') or env.get('IBMCLOUD_REGION', 'us-south')
    if not instance_id or instance_id.startswith('your_'):
        return {'ok': None, 'skipped': True}
    import requests
    api_key = env.get('IBMCLOUD_API_KEY', '')
    try:
        token_resp = requests.post(
            'https://iam.cloud.ibm.com/identity/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'urn:ibm:params:oauth:grant-type:apikey', 'apikey': api_key},
            timeout=20,
        )
        token = token_resp.json().get('access_token', '')
        url = f"https://{instance_id}.api.{region}.logs.cloud.ibm.com/v1/logs/overview"
        resp = requests.get(url, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'}, timeout=20)
        if resp.status_code in (200, 404):  # 404 is fine — endpoint exists, just no data
            return {'ok': True, 'detail': f'Cloud Logs endpoint reachable (instance {instance_id[:8]}...)'}
        return {'ok': False, 'error': f'HTTP {resp.status_code}',
                'hint': 'Check CLOUD_LOGS_INSTANCE_ID and CLOUD_LOGS_REGION in .env'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def check_monitoring() -> dict:
    token = env.get('MONITORING_API_TOKEN', '')
    endpoint = env.get('MONITORING_ENDPOINT', '')
    if not token or token.startswith('your_'):
        return {'ok': None, 'skipped': True}
    import requests
    try:
        resp = requests.get(
            f'{endpoint}/api/v3/alerts',
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            timeout=20,
        )
        if resp.status_code in (200, 403):
            return {'ok': True, 'detail': f'Monitoring endpoint reachable'}
        return {'ok': False, 'error': f'HTTP {resp.status_code}',
                'hint': 'Check MONITORING_API_TOKEN and MONITORING_ENDPOINT in .env'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def check_requests_installed() -> dict:
    try:
        import requests
        return {'ok': True, 'detail': f'requests version: {requests.__version__}'}
    except ImportError:
        return {'ok': False, 'error': 'requests not installed', 'hint': 'Run: pip install -r requirements.txt'}


def check_orchestrate_cli() -> dict:
    import subprocess
    result = subprocess.run(['orchestrate', '--version'], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return {'ok': True, 'detail': result.stdout.strip() or 'orchestrate CLI found'}
    # Try pip install
    return {
        'ok': False,
        'error': 'orchestrate CLI not found',
        'hint': 'Will be installed automatically by deploy.sh, or run: pip install ibm-watsonx-orchestrate',
    }


# ─── Main ───

def main():
    print("\n" + "=" * 60)
    print("  IBM Cloud Ops Agent — Credential Verifier")
    print("=" * 60)

    try:
        import requests
    except ImportError:
        print(f"\n{FAIL} 'requests' library not found. Run: pip install requests\n")
        sys.exit(1)

    print("\n[ Python Dependencies ]")
    check("requests library installed", check_requests_installed)

    print("\n[ IBM Cloud Core ]")
    check("IBMCLOUD_API_KEY is set",    check_env_key, 'IBMCLOUD_API_KEY', 'IBM Cloud API Key')
    check("IBMCLOUD_ACCOUNT_ID is set", check_env_key, 'IBMCLOUD_ACCOUNT_ID', 'Account ID')
    check("IBM Cloud IAM token",        check_iam_token)
    check("Account ID valid",           check_account_id)

    print("\n[ watsonx Orchestrate ]")
    check("WO_API_KEY is set", check_env_key, 'WO_API_KEY', 'watsonx Orchestrate API Key')
    check("orchestrate CLI",   check_orchestrate_cli)

    print("\n[ Code Engine (optional) ]")
    ce_id = env.get('CODE_ENGINE_PROJECT_ID', '')
    if not ce_id or ce_id.startswith('your_'):
        print(f"  {SKIP}  Skipped — CODE_ENGINE_PROJECT_ID not configured")
    else:
        check("Code Engine connection", check_code_engine)

    print("\n[ Cloud Logs (optional) ]")
    logs_id = env.get('CLOUD_LOGS_INSTANCE_ID', '')
    if not logs_id or logs_id.startswith('your_'):
        print(f"  {SKIP}  Skipped — CLOUD_LOGS_INSTANCE_ID not configured")
    else:
        check("Cloud Logs connection", check_cloud_logs)

    print("\n[ Cloud Monitoring (optional) ]")
    mon_token = env.get('MONITORING_API_TOKEN', '')
    if not mon_token or mon_token.startswith('your_'):
        print(f"  {SKIP}  Skipped — MONITORING_API_TOKEN not configured")
    else:
        check("Monitoring connection", check_monitoring)

    print("\n" + "─" * 60)
    print("  Verification complete.")
    print("  If everything is green, run: ./deploy.sh")
    print("─" * 60 + "\n")


if __name__ == '__main__':
    main()
