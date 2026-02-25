#!/usr/bin/env python3
"""
IBM Cloud Ops Agent — Interactive Setup Wizard
===============================================
Run this script to be guided through setting up your .env file.
It will ask you for each credential and explain where to find it.

Usage: python3 scripts/setup_wizard.py
"""

import os
import sys


def print_header():
    print("\n" + "=" * 60)
    print("  IBM Cloud Ops Agent — Setup Wizard")
    print("=" * 60)
    print("\nThis wizard will help you configure your credentials.")
    print("You can press Enter to skip optional values.\n")


def ask(prompt: str, required: bool = True, default: str = '') -> str:
    suffix = ' (required)' if required else f' (optional, press Enter to skip)'
    while True:
        val = input(f"\n{prompt}{suffix}:\n> ").strip()
        if val:
            return val
        if not required:
            return default
        print("  ⚠  This field is required. Please enter a value.")


def print_instruction(text: str):
    print(f"\n  💡 {text}")


def confirm(prompt: str) -> bool:
    resp = input(f"\n{prompt} [y/N]: ").strip().lower()
    return resp in ('y', 'yes')


def main():
    print_header()

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    env_example_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.example')

    # Load existing values if .env exists
    existing = {}
    if os.path.exists(env_path):
        print(f"  Found existing .env file at: {env_path}")
        if not confirm("  Overwrite it with new values?"):
            print("  Exiting. Your .env file is unchanged.")
            sys.exit(0)
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    existing[k.strip()] = v.strip()

    values = dict(existing)

    # ─── IBM CLOUD CORE ───
    print("\n" + "─" * 50)
    print("STEP 1: IBM Cloud Core Credentials")
    print("─" * 50)

    print_instruction(
        "IBM Cloud API Key: go to cloud.ibm.com → click your profile icon (top right)\n"
        "  → 'IBM Cloud API keys' → 'Create an IBM Cloud API key' → copy the key."
    )
    values['IBMCLOUD_API_KEY'] = ask("IBM Cloud API Key", required=True)

    print_instruction(
        "Account ID: IBM Cloud → profile icon → 'Profile and settings'\n"
        "  → Account ID is shown at the top."
    )
    values['IBMCLOUD_ACCOUNT_ID'] = ask("IBM Cloud Account ID", required=True)

    print_instruction(
        "Region: the IBM Cloud region where your services are deployed.\n"
        "  Common values: us-south, us-east, eu-de, eu-gb, jp-tok, au-syd"
    )
    values['IBMCLOUD_REGION'] = ask("Primary IBM Cloud Region (default: us-south)", required=False, default='us-south') or 'us-south'

    # ─── WATSONX ORCHESTRATE ───
    print("\n" + "─" * 50)
    print("STEP 2: watsonx Orchestrate Credentials")
    print("─" * 50)

    print_instruction(
        "Orchestrate API Key: IBM Cloud → Resources → your Orchestrate instance\n"
        "  → 'Service credentials' tab → 'New credential' → expand it → copy 'apikey'."
    )
    print_instruction(
        "Orchestrate Instance URL: IBM Cloud → your Orchestrate instance → Manage tab\n"
        "  → copy the instance URL (contains /instances/<id>)."
    )
    values['WO_INSTANCE'] = ask("watsonx Orchestrate Instance URL", required=True)

    values['WO_API_KEY'] = ask("watsonx Orchestrate API Key", required=True)

    values['WO_ENV_NAME'] = ask("Orchestrate environment name (default: local)", required=False, default='local') or 'local'

    # ─── CODE ENGINE ───
    print("\n" + "─" * 50)
    print("STEP 3: Code Engine (optional)")
    print("─" * 50)

    if confirm("  Do you want to set up Code Engine integration?"):
        print_instruction(
            "Code Engine Project ID: IBM Cloud → Code Engine → click your project\n"
            "  → Project ID is shown at the top of the page."
        )
        values['CODE_ENGINE_PROJECT_ID'] = ask("Code Engine Project ID", required=False)
        values['CODE_ENGINE_REGION'] = ask("Code Engine Region (default: same as primary)", required=False, default=values.get('IBMCLOUD_REGION', 'us-south'))
    else:
        print("  Skipping Code Engine setup.")

    # ─── CLOUD LOGS ───
    print("\n" + "─" * 50)
    print("STEP 4: IBM Cloud Logs (optional)")
    print("─" * 50)

    if confirm("  Do you want to set up Cloud Logs integration?"):
        print_instruction(
            "Cloud Logs Instance ID (GUID): IBM Cloud → Resources → your Cloud Logs instance\n"
            "  → The 'Details' panel on the right shows 'GUID'. Copy that value."
        )
        values['CLOUD_LOGS_INSTANCE_ID'] = ask("Cloud Logs Instance ID / GUID", required=False)
        values['CLOUD_LOGS_INSTANCE_GUID'] = values.get('CLOUD_LOGS_INSTANCE_ID', '')
        values['CLOUD_LOGS_REGION'] = ask("Cloud Logs Region (default: same as primary)", required=False, default=values.get('IBMCLOUD_REGION', 'us-south'))
    else:
        print("  Skipping Cloud Logs setup.")

    # ─── MONITORING ───
    print("\n" + "─" * 50)
    print("STEP 5: IBM Cloud Monitoring (optional)")
    print("─" * 50)

    if confirm("  Do you want to set up Cloud Monitoring integration?"):
        print_instruction(
            "Monitoring API Token: IBM Cloud → Resources → your Cloud Monitoring instance\n"
            "  → 'Service credentials' tab → expand a credential → copy 'Sysdig Monitor API Token'."
        )
        values['MONITORING_API_TOKEN'] = ask("Monitoring API Token", required=False)
        print_instruction(
            "Monitoring Endpoint: same service credentials → 'Sysdig Endpoint'\n"
            "  Example: https://us-south.monitoring.cloud.ibm.com"
        )
        values['MONITORING_ENDPOINT'] = ask("Monitoring Endpoint URL", required=False, default='https://us-south.monitoring.cloud.ibm.com')
    else:
        print("  Skipping Monitoring setup.")

    # ─── DATABASES ───
    print("\n" + "─" * 50)
    print("STEP 6: IBM Cloud Databases (optional)")
    print("─" * 50)

    if confirm("  Do you want to set up IBM Cloud Databases integration?"):
        print_instruction(
            "The Databases integration uses your main IBM Cloud API Key.\n"
            "  Just confirm the region where your databases are deployed."
        )
        values['ICD_REGION'] = ask("Databases Region (default: same as primary)", required=False, default=values.get('IBMCLOUD_REGION', 'us-south'))
        values['ICD_RESOURCE_GROUP'] = ask("Resource Group name (default: default)", required=False, default='default')
    else:
        print("  Skipping Databases setup.")

    # ─── WRITE .env ───
    print("\n" + "─" * 50)
    print("Writing .env file...")
    print("─" * 50)

    # Read template for comments
    template_lines = []
    if os.path.exists(env_example_path):
        with open(env_example_path) as f:
            template_lines = f.readlines()

    with open(env_path, 'w') as f:
        f.write("# IBM Cloud Ops Agent — Generated by setup_wizard.py\n")
        f.write(f"# Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# DO NOT COMMIT THIS FILE TO GIT\n\n")
        for key, val in values.items():
            if val:
                f.write(f"{key}={val}\n")

    print(f"\n  ✅ .env file written to: {env_path}")
    print("\nNext steps:")
    print("  1. Run:  python3 scripts/verify_credentials.py")
    print("  2. Run:  pip install -r requirements.txt")
    print("  3. Run:  ./deploy.sh")
    print()


if __name__ == '__main__':
    main()
