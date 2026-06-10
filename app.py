#!/usr/bin/env python3
"""
IPTV Authentication Proxy Server (النسخة النهائية لحل مشكلة الأندرويد والأداء العالي)
خادم وسيط ذكي وعالي الأمان لحماية قنوات الـ IPTV مع لوحة تحكم سايبربانك متحركة.
يدعم روابط البث المباشر المستمر (TS) وقوائم التشغيل المتقطعة (HLS/m3u8) بشكل كامل.
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
import base64
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse, urlunparse, urljoin

import requests
from flask import (
    Flask, request, jsonify, Response, render_template_string,
    abort, make_response, stream_with_context
)
from flask_cors import CORS

# ---------------------------------------------------------------------------
# إعدادات التهيئة والتحكم (Configuration)
# ---------------------------------------------------------------------------

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "iptv-proxy-secret-change-in-production")
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iptv.db")
    
    # رابط بث الـ IPTV الخارجي (المنبع المعتمد للتجربة: الجزيرة)
    SOURCE_URL = os.environ.get(
        "SOURCE_URL",
        "https://dash4.antik.sk/live/test_aljazeera/playlist.m3u8"
    )
    
    # كلمة مرور مدير لوحة التحكم
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    
    # فترة السماح للمشاهدين الجدد بالثواني (180 ثانية = 3 دقائق)
    GRACE_PERIOD = int(os.environ.get("GRACE_PERIOD", "180"))
    
    # إعدادات الشبكة والمنفذ
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))
    
    # الحد الأقصى للاتصالات المتزامنة لكل آيبي
    MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "5"))


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# إعداد تتبع الأحداث (Logging)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("IPTVProxy")

# إنشاء مجمع اتصالات ذكي (HTTP Connection Pool) لرفع كفاءة البث
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=200)
http_session.mount("http://", adapter)
http_session.mount("https://", adapter)
http_session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV-Proxy/2.0"})

# ---------------------------------------------------------------------------
# إدارة قاعدة البيانات (Database Management)
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(app.config["DATABASE"], timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT UNIQUE,
            label TEXT,
            country TEXT,
            flag TEXT,
            created_at REAL,
            updated_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT UNIQUE,
            label TEXT,
            country TEXT,
            flag TEXT,
            reason TEXT,
            banned_at REAL,
            updated_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS temp_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT UNIQUE,
            token TEXT,
            country TEXT,
            flag TEXT,
            started_at REAL,
            expires_at REAL,
            active INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS active_streams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT,
            session_id TEXT,
            started_at REAL,
            thread_id TEXT
        )
    """)
    conn.commit()
    conn.close()
    log.info("Database initialised successfully.")


# ---------------------------------------------------------------------------
# دوال التحكم والتحقق
# ---------------------------------------------------------------------------

def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
    elif request.headers.get("X-Real-IP"):
        ip = request.headers.get("X-Real-IP").strip()
    else:
        ip = request.remote_addr
    return ip


def get_geo_info(ip):
    private_patterns = [
        r"^10\.", r"^127\.", r"^172\.(1[6-9]|2\d|3[01])\.", r"^192\.168\.",
        r"^::1$", r"^fe80:", r"^fc00:", r"^fd00:",
    ]
    for pat in private_patterns:
        if re.match(pat, ip):
            return "Local Network", "🏠"

    try:
        resp = http_session.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            country = data.get("country", "Unknown")
            cc = data.get("countryCode", "").lower()
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
    except Exception as e:
        conn.rollback()
        log.error(f"Error creating temp session: {e}")
        raise
    finally:
        conn.close()
    log.info(f"Temp session created for IP {ip} ({country}) — expires in {app.config['GRACE_PERIOD']}s")
    return get_temp_session(ip)


def terminate_connection(ip):
    conn = get_db()
    conn.execute("UPDATE temp_sessions SET active = 0 WHERE ip = ?", (ip,))
    conn.execute("DELETE FROM active_streams WHERE ip = ?", (ip,))
    conn.commit()
    conn.close()


def ban_ip(ip, reason="Grace period expired"):
    now = time.time()
    conn = get_db()
    session = conn.execute("SELECT * FROM temp_sessions WHERE ip = ?", (ip,)).fetchone()
    country = session["country"] if session else "Unknown"
    flag = session["flag"] if session else ""

    terminate_connection(ip)

    try:
        conn.execute(
            """INSERT OR REPLACE INTO blacklist (ip, label, country, flag, reason, banned_at, updated_at)
               VALUES (?, '', ?, ?, ?, ?, ?)""",
            (ip, country, flag, reason, now, now),
        )
        conn.commit()
        log.info(f"IP {ip} has been banned. Reason: {reason}")
    except Exception as e:
        conn.rollback()
        log.error(f"Error banning IP {ip}: {e}")
    finally:
        conn.close()


