#!/usr/bin/env python3
"""Append the body HTML to dashboard.html."""
import os

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    outpath = os.path.join(base_dir, "dashboard.html")
    
    body_html = """
<!-- Glow Orbs -->
<div class="glow-orb glow-orb-1"></div>
<div class="glow-orb glow-orb-2"></div>
<div class="glow-orb glow-orb-3"></div>
<div class="bg-grid"></div>

<!-- Toast Notification -->
<div id="toast" class="toast"></div>

<!-- ============================================================ -->
<!-- LOGIN SCREEN -->
<!-- ============================================================ -->
<div id="loginScreen" class="login-container" style="position: relative; z-index: 10;">
  <div class="glass login-box" style="border-radius: 20px;">
    <div style="text-align: center; margin-bottom: 16px;">
      <span style="font-size: 3rem;">🛡️</span>
    </div>
    <div class="login-title">IPTV Proxy Dashboard</div>
    <div class="login-subtitle">تأمين البث الخاص بك — أدخل كلمة المرور</div>
    <form id="loginForm" onsubmit="return handleLogin(event)">
      <input type="password" id="passwordInput" class="login-input" placeholder="••••••••" autofocus />
      <button type="submit" class="login-btn">دخول <span style="margin-right: 8px;">→</span></button>
      <div id="loginError" style="color: #ef4444; font-size: 0.85rem; text-align: center; margin-top: 12px; display: none;">❌ كلمة المرور غير صحيحة</div>
    </form>
  </div>
</div>

<!-- ============================================================ -->
<!-- MAIN DASHBOARD -->
<!-- ============================================================ -->
<div id="mainDashboard" style="display: none; position: relative; z-index: 10; padding: 20px; max-width: 1400px; margin: 0 auto;">

  <!-- Header -->
  <header class="glass-card" style="padding: 20px 28px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
    <div style="display: flex; align-items: center; gap: 14px;">
      <span style="font-size: 2rem;">🛡️</span>
      <div>
        <h1 class="header-glow" style="font-size: 1.4rem; font-weight: 900; color: #e2e8f0; margin: 0;">IPTV Proxy</h1>
        <p style="font-size: 0.75rem; color: rgba(148,163,184,0.6); margin: 0;">نظام تأمين البث مع تحكم كامل</p>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 16px;">
      <span id="onlineBadge" style="display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.2); border-radius: 20px; font-size: 0.8rem; color: #22c55e;">
        <span style="width: 8px; height: 8px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.5); animation: glowPulse 2s infinite;"></span>
        متصل
      </span>
      <button onclick="handleLogout()" class="logout-btn">تسجيل الخروج</button>
    </div>
  </header>

  <!-- Stats Cards -->
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px;">
    <div class="glass-card anim-fade-in" style="padding: 20px; display: flex; align-items: center; gap: 16px;" style="animation-delay: 0.05s;">
      <div class="stat-icon-bg" style="background: rgba(0,255,255,0.1);">📡</div>
      <div>
        <div style="font-size: 0.75rem; color: rgba(148,163,184,0.6);">المتصلون الآن</div>
        <div class="stat-number" id="statActive">0</div>
      </div>
    </div>
    <div class="glass-card anim-fade-in" style="padding: 20px; display: flex; align-items: center; gap: 16px;" style="animation-delay: 0.1s;">
      <div class="stat-icon-bg" style="background: rgba(34,197,94,0.1);">✅</div>
      <div>
        <div style="font-size: 0.75rem; color: rgba(148,163,184,0.6);">المعتمدون</div>
        <div class="stat-number" id="statWhitelist">0</div>
      </div>
    </div>
    <div class="glass-card anim-fade-in" style="padding: 20px; display: flex; align-items: center; gap: 16px;" style="animation-delay: 0.15s;">
      <div class="stat-icon-bg" style="background: rgba(239,68,68,0.1);">🚫</div>
      <div>
        <div style="font-size: 0.75rem; color: rgba(148,163,184,0.6);">المحظورون</div>
        <div class="stat-number" id="statBlacklist">0</div>
      </div>
    </div>
    <div class="glass-card anim-fade-in" style="padding: 20px; display: flex; align-items: center; gap: 16px;" style="animation-delay: 0.2s;">
      <div class="stat-icon-bg" style="background: rgba(168,85,247,0.1);">⏱️</div>
      <div>
        <div style="font-size: 0.75rem; color: rgba(148,163,184,0.6);">المهلة (ثواني)</div>
        <div class="stat-number" id="statGracePeriod">180</div>
      </div>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- ACTIVE CONNECTIONS -->
  <!-- ============================================================ -->
  <div class="glass-card" style="padding: 24px; margin-bottom: 24px; border: 1px solid rgba(255,165,0,0.15);">
    <div class="section-header">
      <span class="section-icon">🔴</span>
      <span class="section-title">المتصلون حالياً — قيد المراجعة</span>
      <span id="activeCount" style="background: rgba(255,165,0,0.15); color: #f59e0b; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;">0</span>
      <div class="section-line"></div>
      <button onclick="clearExpired()" style="padding: 6px 14px; background: rgba(255,165,0,0.1); border: 1px solid rgba(255,165,0,0.2); border-radius: 8px; color: #f59e0b; font-size: 0.75rem; font-weight: 700; cursor: pointer; transition: all 0.3s; white-space: nowrap;">مسح المنتهية</button>
    </div>
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>✅ صح</th>
            <th>🚫 حظر</th>
            <th>🌐 IP</th>
            <th>📍 الدولة</th>
            <th>⏱️ الوقت المتبقي</th>
          </tr>
        </thead>
        <tbody id="activeTableBody">
          <!-- Dynamic rows -->
        </tbody>
      </table>
    </div>
    <div id="activeEmpty" class="empty-state">
      <div class="empty-state-icon">📡</div>
      <div>لا يوجد متصلون حاليًا</div>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- WHITELIST -->
  <!-- ============================================================ -->
  <div class="glass-card" style="padding: 24px; margin-bottom: 24px;">
    <div class="section-header">
      <span class="section-icon">✅</span>
      <span class="section-title">قائمة الصح — المعتمدون</span>
      <span id="wlCount" style="background: rgba(34,197,94,0.15); color: #22c55e; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;">0</span>
      <div class="section-line"></div>
    </div>
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>🌐 IP</th>
            <th>📍 الدولة</th>
            <th>🏷️ التسمية</th>
            <th>📅 تاريخ الإضافة</th>
            <th>⚡ إجراء</th>
          </tr>
        </thead>
        <tbody id="whitelistTableBody">
          <!-- Dynamic rows -->
        </tbody>
      </table>
    </div>
    <div id="whitelistEmpty" class="empty-state">
      <div class="empty-state-icon">✅</div>
      <div>لا يوجد معتمدون بعد</div>
    </div>
  </div>

  <!-- ============================================================ -->
  <!-- BLACKLIST -->
  <!-- ============================================================ -->
  <div class="glass-card" style="padding: 24px; margin-bottom: 24px;">
    <div class="section-header">
      <span class="section-icon">🚫</span>
      <span class="section-title">قائمة المحظورين</span>
      <span id="blCount" style="background: rgba(239,68,68,0.15); color: #ef4444; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;">0</span>
      <div class="section-line"></div>
    </div>
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>🌐 IP</th>
            <th>📍 الدولة</th>
            <th>🏷️ التسمية (انقر مرتين)</th>
            <th>📅 تاريخ الحظر</th>
            <th>⚡ إجراء</th>
          </tr>
        </thead>
        <tbody id="blacklistTableBody">
          <!-- Dynamic rows -->
        </tbody>
      </table>
    </div>
    <div id="blacklistEmpty" class="empty-state">
      <div class="empty-state-icon">🚫</div>
      <div>ممتاز! لا يوجد محظورون</div>
    </div>
  </div>

  <footer style="text-align: center; padding: 24px; color: rgba(148,163,184,0.4); font-size: 0.75rem;">
    IPTV Authentication Proxy Server — جميع الحقوق محفوظة © 2026
  </footer>
</div>

<script>
// ===================================================================
// STATE
// ===================================================================
let pollInterval = null;
let countdownIntervals = {};
const API_BASE = '';
let isAuthenticated = false;

// ===================================================================
// TOAST
// ===================================================================
function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = 'toast ' + type + ' show';
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

// ===================================================================
// LOGIN
// ===================================================================
async function handleLogin(e) {
  e.preventDefault();
  const password = document.getElementById('passwordInput').value;
  const errorDiv = document.getElementById('loginError');
  
  try {
    const resp = await fetch(API_BASE + '/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (resp.ok) {
      document.getElementById('loginScreen').style.display = 'none';
      document.getElementById('mainDashboard').style.display = 'block';
      isAuthenticated = true;
      errorDiv.style.display = 'none';
      startPolling();
      showToast('✅ تم تسجيل الدخول بنجاح', 'success');
    } else {
      errorDiv.style.display = 'block';
      document.getElementById('passwordInput').value = '';
      document.getElementById('passwordInput').focus();
      showToast('❌ كلمة المرور غير صحيحة', 'error');
    }
  } catch (err) {
    errorDiv.style.display = 'block';
    errorDiv.textContent = '❌ خطأ في الاتصال بالخادم';
  }
}

function handleLogout() {
  isAuthenticated = false;
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  // Clear all countdown intervals
  Object.keys(countdownIntervals).forEach(k => {
    clearInterval(countdownIntervals[k]);
    delete countdownIntervals[k];
  });
  document.getElementById('mainDashboard').style.display = 'none';
  document.getElementById('loginScreen').style.display = 'flex';
  document.getElementById('passwordInput').value = '';
  document.getElementById('loginError').style.display = 'none';
  showToast('👋 تم تسجيل الخروج', 'info');
}

// ===================================================================
// API HELPERS
// ===================================================================
async function apiFetch(url, options = {}) {
  const resp = await fetch(API_BASE + url, {
    ...options,
    headers: { ...options.headers, 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  });
  if (resp.status === 401) {
    handleLogout();
    throw new Error('Unauthorized');
  }
  return resp.json();
}

// ===================================================================
// POLLING
// ===================================================================
function startPolling() {
  fetchStatus();
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(fetchStatus, 2000);
}

async function fetchStatus() {
  if (!isAuthenticated) return;
  try {
    const data = await apiFetch('/api/status');
    renderDashboard(data);
  } catch (err) {
    // Silently handle
  }
}

// ===================================================================
// RENDER
// ===================================================================
function renderDashboard(data) {
  // Stats
  document.getElementById('statActive').textContent = data.active_connections.length;
  document.getElementById('statWhitelist').textContent = data.whitelist.length;
  document.getElementById('statBlacklist').textContent = data.blacklist.length;
  document.getElementById('statGracePeriod').textContent = data.grace_period;
  document.getElementById('activeCount').textContent = data.active_connections.length;
  document.getElementById('wlCount').textContent = data.whitelist.length;
  document.getElementById('blCount').textContent = data.blacklist.length;

  renderActiveConnections(data);
  renderWhitelist(data);
  renderBlacklist(data);
}

// ===================================================================
// RENDER ACTIVE CONNECTIONS
// ===================================================================
function renderActiveConnections(data) {
  const tbody = document.getElementById('activeTableBody');
  const empty = document.getElementById('activeEmpty');
  const now = data.now || (Date.now() / 1000);

  // Collect existing row IDs to detect removals
  const existingIds = new Set();
  tbody.querySelectorAll('tr[data-ip]').forEach(tr => existingIds.add(tr.dataset.ip));

  const currentIps = new Set(data.active_connections.map(c => c.ip));

  // Remove rows that are no longer active (with animation)
  existingIds.forEach(ip => {
    if (!currentIps.has(ip)) {
      const tr = tbody.querySelector(`tr[data-ip="${ip}"]`);
      if (tr) {
        tr.classList.add('anim-exit');
        setTimeout(() => { if (tr.parentNode) tr.remove(); }, 500);
        // Clear countdown
        if (countdownIntervals[ip]) {
          clearInterval(countdownIntervals[ip]);
          delete countdownIntervals[ip];
        }
      }
    }
  });

  // Render active rows
  const activeIps = data.active_connections.map(c => c.ip);
  const html = data.active_connections.map(conn => {
    const remaining = conn.remaining;
    const mins = Math.floor(remaining / 60);
    const secs = remaining % 60;
    const isDanger = remaining <= 30;
    const timerClass = isDanger ? 'glow-timer-danger' : 'glow-timer';
    
    return `<tr data-ip="${conn.ip}" class="anim-enter" style="transition: all 0.3s;">
      <td>
        <label class="checkbox-label">
          <input type="checkbox" class="checkbox-custom" onchange="approveIP('${conn.ip}')" />
          <span class="checkbox-text">صح</span>
        </label>
      </td>
      <td>
        <button class="btn-action btn-block" onclick="blockIP('${conn.ip}')">حظر</button>
      </td>
      <td><span class="ip-mono">${conn.ip}</span></td>
      <td><span class="country-badge">${conn.flag} ${conn.country}</span></td>
      <td>
        <span class="countdown-timer ${timerClass}" id="timer-${conn.ip}" data-expires="${conn.expires_at}" style="display: inline-block; padding: 4px 14px; border-radius: 20px; font-weight: 700; font-size: 0.9rem; color: ${isDanger ? '#ef4444' : '#f59e0b'}; background: ${isDanger ? 'rgba(239,68,68,0.1)' : 'rgba(255,165,0,0.1)'}">
          ${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}
        </span>
      </td>
    </tr>`;
  }).join('');

  // Only replace if content has changed
  if (html) {
    tbody.innerHTML = html;
    empty.style.display = 'none';
    tbody.style.display = '';
  } else {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    tbody.style.display = 'none';
  }

  // Start/update countdowns
  data.active_connections.forEach(conn => {
    startCountdown(conn.ip, conn.expires_at);
  });
}

function startCountdown(ip, expiresAt) {
  if (countdownIntervals[ip]) clearInterval(countdownIntervals[ip]);
  
  function update() {
    const now = Date.now() / 1000;
    let remaining = Math.max(0, Math.floor(expiresAt - now));
    const el = document.getElementById(`timer-${ip}`);
    if (!el) { clearInterval(countdownIntervals[ip]); delete countdownIntervals[ip]; return; }
    
    const mins = Math.floor(remaining / 60);
    const secs = remaining % 60;
    el.textContent = String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
    
    const isDanger = remaining <= 30;
    el.className = `countdown-timer ${isDanger ? 'glow-timer-danger' : 'glow-timer'}`;
    el.style.color = isDanger ? '#ef4444' : '#f59e0b';
    el.style.background = isDanger ? 'rgba(239,68,68,0.1)' : 'rgba(255,165,0,0.1)';
    
    if (remaining <= 0) {
      clearInterval(countdownIntervals[ip]);
      delete countdownIntervals[ip];
    }
  }
  
  update();
  countdownIntervals[ip] = setInterval(update, 1000);
}

// ===================================================================
// RENDER WHITELIST
// ===================================================================
function renderWhitelist(data) {
  const tbody = document.getElementById('whitelistTableBody');
  const empty = document.getElementById('whitelistEmpty');
  
  const existingIds = new Set();
  tbody.querySelectorAll('tr[data-ip]').forEach(tr => existingIds.add(tr.dataset.ip));
  const currentIps = new Set(data.whitelist.map(w => w.ip));

  existingIds.forEach(ip => {
    if (!currentIps.has(ip)) {
      const tr = tbody.querySelector(`tr[data-ip="${ip}"]`);
      if (tr) { tr.classList.add('anim-exit'); setTimeout(() => tr.remove(), 500); }
    }
  });

  const html = data.whitelist.map(w => {
    const dateStr = new Date(w.created_at * 1000).toLocaleDateString('ar-EG', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    return `<tr data-ip="${w.ip}" class="anim-enter" style="transition: all 0.3s;">
      <td><span class="ip-mono">${w.ip}</span></td>
      <td><span class="country-badge">${w.flag} ${w.country}</span></td>
      <td><span class="whitelist-label" id="wlabel-${w.ip}">${w.label || '—'}</span></td>
      <td style="color: rgba(148,163,184,0.6); font-size: 0.8rem;">${dateStr}</td>
      <td>
        <button class="btn-action btn-block" onclick="blockIP('${w.ip}')">حظر</button>
      </td>
    </tr>`;
  }).join('');

  if (html) {
    tbody.innerHTML = html;
    empty.style.display = 'none';
    tbody.style.display = '';
  } else {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    tbody.style.display = 'none';
  }
}

// ===================================================================
// RENDER BLACKLIST
// ===================================================================
function renderBlacklist(data) {
  const tbody = document.getElementById('blacklistTableBody');
  const empty = document.getElementById('blacklistEmpty');
  
  const existingIds = new Set();
  tbody.querySelectorAll('tr[data-ip]').forEach(tr => existingIds.add(tr.dataset.ip));
  const currentIps = new Set(data.blacklist.map(b => b.ip));

  existingIds.forEach(ip => {
    if (!currentIps.has(ip)) {
      const tr = tbody.querySelector(`tr[data-ip="${ip}"]`);
      if (tr) { tr.classList.add('anim-exit'); setTimeout(() => tr.remove(), 500); }
    }
  });

  const html = data.blacklist.map(b => {
    const dateStr = new Date(b.banned_at * 1000).toLocaleDateString('ar-EG', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    return `<tr data-ip="${b.ip}" class="anim-enter glitch-effect" style="transition: all 0.3s;">
      <td><span class="ip-mono">${b.ip}</span></td>
      <td><span class="country-badge">${b.flag} ${b.country}</span></td>
      <td>
        <span class="bl-label" id="blabel-${b.ip}" ondblclick="startRename('${b.ip}')" style="cursor: pointer; padding: 2px 8px; border-radius: 4px; transition: all 0.3s;">${b.label || 'اضغط مرتين للتسمية'}</span>
        <input class="rename-input" id="binput-${b.ip}" style="display: none;" onblur="saveRename('${b.ip}')" onkeydown="if(event.key==='Enter')saveRename('${b.ip}')" />
      </td>
      <td style="color: rgba(148,163,184,0.6); font-size: 0.8rem;">${dateStr}</td>
      <td>
        <button class="btn-action btn-unban" onclick="unbanIP('${b.ip}')">إلغاء الحظر</button>
      </td>
    </tr>`;
  }).join('');

  if (html) {
    tbody.innerHTML = html;
    empty.style.display = 'none';
    tbody.style.display = '';
  } else {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    tbody.style.display = 'none';
  }
}

// ===================================================================
// ACTIONS
// ===================================================================
async function approveIP(ip) {
  try {
    await apiFetch('/api/approve', {
      method: 'POST',
      body: JSON.stringify({ ip }),
    });
    showToast(`✅ تم اعتماد ${ip} بنجاح`, 'success');
    // Animate the checkbox row
    const tr = document.querySelector(`tr[data-ip="${ip}"]`);
    if (tr) {
      tr.classList.add('anim-exit');
      setTimeout(() => { if (tr.parentNode) tr.remove(); }, 500);
    }
  } catch (err) {
    showToast('❌ فشل في الاعتماد', 'error');
  }
}

async function blockIP(ip) {
  try {
    await apiFetch('/api/block', {
      method: 'POST',
      body: JSON.stringify({ ip }),
    });
    showToast(`🚫 تم حظر ${ip}`, 'error');
    const tr = document.querySelector(`tr[data-ip="${ip}"]`);
    if (tr) {
      tr.classList.add('anim-exit');
      setTimeout(() => { if (tr.parentNode) tr.remove(); }, 500);
    }
  } catch (err) {
    showToast('❌ فشل في الحظر', 'error');
  }
}

async function unbanIP(ip) {
  try {
    await apiFetch('/api/unban', {
      method: 'POST',
      body: JSON.stringify({ ip }),
    });
    showToast(`✅ تم إلغاء حظر ${ip}`, 'success');
    const tr = document.querySelector(`tr[data-ip="${ip}"]`);
    if (tr) {
      tr.classList.add('anim-exit');
      setTimeout(() => { if (tr.parentNode) tr.remove(); }, 500);
    }
  } catch (err) {
    showToast('❌ فشل في إلغاء الحظر', 'error');
  }
}

async function clearExpired() {
  try {
    const data = await apiFetch('/api/clear-expired');
    showToast(`🧹 تم مسح ${data.cleared} جلسة منتهية`, 'info');
  } catch (err) {
    showToast('❌ فشل في المسح', 'error');
  }
}

// ===================================================================
// RENAME (Double-click on blacklist)
// ===================================================================
function startRename(ip) {
  const label = document.getElementById(`blabel-${ip}`);
  const input = document.getElementById(`binput-${ip}`);
  if (!label || !input) return;
  label.style.display = 'none';
  input.style.display = 'inline-block';
  input.value = label.textContent === 'اضغط مرتين للتسمية' ? '' : label.textContent;
  input.focus();
  input.select();
}

async function saveRename(ip) {
  const label = document.getElementById(`blabel-${ip}`);
  const input = document.getElementById(`binput-${ip}`);
  if (!label || !input) return;
  
  const newLabel = input.value.trim();
  input.style.display = 'none';
  label.style.display = 'inline';
  
  if (newLabel && newLabel !== label.textContent) {
    try {
      await apiFetch('/api/rename', {
        method: 'POST',
        body: JSON.stringify({ ip, label: newLabel, list: 'blacklist' }),
      });
      label.textContent = newLabel;
      showToast(`🏷️ تم تحديث التسمية لـ ${ip}`, 'info');
    } catch (err) {
      showToast('❌ فشل في تحديث التسمية', 'error');
    }
  }
}

// ===================================================================
// KEYBOARD SHORTCUT — Enter to login
// ===================================================================
document.addEventListener('DOMContentLoaded', function() {
  const pwInput = document.getElementById('passwordInput');
  if (pwInput) pwInput.focus();
});
</script>
</body>
</html>
"""
    
    # Read existing file
    with open(outpath, "r", encoding="utf-8") as f:
        existing = f.read()
    
    # Check if we need to close the open tags
    if "</body>" not in existing:
        # Append the body content
        with open(outpath, "a", encoding="utf-8") as f:
            f.write(body_html)
        print(f"Part 2 appended. Total size: {os.path.getsize(outpath)} bytes")
    else:
        print("File already complete, skipping.")

if __name__ == "__main__":
    main()
