#!/usr/bin/env python3
"""
IBM Cloud Ops Agent — MCP Toolkit Server
=========================================
Provides 28 tools across Code Engine, Cloud Logs, Cloud Monitoring,
and IBM Cloud Databases for the watsonx Orchestrate agent.

Credentials are injected by deploy.sh from your .env file.
"""

import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

# ─────────────────────────────────────────
# CREDENTIALS (injected by deploy.sh)
# ─────────────────────────────────────────
IBMCLOUD_API_KEY            = '__IBMCLOUD_API_KEY__'
IBMCLOUD_ACCOUNT_ID         = '__IBMCLOUD_ACCOUNT_ID__'
IBMCLOUD_REGION             = '__IBMCLOUD_REGION__'
CODE_ENGINE_PROJECT_ID      = '__CODE_ENGINE_PROJECT_ID__'
CODE_ENGINE_REGION          = '__CODE_ENGINE_REGION__'
CLOUD_LOGS_INSTANCE_ID      = '__CLOUD_LOGS_INSTANCE_ID__'
CLOUD_LOGS_INSTANCE_GUID    = '__CLOUD_LOGS_INSTANCE_GUID__'
CLOUD_LOGS_REGION           = '__CLOUD_LOGS_REGION__'
MONITORING_API_TOKEN        = '__MONITORING_API_TOKEN__'
MONITORING_ENDPOINT         = '__MONITORING_ENDPOINT__'
ICD_REGION                  = '__ICD_REGION__'
ICD_RESOURCE_GROUP          = '__ICD_RESOURCE_GROUP__'

# ─────────────────────────────────────────
# IAM TOKEN MANAGEMENT
# ─────────────────────────────────────────

_iam_token: Optional[str] = None
_token_expiry: Optional[datetime] = None


def get_iam_token() -> Optional[str]:
    """Obtain and cache an IBM Cloud IAM bearer token."""
    global _iam_token, _token_expiry
    if _iam_token and _token_expiry and datetime.now() < _token_expiry:
        return _iam_token
    try:
        resp = requests.post(
            'https://iam.cloud.ibm.com/identity/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'urn:ibm:params:oauth:grant-type:apikey',
                'apikey': IBMCLOUD_API_KEY,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        _iam_token = data['access_token']
        _token_expiry = datetime.now() + timedelta(minutes=50)
        return _iam_token
    except Exception as exc:
        print(f"[IAM] Token error: {exc}", file=sys.stderr)
        return None


def auth_headers() -> Dict[str, str]:
    token = get_iam_token()
    if not token:
        raise RuntimeError("Unable to obtain IAM token. Check IBMCLOUD_API_KEY.")
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }


def _api(method: str, url: str, **kwargs) -> Dict[str, Any]:
    """Generic REST helper — returns {success, data} or {success, error}."""
    try:
        headers = {**auth_headers(), **kwargs.pop('extra_headers', {})}
        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if resp.status_code in (200, 201, 202, 204):
            body = resp.json() if resp.content else {}
            return {'success': True, 'data': body}
        return {
            'success': False,
            'error': f'HTTP {resp.status_code}',
            'details': resp.text[:500],
        }
    except requests.Timeout:
        return {'success': False, 'error': 'Request timed out after 30 s'}
    except Exception as exc:
        return {'success': False, 'error': str(exc)[:300]}


# ═══════════════════════════════════════════
# CODE ENGINE TOOLS
# ═══════════════════════════════════════════

CE_BASE = "https://api.{region}.codeengine.cloud.ibm.com/v2/projects/{project_id}"


def _ce_url(path: str, region: str = None, project_id: str = None) -> str:
    r = region or CODE_ENGINE_REGION or IBMCLOUD_REGION
    p = project_id or CODE_ENGINE_PROJECT_ID
    return CE_BASE.format(region=r, project_id=p) + path


