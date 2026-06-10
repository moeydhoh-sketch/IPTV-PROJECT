#!/usr/bin/env python3
"""
IPTV Authentication Proxy Server
A lightweight, high-security IPTV stream proxy with stunning web dashboard.
"""

import os
import sys
import sqlite3
import threading
import time
import json
import uuid
import re
import logging
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
from urllib.parse import urlparse, urlunparse

import requests
from flask import (
    Flask, request, jsonify, Response, render_template_string,
    send_file, abort, make_response, stream_with_context,
    send_from_directory
)
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "iptv-proxy-secret-change-in-production")
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iptv.db")
    # External IPTV source URL
    SOURCE_URL = os.environ.get(
        "SOURCE_URL",
        "https://live-sstv.apps.skin-knife.com/live/space_toon/index.m3u8"
    )
    # Admin password for the dashboard
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    # Grace period in seconds (3 minutes)
    GRACE_PERIOD = int(os.environ.get("GRACE_PERIOD", "180"))
    # Dashboard listen host/port
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))
    # Maximum concurrent connections per IP
    MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "3"))
    # Token expiry for temporary sessions (seconds)
    TOKEN_EXPIRY = int(os.environ.get("TOKEN_EXPIRY", "86400"))


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("IPTV-Proxy")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(app.config["DATABASE"], check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS whitelist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ip          TEXT    UNIQUE NOT NULL,
            label       TEXT    DEFAULT '',
            country     TEXT    DEFAULT 'Unknown',
            flag        TEXT    DEFAULT '',
            created_at  REAL    NOT NULL,
            updated_at  REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS blacklist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ip          TEXT    UNIQUE NOT NULL,
            label       TEXT    DEFAULT '',
            country     TEXT    DEFAULT 'Unknown',
            flag        TEXT    DEFAULT '',
            reason      TEXT    DEFAULT 'Grace period expired',
            banned_at   REAL    NOT NULL,
            updated_at  REAL    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS temp_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ip          TEXT    UNIQUE NOT NULL,
            token       TEXT    UNIQUE NOT NULL,
            country     TEXT    DEFAULT 'Unknown',
            flag        TEXT    DEFAULT '',
            started_at  REAL    NOT NULL,
            expires_at  REAL    NOT NULL,
            active      INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS active_streams (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ip          TEXT    NOT NULL,
            session_id  TEXT    NOT NULL,
            started_at  REAL    NOT NULL,
            thread_id   TEXT    DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_whitelist_ip ON whitelist(ip);
        CREATE INDEX IF NOT EXISTS idx_blacklist_ip ON blacklist(ip);
        CREATE INDEX IF NOT EXISTS idx_temp_ip ON temp_sessions(ip);
        CREATE INDEX IF NOT EXISTS idx_temp_token ON temp_sessions(token);
    """)
    conn.commit()
    conn.close()
    log.info("Database initialised successfully.")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_client_ip():
    """Extract the real client IP from request headers."""
    # Priority: X-Forwarded-For > X-Real-IP > remote_addr
    x_forwarded = request.headers.get("X-Forwarded-For", "")
    if x_forwarded:
        ips = [ip.strip() for ip in x_forwarded.split(",")]
        if ips[0]:
            return ips[0]
    x_real = request.headers.get("X-Real-IP", "")
    if x_real:
        return x_real.strip()
    return request.remote_addr or "0.0.0.0"


def get_geo_info(ip):
    """Lookup approximate geo-location and flag emoji."""
    # Skip private IPs
    private_patterns = [
        r"^10\.", r"^127\.", r"^172\.(1[6-9]|2\d|3[01])\.", r"^192\.168\.",
        r"^::1$", r"^fe80:", r"^fc00:", r"^fd00:",
    ]
    for pat in private_patterns:
        if re.match(pat, ip):
            return "Local Network", "🏠"

    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            country = data.get("country", "Unknown")
            cc = data.get("countryCode", "").lower()
            # Build flag emoji from country code
            if cc and len(cc) == 2:
                offset = 0x1F1E6 - ord("a")
                flag = chr(ord(cc[0]) + offset) + chr(ord(cc[1]) + offset)
                return country, flag
            return country, "🌍"
    except Exception:
        pass
    return "Unknown", "🌍"


def is_whitelisted(ip):
    conn = get_db()
    row = conn.execute("SELECT 1 FROM whitelist WHERE ip = ?", (ip,)).fetchone()
    conn.close()
    return row is not None


def is_blacklisted(ip):
    conn = get_db()
    row = conn.execute("SELECT 1 FROM blacklist WHERE ip = ?", (ip,)).fetchone()
    conn.close()
    return row is not None


def get_temp_session(ip):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM temp_sessions WHERE ip = ? AND active = 1", (ip,)
    ).fetchone()
    conn.close()
    return row


def create_temp_session(ip):
    """Create a grace-period temp session for an unknown IP."""
    now = time.time()
    token = uuid.uuid4().hex[:16]
    country, flag = get_geo_info(ip)
    conn = get_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO temp_sessions (ip, token, country, flag, started_at, expires_at, active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (ip, token, country, flag, now, now + app.config["GRACE_PERIOD"]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    log.info(f"Temp session created for IP {ip} ({country}) — expires in {app.config['GRACE_PERIOD']}s")
    return get_temp_session(ip)


def terminate_connection(ip):
    """Kill active streams for an IP."""
    conn = get_db()
    streams = conn.execute(
        "SELECT * FROM active_streams WHERE ip = ?", (ip,)
    ).fetchall()
    for s in streams:
        # Reset the session token/active flag
        conn.execute(
            "UPDATE temp_sessions SET active = 0 WHERE ip = ?", (ip,)
        )
    conn.execute("DELETE FROM active_streams WHERE ip = ?", (ip,))
    conn.commit()
    conn.close()
    log.warning(f"All streams terminated for IP {ip}")


def ban_ip(ip, reason="Grace period expired"):
    """Move IP to blacklist and clean up."""
    now = time.time()
    conn = get_db()
    # Get info from temp session
    session = conn.execute(
        "SELECT * FROM temp_sessions WHERE ip = ?", (ip,)
    ).fetchone()
    country = session["country"] if session else "Unknown"
    flag = session["flag"] if session else ""

    terminate_connection(ip)

    try:
        conn.execute(
            """INSERT OR REPLACE INTO blacklist (ip, label, country, flag, reason, banned_at, updated_at)
               VALUES (?, '', ?, ?, ?, ?, ?)""",
            (ip, country, flag, reason, now, now),
        )
        conn.execute("UPDATE temp_sessions SET active = 0 WHERE ip = ?", (ip,))
        conn.commit()
        log.info(f"IP {ip} has been banned. Reason: {reason}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Authentication decorator
# ---------------------------------------------------------------------------

def authenticate(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if auth == f"Bearer {app.config['ADMIN_PASSWORD']}":
            return f(*args, **kwargs)
        # Check admin cookie
        token = request.cookies.get("admin_token")
        if token == app.config["ADMIN_PASSWORD"]:
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


# ===================================================================
# API ENDPOINTS — Dashboard
# ===================================================================

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    password = data.get("password", "")
    if password == app.config["ADMIN_PASSWORD"]:
        resp = jsonify({"status": "ok"})
        resp.set_cookie("admin_token", password, max_age=86400 * 30, httponly=True, samesite="Lax")
        return resp
    return jsonify({"error": "Invalid password"}), 401


@app.route("/api/status")
@authenticate
def api_status():
    """Get dashboard status data."""
    conn = get_db()
    now = time.time()

    # Active connections (temp sessions not yet expired and not blacklisted/whitelisted)
    sessions = conn.execute(
        """SELECT * FROM temp_sessions
           WHERE active = 1 AND expires_at > ?
           AND ip NOT IN (SELECT ip FROM whitelist)
           AND ip NOT IN (SELECT ip FROM blacklist)
           ORDER BY started_at DESC""",
        (now,),
    ).fetchall()

    active_connections = []
    for s in sessions:
        remaining = max(0, int(s["expires_at"] - now))
        active_connections.append({
            "id": s["id"],
            "ip": s["ip"],
            "token": s["token"],
            "country": s["country"],
            "flag": s["flag"],
            "started_at": s["started_at"],
            "expires_at": s["expires_at"],
            "remaining": remaining,
        })

    # Whitelist
    wl_rows = conn.execute(
        "SELECT * FROM whitelist ORDER BY updated_at DESC"
    ).fetchall()
    whitelist = [
        {
            "id": r["id"],
            "ip": r["ip"],
            "label": r["label"],
            "country": r["country"],
            "flag": r["flag"],
            "created_at": r["created_at"],
        }
        for r in wl_rows
    ]

    # Blacklist
    bl_rows = conn.execute(
        "SELECT * FROM blacklist ORDER BY banned_at DESC"
    ).fetchall()
    blacklist = [
        {
            "id": r["id"],
            "ip": r["ip"],
            "label": r["label"],
            "country": r["country"],
            "flag": r["flag"],
            "reason": r["reason"],
            "banned_at": r["banned_at"],
        }
        for r in bl_rows
    ]

    # Count of active streams
    stream_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM active_streams"
    ).fetchone()["cnt"]

    conn.close()

    return jsonify({
        "now": now,
        "grace_period": app.config["GRACE_PERIOD"],
        "active_connections": active_connections,
        "whitelist": whitelist,
        "blacklist": blacklist,
        "stream_count": stream_count,
    })


@app.route("/api/approve", methods=["POST"])
@authenticate
def api_approve():
    """Approve an IP — move from temp to whitelist."""
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    if not ip:
        return jsonify({"error": "IP required"}), 400

    now = time.time()
    conn = get_db()

    # Get temp session data
    session = conn.execute(
        "SELECT * FROM temp_sessions WHERE ip = ?", (ip,)
    ).fetchone()
    country = session["country"] if session else "Unknown"
    flag = session["flag"] if session else ""

    try:
        conn.execute(
            """INSERT OR REPLACE INTO whitelist (ip, label, country, flag, created_at, updated_at)
               VALUES (?, '', ?, ?, ?, ?)""",
            (ip, country, flag, now, now),
        )
        conn.execute("UPDATE temp_sessions SET active = 0 WHERE ip = ?", (ip,))
        conn.execute("DELETE FROM active_streams WHERE ip = ?", (ip,))
        conn.commit()
        log.info(f"IP {ip} approved and added to whitelist.")
        return jsonify({"status": "approved", "ip": ip})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/block", methods=["POST"])
@authenticate
def api_block():
    """Block an IP immediately — move to blacklist."""
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    reason = data.get("reason", "Manually blocked by admin")
    if not ip:
        return jsonify({"error": "IP required"}), 400

    ban_ip(ip, reason)
    return jsonify({"status": "blocked", "ip": ip})


@app.route("/api/unban", methods=["POST"])
@authenticate
def api_unban():
    """Unban an IP — remove from blacklist."""
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    if not ip:
        return jsonify({"error": "IP required"}), 400

    conn = get_db()
    try:
        conn.execute("DELETE FROM blacklist WHERE ip = ?", (ip,))
        conn.commit()
        log.info(f"IP {ip} unbanned.")
        return jsonify({"status": "unbanned", "ip": ip})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/rename", methods=["POST"])
@authenticate
def api_rename():
    """Rename a label for whitelist or blacklist entry."""
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    label = data.get("label", "").strip()
    list_type = data.get("list", "whitelist")  # 'whitelist' or 'blacklist'

    if not ip:
        return jsonify({"error": "IP required"}), 400

    table = "whitelist" if list_type == "whitelist" else "blacklist"
    conn = get_db()
    try:
        now = time.time()
        conn.execute(
            f"UPDATE {table} SET label = ?, updated_at = ? WHERE ip = ?",
            (label, now, ip),
        )
        conn.commit()
        return jsonify({"status": "renamed", "ip": ip, "label": label})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/clear-expired")
@authenticate
def api_clear_expired():
    """Manually clear expired temp sessions."""
    now = time.time()
    conn = get_db()
    expired = conn.execute(
        "SELECT * FROM temp_sessions WHERE active = 1 AND expires_at < ? "
        "AND ip NOT IN (SELECT ip FROM whitelist) "
        "AND ip NOT IN (SELECT ip FROM blacklist)",
        (now,),
    ).fetchall()

    for s in expired:
        ban_ip(s["ip"], "Grace period expired")

    conn.close()
    return jsonify({"cleared": len(expired)})


# ===================================================================
# STREAM PROXY — Core IPTV Proxying
# ===================================================================

@app.route("/stream")
def proxy_stream():
    """
    Main streaming endpoint.
    - Checks if IP is whitelisted → allows stream.
    - Checks if IP is blacklisted → 403 Forbidden.
    - Unknown IP → creates temp session (grace period) → allows stream.
    - A background thread monitors expiry; if timer runs out → ban & kill.
    """
    client_ip = get_client_ip()
    log.info(f"Stream request from IP: {client_ip}")

    # Block blacklisted IPs immediately
    if is_blacklisted(client_ip):
        log.warning(f"Blocked blacklisted IP: {client_ip}")
        return jsonify({"error": "Access denied — you are banned."}), 403

    # If not whitelisted, create or get temp session
    if not is_whitelisted(client_ip):
        session = get_temp_session(client_ip)
        if not session or session["active"] == 0:
            session = create_temp_session(client_ip)

        # Check if session has expired
        if time.time() > session["expires_at"]:
            ban_ip(client_ip, "Grace period expired")
            return jsonify({"error": "Access denied — grace period expired."}), 403

    # --- Proxy the stream ---
    source_url = app.config["SOURCE_URL"]

    def generate():
        """Generator that fetches and yields stream chunks in a managed session."""
        session_id = uuid.uuid4().hex
        thread_id = threading.current_thread().name

        # Register active stream
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO active_streams (ip, session_id, started_at, thread_id) VALUES (?, ?, ?, ?)",
                (client_ip, session_id, time.time(), thread_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

        try:
            # Stream from external source with chunked transfer
            resp = requests.get(source_url, stream=True, timeout=30)
            resp.raise_for_status()

            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    # Check if this IP has been banned during streaming
                    if is_blacklisted(client_ip):
                        log.warning(f"Stream killed for IP {client_ip} — banned during playback.")
                        break
                    yield chunk
        except requests.exceptions.RequestException as e:
            log.error(f"Stream fetch error for {client_ip}: {e}")
        except GeneratorExit:
            log.info(f"Client {client_ip} disconnected.")
        finally:
            # Cleanup active stream
            conn = get_db()
            try:
                conn.execute(
                    "DELETE FROM active_streams WHERE ip = ? AND session_id = ?",
                    (client_ip, session_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                conn.close()

    response = Response(
        stream_with_context(generate()),
        mimetype="application/vnd.apple.mpegurl",
    )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Proxy"] = "IPTV-Auth-Proxy"
    return response


# ===================================================================
# SERVE STATIC — Dashboard HTML
# ===================================================================

# We embed the entire HTML dashboard as a string for single-file deployment
# The HTML is loaded from the template at startup

HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")


@app.route("/")
def index():
    if os.path.exists(HTML_FILE):
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            return render_template_string(f.read())
    return "Dashboard not found. Please ensure dashboard.html exists.", 404


# ===================================================================
# Background Cleanup Thread
# ===================================================================

def cleanup_worker():
    """Background thread that periodically bans expired sessions."""
    while True:
        try:
            now = time.time()
            conn = get_db()
            expired = conn.execute(
                "SELECT * FROM temp_sessions WHERE active = 1 AND expires_at < ? "
                "AND ip NOT IN (SELECT ip FROM whitelist) "
                "AND ip NOT IN (SELECT ip FROM blacklist)",
                (now,),
            ).fetchall()
            for s in expired:
                ban_ip(s["ip"], "Grace period expired")
            conn.close()
        except Exception as e:
            log.error(f"Cleanup worker error: {e}")
        time.sleep(15)  # Check every 15 seconds


# ===================================================================
# Main
# ===================================================================

def main():
    init_db()

    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True, name="cleanup-worker")
    cleanup_thread.start()
    log.info("Background cleanup worker started.")

    log.info(f"Starting IPTV Auth Proxy on {app.config['HOST']}:{app.config['PORT']}")
    log.info(f"Source URL: {app.config['SOURCE_URL']}")
    log.info(f"Grace period: {app.config['GRACE_PERIOD']} seconds")

    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
