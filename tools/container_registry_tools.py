"""
container_registry_tools.py — IBM Container Registry (ICR) ADK Tools
======================================================================
These tools let a platform engineering agent manage container images
in IBM Container Registry — the private registry for storing and
distributing container images used by Code Engine, ROKS, and IKS.

What ICR does:
  - Stores private Docker/OCI container images
  - Scans images for CVE vulnerabilities (Vulnerability Advisor)
  - Controls image access via IAM namespaces
  - Enforces content trust / image signing policies

Available tools:
  1. list_registry_namespaces      — List all ICR namespaces
  2. list_images                   — List images in a namespace
  3. get_image_vulnerabilities     — Get CVE scan results for an image
  4. get_registry_quota            — Check storage & pull traffic quotas
  5. delete_image                  — Remove a specific image tag
  6. list_retention_policies       — List image retention policies
  7. set_retention_policy          — Set how many image versions to keep
  8. get_registry_config           — Get account-level registry settings
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ibm_auth import auth_headers, get_region

load_dotenv()

REGION = get_region()

# ICR uses region-specific hostnames
ICR_REGISTRY_HOSTS = {
    "us-south": "us.icr.io",
    "us-east": "us.icr.io",
    "eu-de": "de.icr.io",
    "eu-gb": "uk.icr.io",