def list_apps(project_id: str = None) -> Dict:
    """List all Code Engine applications in the project."""
    result = _api('GET', _ce_url('/apps', project_id=project_id))
    if result['success']:
        apps = result['data'].get('apps', [])
        summary = [
            {
                'name': a.get('name'),
                'status': a.get('status', {}).get('reason', 'unknown'),
                'instances': a.get('scale_initial_instances', 1),
                'memory': a.get('scale_memory_limit', 'N/A'),
                'cpu': a.get('scale_cpu_limit', 'N/A'),
                'url': a.get('status', {}).get('url', 'N/A'),
            }
            for a in apps
        ]
        return {'success': True, 'apps': summary, 'count': len(summary)}
    return result


def get_app_status(app_name: str, project_id: str = None) -> Dict:
    """Get detailed status and configuration for a Code Engine app."""
    result = _api('GET', _ce_url(f'/apps/{app_name}', project_id=project_id))
    if result['success']:
        a = result['data']
        return {
            'success': True,
            'name': a.get('name'),
            'status': a.get('status', {}),
            'image': a.get('image_reference'),
            'min_instances': a.get('scale_min_instances', 0),
            'max_instances': a.get('scale_max_instances', 10),
            'current_instances': a.get('scale_initial_instances', 1),
            'memory': a.get('scale_memory_limit'),
            'cpu': a.get('scale_cpu_limit'),
            'env_vars': a.get('run_env_variables', []),
            'url': a.get('status', {}).get('url'),
        }
    return result


def scale_app(app_name: str, instances: int, project_id: str = None) -> Dict:
    """Scale a Code Engine app to a specific number of instances."""
    # First, GET the current app to obtain an ETag for optimistic locking
    get_resp = requests.get(
        _ce_url(f'/apps/{app_name}', project_id=project_id),
        headers=auth_headers(),
        timeout=30,
    )
    if get_resp.status_code != 200:
        return {'success': False, 'error': f'App {app_name!r} not found'}
    etag = get_resp.headers.get('ETag', '*')

    result = _api(
        'PATCH',
        _ce_url(f'/apps/{app_name}', project_id=project_id),
        json={'scale_initial_instances': instances},
        extra_headers={'If-Match': etag, 'Content-Type': 'application/json'},
    )
    if result['success']:
        return {'success': True, 'message': f"Scaled {app_name!r} to {instances} instance(s)."}
    return result


def restart_app(app_name: str, project_id: str = None) -> Dict:
    """Restart a Code Engine application by creating a new revision."""
    result = _api(
        'POST',
        _ce_url(f'/apps/{app_name}/revisions', project_id=project_id),
        json={},
        extra_headers={'Content-Type': 'application/json'},
    )
    if result['success']:
        return {'success': True, 'message': f"Restart triggered for {app_name!r}."}
    return result


def update_app_memory(app_name: str, memory: str, project_id: str = None) -> Dict:
    """Update the memory limit of a Code Engine app (e.g. '512M', '1G', '2G')."""
    get_resp = requests.get(
        _ce_url(f'/apps/{app_name}', project_id=project_id),
        headers=auth_headers(), timeout=30,
    )
    if get_resp.status_code != 200:
        return {'success': False, 'error': f'App {app_name!r} not found'}
    etag = get_resp.headers.get('ETag', '*')

    result = _api(
        'PATCH',
        _ce_url(f'/apps/{app_name}', project_id=project_id),
        json={'scale_memory_limit': memory},
        extra_headers={'If-Match': etag, 'Content-Type': 'application/json'},
    )
    if result['success']:
        return {'success': True, 'message': f"Memory for {app_name!r} updated to {memory}."}
    return result


def list_ce_jobs(project_id: str = None) -> Dict:
    """List all Code Engine jobs in the project."""
    result = _api('GET', _ce_url('/jobs', project_id=project_id))
    if result['success']:
        jobs = result['data'].get('jobs', [])
        return {
            'success': True,
            'jobs': [{'name': j.get('name'), 'status': j.get('status')} for j in jobs],
            'count': len(jobs),
        }
    return result