def authenticate(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if auth == f"Bearer {app.config['ADMIN_PASSWORD']}":
            return f(*args, **kwargs)
        token = request.cookies.get("admin_token")
        if token == app.config["ADMIN_PASSWORD"]:
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


# ===================================================================
# واجهات لوحة التحكم البرمجية (API Endpoints)
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
    conn = get_db()
    now = time.time()

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

    wl_rows = conn.execute("SELECT * FROM whitelist ORDER BY updated_at DESC").fetchall()
    whitelist = [{
        "id": r["id"], "ip": r["ip"], "label": r["label"],
        "country": r["country"], "flag": r["flag"], "created_at": r["created_at"]
    } for r in wl_rows]

    bl_rows = conn.execute("SELECT * FROM blacklist ORDER BY banned_at DESC").fetchall()
    blacklist = [{
        "id": r["id"], "ip": r["ip"], "label": r["label"], "country": r["country"],
        "flag": r["flag"], "reason": r["reason"], "banned_at": r["banned_at"]
    } for r in bl_rows]

    stream_count = conn.execute("SELECT COUNT(*) as cnt FROM active_streams").fetchone()["cnt"]
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
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    if not ip: return jsonify({"error": "IP required"}), 400

    now = time.time()
    conn = get_db()
    session = conn.execute("SELECT * FROM temp_sessions WHERE ip = ?", (ip,)).fetchone()
    country = session["country"] if session else "Unknown"
    flag = session["flag"] if session else ""

    try:
        conn.execute(
            """INSERT OR REPLACE INTO whitelist (ip, label, country, flag, created_at, updated_at)
               VALUES (?, '', ?, ?, ?, ?)""", (ip, country, flag, now, now),
        )
        conn.execute("UPDATE temp_sessions SET active = 0 WHERE ip = ?", (ip,))
        conn.execute("DELETE FROM active_streams WHERE ip = ?", (ip,))
        conn.commit()
        return jsonify({"status": "approved", "ip": ip})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/block", methods=["POST"])
@authenticate
def api_block():
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    if not ip: return jsonify({"error": "IP required"}), 400
    ban_ip(ip, data.get("reason", "Manually blocked by admin"))
    return jsonify({"status": "blocked", "ip": ip})


@app.route("/api/unban", methods=["POST"])
@authenticate
def api_unban():
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    if not ip: return jsonify({"error": "IP required"}), 400

    conn = get_db()
    try:
        conn.execute("DELETE FROM blacklist WHERE ip = ?", (ip,))
        conn.commit()
        return jsonify({"status": "unbanned", "ip": ip})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/rename", methods=["POST"])
@authenticate
def api_rename():
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    label = data.get("label", "").strip()
    if not ip: return jsonify({"error": "IP required"}), 400

    table = "whitelist" if data.get("list", "whitelist") == "whitelist" else "blacklist"
    conn = get_db()
    try:
        conn.execute(f"UPDATE {table} SET label = ?, updated_at = ? WHERE ip = ?", (label, time.time(), ip))
        conn.commit()
        return jsonify({"status": "renamed", "ip": ip, "label": label})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ===================================================================
# محرك بث الـ HLS والـ TS المطور (IPTV Proxy Engine)
# ===================================================================

@app.route("/stream")
def proxy_stream():
    client_ip = get_client_ip()

    if is_blacklisted(client_ip):
        abort(403, "Access denied — Banned.")

    if not is_whitelisted(client_ip):
        session = get_temp_session(client_ip)
        if not session or session["active"] == 0:
            session = create_temp_session(client_ip)
        if time.time() > session["expires_at"]:
            ban_ip(client_ip, "Grace period expired")
            abort(403, "Access denied — Expired.")

    sub_param = request.args.get("sub")
    source_url = base64.urlsafe_b64decode(sub_param.encode()).decode() if sub_param else app.config["SOURCE_URL"]

    # معالجة ملف الـ m3u8 الرئيسي وإعادة صياغة الروابط داخلياً
    if ".m3u8" in source_url.lower() or request.args.get("type") == "m3u8":
        try:
            resp = http_session.get(source_url, timeout=10)
            resp.raise_for_status()
            playlist_data = resp.text
            
            parsed_url = urlparse(source_url)
            base_dir_url = f"{parsed_url.scheme}://{parsed_url.netloc}{os.path.dirname(parsed_url.path)}/"
            
            rewritten_playlist = []
            for line in playlist_data.splitlines():
                line = line.strip()
                if not line: continue
                
                if line.startswith("#"):
                    if "URI=" in line:
                        match = re.search(r'URI="([^"]+)"', line)
                        if match:
                            abs_uri = urljoin(base_dir_url, match.group(1))
                            encoded_uri = base64.urlsafe_b64encode(abs_uri.encode()).decode()
                            line = line.replace(f'URI="{match.group(1)}"', f'URI="/stream?sub={encoded_uri}"')
                    rewritten_playlist.append(line)
                else:
                    abs_uri = urljoin(base_dir_url, line)
                    encoded_uri = base64.urlsafe_b64encode(abs_uri.encode()).decode()
                    proxy_uri = f"/stream?sub={encoded_uri}" if ".m3u8" in line.lower() else f"/hls/segment?url={encoded_uri}"
                    rewritten_playlist.append(proxy_uri)
            
            response = Response("\n".join(rewritten_playlist), mimetype="application/vnd.apple.mpegurl")
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response
        except Exception as e:
            log.error(f"HLS proxy error: {e}")
            abort(502, "HLS Fetch failed.")

    # معالجة البث إذا كان من نوع TS المستمر
    else:
        def generate_ts():
            session_id = uuid.uuid4().hex
            conn = get_db()
            try:
                conn.execute("INSERT INTO active_streams (ip, session_id, started_at, thread_id) VALUES (?, ?, ?, ?)",
                             (client_ip, session_id, time.time(), threading.current_thread().name))
                conn.commit()
            except Exception: pass
            finally: conn.close()

            try:
                resp = http_session.get(source_url, stream=True, timeout=20)
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        if is_blacklisted(client_ip): break
                        yield chunk
            except Exception: pass
            finally:
                conn = get_db()
                conn.execute("DELETE FROM active_streams WHERE ip = ? AND session_id = ?", (client_ip, session_id))
                conn.commit()
                conn.close()

        response = Response(stream_with_context(generate_ts()), mimetype="video/mp2t")
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response


@app.route("/hls/segment")
def proxy_segment():
    """
    (هنا التعديل الجوهري لحل مشكلة الأندرويد)
    يتم سحب قطعة الفيديو كاملة وإرسالها بـ Content-Length ثابت ليفهمها الأندرويد فوراً بدون تقطيع.
    """
    client_ip = get_client_ip()
    if is_blacklisted(client_ip): abort(403)
    
    if not is_whitelisted(client_ip):
        session = get_temp_session(client_ip)
        if not session or time.time() > session["expires_at"]:
            ban_ip(client_ip, "Grace period expired")
            abort(403)

    encoded_url = request.args.get("url")
    if not encoded_url: abort(400)

    try:
        target_url = base64.urlsafe_b64decode(encoded_url.encode()).decode()
        # سحب الملف بالكامل وتمريره مباشرة لمنع الـ Loop والتقطيع في الأندرويد
        resp = http_session.get(target_url, timeout=15)
        resp.raise_for_status()
        
        response = Response(resp.content, mimetype=resp.headers.get("Content-Type", "video/mp2t"))
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response
    except Exception as e:
        log.error(f"Segment fetch failed: {e}")
        abort(502)


# ===================================================================
# واجهة العرض الرئيسية ونظام التشغيل بالخلفية
# ===================================================================

HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")

@app.route("/")
def index():
    if os.path.exists(HTML_FILE):
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            return render_template_string(f.read())
    return "dashboard.html not found.", 404


def cleanup_worker():
    while True:
        try:
            now = time.time()
            conn = get_db()
            expired = conn.execute("SELECT ip FROM temp_sessions WHERE active = 1 AND expires_at < ?"
                                   " AND ip NOT IN (SELECT ip FROM whitelist) AND ip NOT IN (SELECT ip FROM blacklist)", (now,)).fetchall()
            for s in expired:
                ban_ip(s["ip"], "Grace period expired")
            conn.close()
        except Exception: pass
        time.sleep(15)


def main():
    init_db()
    threading.Thread(target=cleanup_worker, daemon=True, name="cleanup-worker").start()
    log.info(f"Starting High-Performance IPTV Proxy on 0.0.0.0:5000")
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=False, threaded=True)

if __name__ == "__main__":
    main()
