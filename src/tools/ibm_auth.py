"""
ibm_auth.py — Shared IBM Cloud IAM authentication helper.

Reads IBM_CLOUD_API_KEY from the environment (injected by the Orchestrate
connection at tool runtime). No key is ever hardcoded or passed in chat.
"""
import os
import time
import requests

_cache: dict = {"token": None, "expires_at": 0.0}


def get_iam_token() -> str:
    """Exchange IBM_CLOUD_API_KEY for a Bearer token, caching for 50 min."""
    if _cache["token"] and time.time() < _cache["expires_at"]:
        return _cache["token"]

    api_key = os.environ.get("IBMCLOUD_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "IBMCLOUD_API_KEY is not set. "
            "Run deploy.sh to register the connection — credentials are never passed in chat."
        )

    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"IAM token request failed {resp.status_code}: {resp.text}")

    data = resp.json()
    _cache["token"] = data["access_token"]
    _cache["expires_at"] = time.time() + 3000  # refresh 10 min before 60-min expiry
    return _cache["token"]


def auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {get_iam_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def region() -> str:
    return os.environ.get("IBMCLOUD_REGION", "us-south")


def ce_project_id() -> str:
    """Code Engine project ID from env — set in .env."""
    return os.environ.get("CODE_ENGINE_PROJECT_ID", "")


def logs_instance_guid() -> str:
    return os.environ.get("CLOUD_LOGS_INSTANCE_GUID", "")


def logs_region() -> str:
    return os.environ.get("CLOUD_LOGS_REGION", region())