def list_ce_builds(project_id: str = None) -> Dict:
    """List all Code Engine builds in the project."""
    result = _api('GET', _ce_url('/builds', project_id=project_id))
    if result['success']:
        builds = result['data'].get('builds', [])
        return {'success': True, 'builds': builds, 'count': len(builds)}
    return result


def get_ce_project_info(project_id: str = None) -> Dict:
    """Get information about the Code Engine project."""
    p = project_id or CODE_ENGINE_PROJECT_ID
    r = CODE_ENGINE_REGION or IBMCLOUD_REGION
    result = _api('GET', f"https://api.{r}.codeengine.cloud.ibm.com/v2/projects/{p}")
    if result['success']:
        proj = result['data']
        return {
            'success': True,
            'name': proj.get('name'),
            'id': proj.get('id'),
            'region': proj.get('region'),
            'status': proj.get('status'),
            'resource_group': proj.get('resource_group_id'),
        }
    return result


# ═══════════════════════════════════════════
# CLOUD LOGS TOOLS
# ═══════════════════════════════════════════

def _logs_endpoint() -> str:
    return f"https://{CLOUD_LOGS_INSTANCE_ID}.api.{CLOUD_LOGS_REGION}.logs.cloud.ibm.com"


def get_app_logs(app_name: str, hours: int = 1, severity: str = None) -> Dict:
    """Retrieve recent logs for a specific Code Engine application.

    Args:
        app_name: Name of the Code Engine application.
        hours: How many hours back to look (default 1).
        severity: Optional filter — 'debug', 'info', 'warning', 'error', 'critical'.
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    query_parts = [f'source logs | filter $d.kubernetes.labels.app == "{app_name}"']
    if severity:
        sev_map = {'debug': 1, 'info': 2, 'warning': 3, 'error': 4, 'critical': 5}
        sev_num = sev_map.get(severity.lower(), 2)
        query_parts.append(f'filter $l.severity >= {sev_num}')
    query_parts.append('limit 100')

    return _query_cloud_logs(
        query=' | '.join(query_parts),
        start_time=start_time.isoformat() + 'Z',
        end_time=end_time.isoformat() + 'Z',
    )


def _query_cloud_logs(query: str, start_time: str = None, end_time: str = None) -> Dict:
    """Internal: send a DataPrime query to IBM Cloud Logs."""
    end = end_time or datetime.utcnow().isoformat() + 'Z'
    start = start_time or (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z'

    payload = {
        'query': query,
        'metadata': {
            'startDate': start,
            'endDate': end,
            'tier': 'TIER_FREQUENT_SEARCH',
            'syntax': 'QUERY_SYNTAX_DATAPRIME',
            'defaultSource': 'logs',
        },
    }
    url = f"{_logs_endpoint()}/v1/dataprime/query"
    try:
        headers = {**auth_headers(), 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            return {'success': False, 'error': f'HTTP {resp.status_code}', 'details': resp.text[:400]}
        lines = [line for line in resp.text.strip().split('\n') if line]
        results = []
        for line in lines[:50]:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        log_entries = []
        for r in results:
            if r.get('result', {}).get('results'):
                log_entries.extend(r['result']['results'])
        return {'success': True, 'entries': log_entries, 'count': len(log_entries)}
    except Exception as exc:
        return {'success': False, 'error': str(exc)[:300]}


def query_cloud_logs(query: str, hours: int = 1) -> Dict:
    """Run a custom DataPrime query against IBM Cloud Logs.

    Args:
        query: A DataPrime query string.
               Example: 'source logs | filter $l.severity >= 4 | limit 50'
        hours: How many hours back to query (default 1).
    """
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    return _query_cloud_logs(
        query=query,
        start_time=start.isoformat() + 'Z',
        end_time=end.isoformat() + 'Z',
    )


def get_error_logs(hours: int = 1) -> Dict:
    """Get all error and critical logs across all services for the past N hours."""
    return query_cloud_logs(
        query='source logs | filter $l.severity >= 4 | limit 100',
        hours=hours,
    )


def get_logs_summary(hours: int = 1) -> Dict:
    """Get a summary count of logs by severity for the past N hours."""
    return query_cloud_logs(
        query='source logs | count by $l.severity | limit 10',
        hours=hours,
    )


# ═══════════════════════════════════════════
# CLOUD MONITORING TOOLS
# ═══════════════════════════════════════════

def _mon_api(path: str, params: dict = None) -> Dict:
    """Call IBM Cloud Monitoring (Sysdig) REST API."""
    if not MONITORING_API_TOKEN or MONITORING_API_TOKEN == '__MONITORING_API_TOKEN__':
        return {'success': False, 'error': 'MONITORING_API_TOKEN not configured in .env'}
    url = f"{MONITORING_ENDPOINT}{path}"
    try:
        resp = requests.get(
            url,
            headers={
                'Authorization': f'Bearer {MONITORING_API_TOKEN}',
                'IBMInstanceID': CLOUD_LOGS_INSTANCE_GUID,
                'Accept': 'application/json',
            },
            params=params or {},
            timeout=30,
        )
        if resp.status_code == 200:
            return {'success': True, 'data': resp.json()}
        return {'success': False, 'error': f'HTTP {resp.status_code}', 'details': resp.text[:400]}
    except Exception as exc:
        return {'success': False, 'error': str(exc)[:300]}


def get_metrics(metric_name: str, app_name: str = None, minutes: int = 60) -> Dict:
    """Get metrics from IBM Cloud Monitoring.

    Args:
        metric_name: e.g. 'cpu.used.percent', 'memory.used.percent', 'net.bytes.in'
        app_name: Optional — filter by application name.
        minutes: Time window in minutes (default 60).
    """
    end_ts = int(datetime.utcnow().timestamp())
    start_ts = end_ts - (minutes * 60)
    params = {
        'metrics': json.dumps([{'id': metric_name}]),
        'start': start_ts,
        'end': end_ts,
        'sampling': 300,
    }
    if app_name:
        params['filter'] = f'kubernetes.deployment.name = "{app_name}"'
    return _mon_api('/api/data/batch', params)


def list_alerts() -> Dict:
    """List all active monitoring alerts."""
    return _mon_api('/api/v3/alerts')


def get_dashboards() -> Dict:
    """List all available monitoring dashboards."""
    return _mon_api('/api/v3/dashboards')


def get_cpu_usage(app_name: str = None, minutes: int = 60) -> Dict:
    """Get CPU usage metrics for an app (or all apps) over the past N minutes."""
    return get_metrics('cpu.used.percent', app_name, minutes)


def get_memory_usage(app_name: str = None, minutes: int = 60) -> Dict:
    """Get memory usage metrics for an app (or all apps) over the past N minutes."""
    return get_metrics('memory.used.percent', app_name, minutes)


def get_network_usage(app_name: str = None, minutes: int = 60) -> Dict:
    """Get network I/O metrics for an app (or all apps) over the past N minutes."""
    return get_metrics('net.bytes.total', app_name, minutes)


# ═══════════════════════════════════════════
# IBM CLOUD DATABASES TOOLS
# ═══════════════════════════════════════════

ICD_BASE = "https://api.{region}.databases.cloud.ibm.com/v5/ibm"


def _icd_url(path: str) -> str:
    region = ICD_REGION or IBMCLOUD_REGION
    return ICD_BASE.format(region=region) + path


def list_database_instances() -> Dict:
    """List all IBM Cloud Database instances in your account."""
    # Use the Resource Controller API to find ICD instances
    params = {'resource_id': 'databases-for-postgresql,databases-for-mongodb,databases-for-redis,databases-for-elasticsearch,databases-for-mysql,messages-for-rabbitmq'}
    result = _api(
        'GET',
        'https://resource-controller.cloud.ibm.com/v2/resource_instances',
        params={'resource_plan_id': 'databases'},
    )
    # Fallback: list all resource instances and filter
    result2 = _api('GET', 'https://resource-controller.cloud.ibm.com/v2/resource_instances')
    if result2['success']:
        all_instances = result2['data'].get('resources', [])
        db_instances = [
            i for i in all_instances
            if 'database' in i.get('resource_id', '').lower()
            or 'databases' in i.get('resource_plan_id', '').lower()
        ]
        return {
            'success': True,
            'databases': [
                {
                    'name': i.get('name'),
                    'id': i.get('id'),
                    'type': i.get('resource_id', '').replace('databases-for-', ''),
                    'status': i.get('state'),
                    'region': i.get('region_id'),
                    'resource_group': i.get('resource_group_id'),
                }
                for i in db_instances
            ],
            'count': len(db_instances),
        }
    return result2


def get_database_details(deployment_id: str) -> Dict:
    """Get detailed information about a specific database deployment.

    Args:
        deployment_id: The CRN or ID of the database instance (from list_database_instances).
    """
    import urllib.parse
    encoded_id = urllib.parse.quote(deployment_id, safe='')
    result = _api('GET', _icd_url(f'/deployments/{encoded_id}'))
    if result['success']:
        dep = result['data'].get('deployment', result['data'])
        return {
            'success': True,
            'name': dep.get('name'),
            'type': dep.get('type'),
            'platform_options': dep.get('platform_options', {}),
            'version': dep.get('version'),
            'status': dep.get('status'),
            'connection': dep.get('connection', {}),
        }
    return result


def get_database_connection_info(deployment_id: str) -> Dict:
    """Get connection strings and credentials for a database.

    Args:
        deployment_id: The CRN or ID of the database instance.
    """
    import urllib.parse
    encoded_id = urllib.parse.quote(deployment_id, safe='')
    result = _api('GET', _icd_url(f'/deployments/{encoded_id}/users/admin/connections/public'))
    if result['success']:
        return {'success': True, 'connection_info': result['data']}
    return result


def list_database_backups(deployment_id: str) -> Dict:
    """List available backups for a database instance.

    Args:
        deployment_id: The CRN or ID of the database instance.
    """
    import urllib.parse
    encoded_id = urllib.parse.quote(deployment_id, safe='')
    result = _api('GET', _icd_url(f'/deployments/{encoded_id}/backups'))
    if result['success']:
        backups = result['data'].get('backups', [])
        return {
            'success': True,
            'backups': [
                {
                    'id': b.get('id'),
                    'type': b.get('type'),
                    'status': b.get('status'),
                    'created_at': b.get('created_at'),
                    'size': b.get('size'),
                }
                for b in backups
            ],
            'count': len(backups),
        }
    return result


def get_database_scaling(deployment_id: str) -> Dict:
    """Get current resource scaling (CPU, memory, disk) for a database.

    Args:
        deployment_id: The CRN or ID of the database instance.
    """
    import urllib.parse
    encoded_id = urllib.parse.quote(deployment_id, safe='')
    result = _api('GET', _icd_url(f'/deployments/{encoded_id}/groups'))
    if result['success']:
        return {'success': True, 'scaling': result['data']}
    return result


# ═══════════════════════════════════════════
# GENERAL / RESOURCE TOOLS
# ═══════════════════════════════════════════

def list_resource_groups() -> Dict:
    """List all resource groups in the IBM Cloud account."""
    result = _api(
        'GET',
        f'https://resource-controller.cloud.ibm.com/v2/resource_groups',
        params={'account_id': IBMCLOUD_ACCOUNT_ID},
    )
    if result['success']:
        groups = result['data'].get('resources', [])
        return {
            'success': True,
            'resource_groups': [{'name': g.get('name'), 'id': g.get('id'), 'state': g.get('state')} for g in groups],
        }
    return result


def get_account_summary() -> Dict:
    """Get a high-level summary of active services and resources in the account."""
    result = _api(
        'GET',
        'https://resource-controller.cloud.ibm.com/v2/resource_instances',
        params={'account_id': IBMCLOUD_ACCOUNT_ID, 'limit': 100},
    )
    if result['success']:
        resources = result['data'].get('resources', [])
        by_type: Dict[str, int] = {}
        for r in resources:
            rt = r.get('resource_id', 'unknown').split('::')[0]
            by_type[rt] = by_type.get(rt, 0) + 1
        return {
            'success': True,
            'total_resources': len(resources),
            'by_service': by_type,
        }
    return result


# ═══════════════════════════════════════════
# MCP PROTOCOL DISPATCHER
# ═══════════════════════════════════════════

TOOL_MAP = {
    # Code Engine
    'list_apps':                list_apps,
    'get_app_status':           get_app_status,
    'scale_app':                scale_app,
    'restart_app':              restart_app,
    'update_app_memory':        update_app_memory,
    'list_ce_jobs':             list_ce_jobs,
    'list_ce_builds':           list_ce_builds,
    'get_ce_project_info':      get_ce_project_info,
    # Cloud Logs
    'get_app_logs':             get_app_logs,
    'query_cloud_logs':         query_cloud_logs,
    'get_error_logs':           get_error_logs,
    'get_logs_summary':         get_logs_summary,
    # Cloud Monitoring
    'get_metrics':              get_metrics,
    'list_alerts':              list_alerts,
    'get_dashboards':           get_dashboards,
    'get_cpu_usage':            get_cpu_usage,
    'get_memory_usage':         get_memory_usage,
    'get_network_usage':        get_network_usage,
    # Databases
    'list_database_instances':  list_database_instances,
    'get_database_details':     get_database_details,
    'get_database_connection_info': get_database_connection_info,
    'list_database_backups':    list_database_backups,
    'get_database_scaling':     get_database_scaling,
    # General
    'list_resource_groups':     list_resource_groups,
    'get_account_summary':      get_account_summary,
}


def tools_list_response() -> str:
    """Build the MCP tools/list response."""
    tools = []
    for name, fn in TOOL_MAP.items():
        import inspect
        sig = inspect.signature(fn)
        doc = (fn.__doc__ or '').strip().split('\n')[0]
        props = {}
        required = []
        for pname, param in sig.parameters.items():
            if param.annotation == int:
                ptype = 'integer'
            elif param.annotation == bool:
                ptype = 'boolean'
            else:
                ptype = 'string'
            props[pname] = {'type': ptype}
            if param.default is inspect.Parameter.empty:
                required.append(pname)
        tools.append({
            'name': name,
            'description': doc,
            'inputSchema': {
                'type': 'object',
                'properties': props,
                'required': required,
            },
        })
    return json.dumps({'tools': tools})


def main():
    """Main MCP stdio loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({'error': 'Invalid JSON'}) + '\n')
            sys.stdout.flush()
            continue

        method = request.get('method', '')
        req_id = request.get('id')

        def respond(result):
            sys.stdout.write(json.dumps({'id': req_id, 'result': result}) + '\n')
            sys.stdout.flush()

        def respond_error(msg):
            sys.stdout.write(json.dumps({'id': req_id, 'error': {'message': msg}}) + '\n')
            sys.stdout.flush()

        if method == 'tools/list':
            respond({'tools': json.loads(tools_list_response())['tools']})

        elif method == 'tools/call':
            params = request.get('params', {})
            tool_name = params.get('name')
            tool_args = params.get('arguments', {})

            fn = TOOL_MAP.get(tool_name)
            if not fn:
                respond_error(f"Unknown tool: {tool_name!r}")
                continue

            try:
                result = fn(**tool_args)
                respond({'content': [{'type': 'text', 'text': json.dumps(result, indent=2)}]})
            except TypeError as te:
                respond_error(f"Invalid arguments for {tool_name}: {te}")
            except Exception as exc:
                respond_error(f"Tool error: {exc}")

        elif method == 'initialize':
            respond({
                'protocolVersion': '2024-11-05',
                'serverInfo': {'name': 'ibm-cloud-ops-toolkit', 'version': '1.0.0'},
                'capabilities': {'tools': {}},
            })

        else:
            respond_error(f"Unknown method: {method!r}")


if __name__ == '__main__':
    main()
