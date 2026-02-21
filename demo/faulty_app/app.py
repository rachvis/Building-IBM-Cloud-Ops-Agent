"""
app.py — Deliberately Broken Flask App for IBM Cloud Ops Agent Demo
====================================================================
This app ships with THREE intentional bugs that cause it to fail on
IBM Cloud Code Engine. The IBM Cloud Ops Agent will detect, diagnose,
and fix each one automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BUG 1 ▸ WRONG PORT
  The app binds to port 5000, but the Code Engine deployment is
  configured with image_port=3000. Code Engine's load balancer
  forwards traffic to port 3000, which nothing is listening on.
  Result: 502 Bad Gateway on every request. The app DOES start, but
  is completely unreachable.

BUG 2 ▸ MISSING REQUIRED ENVIRONMENT VARIABLE
  The /api/data endpoint reads os.environ["DATABASE_URL"] without a
  fallback. If DATABASE_URL is not set in Code Engine, any call to
  that route raises a KeyError and returns HTTP 500.

BUG 3 ▸ CRASH ROUTE (intentional unhandled exception)
  The /api/crash endpoint divides by zero. Calling it kills the
  worker thread, causing a 500 error and a traceback in the logs.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOW THE DEMO WORKS
==================
1. Deploy this app to Code Engine with image_port=3000 and NO DATABASE_URL set.
2. The app will appear as "failed" / unreachable.
3. Tell the Ops Agent: "Check the health of faulty-api in my Code Engine project."
4. The agent will:
   a) Call check_app_health()    → spots status=failed + port mismatch
   b) Call get_app_logs()        → sees KeyError: DATABASE_URL in logs
   c) Call update_app()          → fixes port from 3000 → 5000
   d) Call update_app_env_vars() → sets DATABASE_URL=sqlite:///demo.db
   e) Call check_app_health()    → confirms status=ready ✅

NOTE: This is a demo container only. In production you would use a
real database URL from IBM Secrets Manager.
"""

import os
import logging

from flask import Flask, jsonify

# ─── Logging setup (structured JSON-like output for Cloud Logs) ───────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__)


# ─── BUG 2 helper: read DATABASE_URL without fallback ────────────────────────
def get_database_url() -> str:
    """
    Reads DATABASE_URL from environment.

    BUG: Uses os.environ[] (raises KeyError) instead of os.getenv() (returns None).
    If DATABASE_URL is not set in Code Engine, this blows up with:
      KeyError: 'DATABASE_URL'
    """
    return os.environ["DATABASE_URL"]   # ← intentional: no default / fallback


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    """Simple liveness probe — always returns 200 if the process is alive."""
    log.info("Health check requested")
    return jsonify({"status": "ok", "service": "faulty-api"}), 200


@app.route("/api/data")
def get_data():
    """
    Returns mock data after reading the database URL from env.

    BUG 2: If DATABASE_URL is missing this raises KeyError and returns 500.
    The traceback is logged and visible to the Ops Agent via get_app_logs().
    """
    try:
        db_url = get_database_url()
        log.info(f"Connected to database: {db_url}")
        return jsonify({
            "status": "ok",
            "database": db_url,
            "records": [
                {"id": 1, "name": "Alice", "role": "Engineer"},
                {"id": 2, "name": "Bob",   "role": "Manager"},
            ],
        }), 200
    except KeyError as exc:
        log.error(
            f"STARTUP ERROR: Required environment variable {exc} is not set. "
            "Set DATABASE_URL in your Code Engine app environment variables."
        )
        return jsonify({
            "error": f"Missing required environment variable: {exc}",
            "fix": "Set DATABASE_URL in Code Engine → your app → Environment variables",
        }), 500


@app.route("/api/crash")
def crash():
    """
    BUG 3: Intentional division-by-zero crash.
    Calling this endpoint raises ZeroDivisionError and kills the request thread.
    The full traceback appears in Cloud Logs — visible to the Ops Agent.
    """
    log.warning("Crash route called — this will raise ZeroDivisionError!")
    result = 1 / 0          # ← intentional crash
    return jsonify({"result": result}), 200


@app.route("/")
def index():
    return jsonify({
        "service": "faulty-api",
        "version": "1.0.0-BROKEN",
        "routes": {
            "/health":     "Liveness probe",
            "/api/data":   "Returns data (fails if DATABASE_URL not set)",
            "/api/crash":  "Always crashes with ZeroDivisionError",
        },
        "note": (
            "This app has deliberate bugs for the IBM Cloud Ops Agent demo. "
            "See DEMO_INSTRUCTIONS.md for the full walkthrough."
        ),
    }), 200


# ─── BUG 1: Bind to port 5000 but Code Engine is configured for port 3000 ───
if __name__ == "__main__":
    # The Code Engine app spec sets image_port=3000 (wrong).
    # This process binds to 5000. Traffic arrives on 3000 → nothing there → 502.
    port = int(os.getenv("PORT", "5000"))
    log.info(f"Starting faulty-api on port {port}")
    log.info("DATABASE_URL = %s", os.getenv("DATABASE_URL", "NOT SET ← this will cause /api/data to fail"))
    app.run(host="0.0.0.0", port=port, debug=False)
