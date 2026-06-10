#!/usr/bin/env python3
"""
IPTV Authentication Proxy Server (النسخة المطورة والمحسنة للأداء العالي)
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
    
    # رابط بث الـ IPTV الخارجي (المنبع)
    SOURCE_URL = os.environ.get(
        "SOURCE_URL",
        "https://live-sstv.apps.skin-knife.com/live/space_toon/index.m3u8"
    )
    
    # كلمة مرور مدير لوحة التحكم
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    
    # فترة السماح للمشاهدين الجدد بالثواني (180 ثانية = 3 دقائق)
    GRACE_PERIOD = int(os.environ.get("GRACE_PERIOD", "180"))
    
    # إعدادات الشبكة والمنفذ
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))
    
    # الحد الأقصى للاتصالات المتزامنة لكل آيبي
    MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "3"))


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# إعداد تتبع الأحداث (Logging) لطباعة العمليات في السيرفر بشكل نظيف
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("IPTVProxy")

# إنشاء مجمع اتصالات ذكي (HTTP Connection Pool) لرفع كفاءة البث وسرعة الاتصال بالمنبع
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
http_session.mount("http://", adapter)
http_session.mount("https://", adapter)
http_session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV-Proxy/2.0"})

# ---------------------------------------------------------------------------
# إدارة قاعدة البيانات (Database Management)
# ---------------------------------------------------------------------------

def get_db():
    """فتح اتصال آمن وسريع بقاعدة بيانات SQLite مخصصة للبث المتعدد."""
    conn = sqlite3.connect(app.config["DATABASE"], timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """إنشاء الجداول اللازمة لحفظ القوائم والزيارات المؤقتة عند بدء تشغيل السيرفر."""
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
# دوال التحقق الجغرافي والآيبيهات والتحكم
# ---------------------------------------------------------------------------

def get_client_ip():
    """استخراج الآيبي الحقيقي للعميل حتى لو كان خلف جدار حماية أو بروكسي في جوجل كلاود."""
    if request.headers.get("X-Forwarded-For"):
        ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
    elif request.headers.get("X-Real-IP"):
        ip = request.headers.get("X-Real-IP").strip()
    else:
        ip = request.remote_addr
    return ip


def get_geo_info(ip):
    """جلب علم ودولة المشاهد بشكل فوري وسريع باستخدام قاعدة بيانات سحابية خفيفة."""
    # استثناء الشبكات المحلية والآيبيهات الخاصة
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
            # توليد إيموجي العلم الخاص بالدولة برمجياً
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
    """إنشاء فترة سماح مؤقتة للمشاهد الجديد تبدأ بالعد التنازلي (3 دقائق)."""
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
    """قطع الاتصال وإغلاق مسارات التدفق فوراً للمشاهد المطرود أو المحظور."""
    conn = get_db()
    conn.execute("UPDATE temp_sessions SET active = 0 WHERE ip = ?", (ip,))
    conn.execute("DELETE FROM active_streams WHERE ip = ?", (ip,))
    conn.commit()
    conn.close()
    log.warning(f"All stream pointers terminated in database for IP {ip}")


def ban_ip(ip, reason="Grace period expired"):
    """نقل العميل تلقائياً إلى قائمة المحظورين وقطع البث عنه نهائياً."""
    now = time.time()
    conn = get_db()
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
        conn.commit()
        log.info(f"IP {ip} has been banned. Reason: {reason}")
    except Exception as e:
        conn.rollback()
        log.error(f"Error banning IP {ip}: {e}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# نظام التحقق وحماية لوحة التحكم (Authentication Decorator)
# ---------------------------------------------------------------------------

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
    """جلب إحصائيات لوحة التحكم بالكامل لتغذية الأنيميشن والحركات التفاعلية."""
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

    bl_rows = conn.execute("SELECT * FROM blacklist ORDER BY banned_at DESC").fetchall()
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
    """تفعيل علامة (صح) يدويًا ونقل المشترك لقائمة المعتمدين فورًا."""
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    if not ip:
        return jsonify({"error": "IP required"}), 400

    now = time.time()
    conn = get_db()
    session = conn.execute("SELECT * FROM temp_sessions WHERE ip = ?", (ip,)).fetchone()
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
        log.info(f"IP {ip} approved and whitelisted.")
        return jsonify({"status": "approved", "ip": ip})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/block", methods=["POST"])
@authenticate
def api_block():
    """حظر المشترك يدويًا من لوحة التحكم وطرده من البث في نفس اللحظة."""
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
    """إلغاء حظر المشترك يدويًا وإتاحته ليتصل مجددًا بفترة سماح جديدة."""
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
    """تسمية المشاهد يدوياً عند الضغط مرتين (Double Click) لحفظه بملف الهوية."""
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get("ip", "").strip()
    label = data.get("label", "").strip()
    list_type = data.get("list", "whitelist")

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


# ===================================================================
# هندسة وإدارة بروكسي البث الذكي (HLS & TS IPTV Engine)
# ===================================================================

@app.route("/stream")
def proxy_stream():
    """
    نقطة بث الـ IPTV الموحدة والملكية.
    - تفحص حالة الآيبي إذا كان معتمداً أو جديداً (فترة الـ 3 دقائق).
    - إذا كان البث الأصلي HLS (.m3u8)، يتم قراءته برمجياً وإعادة صياغة الروابط لتدور عبر السيرفر بشكل مشفر.
    - إذا كان البث الأصلي TS، يتم تسيير ماسورة البيانات بشكل متكامل ومحسّن.
    """
    client_ip = get_client_ip()
    log.info(f"Stream request received from: {client_ip}")

    # التحقق من القائمة السوداء
    if is_blacklisted(client_ip):
        log.warning(f"Connection rejected. Banned IP: {client_ip}")
        abort(403, "Access denied - You are banned.")

    # التحقق من فترة السماح
    if not is_whitelisted(client_ip):
        session = get_temp_session(client_ip)
        if not session or session["active"] == 0:
            session = create_temp_session(client_ip)

        if time.time() > session["expires_at"]:
            ban_ip(client_ip, "Grace period expired")
            abort(403, "Access denied - Grace period expired.")

    # تحديد الرابط الفعلي للبث (سواء كان الرئيسي أو ممرراً للـ Sub-playlists)
    sub_param = request.args.get("sub")
    if sub_param:
        try:
            source_url = base64.urlsafe_b64decode(sub_param.encode()).decode()
        except Exception:
            source_url = app.config["SOURCE_URL"]
    else:
        source_url = app.config["SOURCE_URL"]

    # 1. هندسة البث إذا كان من نوع HLS (.m3u8)
    if ".m3u8" in source_url.lower() or request.args.get("type") == "m3u8":
        try:
            resp = http_session.get(source_url, timeout=10)
            resp.raise_for_status()
            playlist_data = resp.text
            
            parsed_url = urlparse(source_url)
            # استخراج المسار الأساسي لروابط الفهرس لبناء روابط كاملة (Absolute URLs)
            base_dir_url = f"{parsed_url.scheme}://{parsed_url.netloc}{os.path.dirname(parsed_url.path)}/"
            
            rewritten_playlist = []
            for line in playlist_data.splitlines():
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith("#"):
                    # إعادة صياغة الروابط المتداخلة بداخل الوسوم الوصفية (مثل Variant Streams)
                    if "URI=" in line:
                        match = re.search(r'URI="([^"]+)"', line)
                        if match:
                            rel_uri = match.group(1)
                            abs_uri = urljoin(base_dir_url, rel_uri)
                            encoded_uri = base64.urlsafe_b64encode(abs_uri.encode()).decode()
                            proxy_uri = f"/stream?sub={encoded_uri}"
                            line = line.replace(f'URI="{rel_uri}"', f'URI="{proxy_uri}"')
                    rewritten_playlist.append(line)
                else:
                    # هذه روابط ملفات الفيديو المجزأة (.ts) أو قوائم فرعية
                    abs_uri = urljoin(base_dir_url, line)
                    encoded_uri = base64.urlsafe_b64encode(abs_uri.encode()).decode()
                    
                    if ".m3u8" in line.lower():
                        # إذا كانت قائمة فرعية، نعيد توجيهها للـ stream proxy
                        proxy_uri = f"/stream?sub={encoded_uri}"
                    else:
                        # إذا كان ملف فيديو مجزأ، نرسله إلى وحدة معالجة الأجزاء الذكية
                        proxy_uri = f"/hls/segment?url={encoded_uri}"
                    rewritten_playlist.append(proxy_uri)
            
            output_content = "\n".join(rewritten_playlist)
            response = Response(output_content, mimetype="application/vnd.apple.mpegurl")
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response
            
        except Exception as e:
            log.error(f"Error parsing HLS stream source: {e}")
            abort(502, "Failed to proxy HLS playlist source.")

    # 2. هندسة البث إذا كان من نوع TS المستمر (MPEG-TS)
    else:
        def generate_ts():
            session_id = uuid.uuid4().hex
            thread_id = threading.current_thread().name

            # تسجيل الاتصال الفعال في قاعدة البيانات
            conn = get_db()
            try:
                conn.execute(
                    "INSERT INTO active_streams (ip, session_id, started_at, thread_id) VALUES (?, ?, ?, ?)",
                    (client_ip, session_id, time.time(), thread_id),
                )
                conn.commit()
            except Exception as e:
                log.error(f"Failed to record active stream: {e}")
            finally:
                conn.close()

            try:
                resp = http_session.get(source_url, stream=True, timeout=20)
                resp.raise_for_status()

                # بث البيانات بحجم مصفوفة مثالي لتقليل زمن الاستجابة (Latency) وتجنب التقطيع
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        # التحقق السريع في كل ثانية بث، لو المشاهد انحظر يقطع البث عنه فوراً!
                        if is_blacklisted(client_ip):
                            log.warning(f"Active stream killed for blacklisted IP: {client_ip}")
                            break
                        yield chunk
            except Exception as e:
                log.error(f"Stream piping error for {client_ip}: {e}")
            finally:
                # إغلاق الجلسة عند فصل الاتصال
                conn = get_db()
                conn.execute(
                    "DELETE FROM active_streams WHERE ip = ? AND session_id = ?",
                    (client_ip, session_id),
                )
                conn.commit()
                conn.close()
                log.info(f"Streaming thread closed for: {client_ip}")

        response = Response(
            stream_with_context(generate_ts()),
            mimetype="video/mp2t",
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Proxy"] = "IPTV-TS-Proxy"
        return response


@app.route("/hls/segment")
def proxy_segment():
    """
    ممرر أجزاء الفيديو (HLS Segments Proxy) الخاص والمحمي.
    يتم تمرير كل جزء مشفراً بـ Base64، ويفحص الصلاحيات والـ 3 دقائق مع كل جزء لضمان السيطرة التامة.
    """
    client_ip = get_client_ip()

    if is_blacklisted(client_ip):
        abort(403, "Access denied.")

    if not is_whitelisted(client_ip):
        session = get_temp_session(client_ip)
        if not session or session["active"] == 0:
            session = create_temp_session(client_ip)
        if time.time() > session["expires_at"]:
            ban_ip(client_ip, "Grace period expired")
            abort(403, "Access denied - Grace expired.")

    encoded_url = request.args.get("url")
    if not encoded_url:
        abort(400, "Missing segment URL.")

    try:
        target_url = base64.urlsafe_b64decode(encoded_url.encode()).decode()
    except Exception:
        abort(400, "Malformed URL payload.")

    try:
        # سحب الملف المجزأ من المنبع وإرساله للمشاهد بكفاءة عالية
        resp = http_session.get(target_url, stream=True, timeout=15)
        resp.raise_for_status()
        
        content_type = resp.headers.get("Content-Type", "video/mp2t")
        
        def pipe_segment():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    if is_blacklisted(client_ip):
                        break
                    yield chunk

        response = Response(stream_with_context(pipe_segment()), mimetype=content_type)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "public, max-age=3600" # كاش آمن لتسريع التحميل للمشتركين المتزامنين
        return response
    except Exception as e:
        log.error(f"Error serving segment: {e}")
        abort(502, "Segment fetch failed.")


# ===================================================================
# واجهة العرض الرئيسية للمدير (Dashboard Rendering)
# ===================================================================

HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")

@app.route("/")
def index():
    """عرض لوحة التحكم السايبربانك الفخمة والمنسقة بالكامل."""
    if os.path.exists(HTML_FILE):
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            return render_template_string(f.read())
    return "لوحة التحكم (dashboard.html) غير موجودة بجانب الملف الرئيسي.", 404


# ===================================================================
# خيط المعالجة بالخلفية للبوت التلقائي (Background Thread)
# ===================================================================

def cleanup_worker():
    """خيط معالجة موازي يفحص وينظف المشاهدين منتهيي الصلاحية كل 15 ثانية برمجياً."""
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
            log.error(f"Cleanup worker error in background: {e}")
        time.sleep(15)


# ===================================================================
# تشغيل الخادم الرئيسي (Main Engine)
# ===================================================================

def main():
    # تهيئة الجداول في قاعدة البيانات
    init_db()

    # تشغيل بوت التنظيف التلقائي في الخلفية كخيط مستقل (Daemon Thread)
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True, name="cleanup-worker")
    cleanup_thread.start()
    log.info("Background security checker worker started.")

    log.info(f"Starting IPTV High-Performance Auth Proxy on {app.config['HOST']}:{app.config['PORT']}")
    log.info(f"Default Target Source URL: {app.config['SOURCE_URL']}")
    log.info(f"Safety Grace Period: {app.config['GRACE_PERIOD']} seconds")

    # بدء خادم الفلاسك بالأداء العالي وتفعيل خيوط المعالجة المتعددة (Multithreading)
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=False,
        threaded=True,
    )


if __name__ == "__main__":
    main()
