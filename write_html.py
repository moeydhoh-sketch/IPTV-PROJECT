#!/usr/bin/env python3
"""Write the dashboard.html file."""
import os

def main():
    # Base path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    outpath = os.path.join(base_dir, "dashboard.html")
    
    html = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>IPTV Proxy — لوحة التحكم</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet" />
<style>
* { font-family: 'Cairo', 'Segoe UI', sans-serif; margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: #0a0e1a;
  min-height: 100vh;
  overflow-x: hidden;
}
.bg-grid {
  background-image:
    linear-gradient(rgba(0,255,255,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,255,255,0.05) 1px, transparent 1px);
  background-size: 60px 60px;
  position: fixed;
  inset: 0;
  z-index: 0;
  animation: gridPulse 8s ease-in-out infinite;
}
@keyframes gridPulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.7; }
}
.glow-orb {
  position: fixed;
  border-radius: 50%;
  filter: blur(120px);
  pointer-events: none;
  z-index: 0;
}
.glow-orb-1 {
  width: 500px; height: 500px;
  background: radial-gradient(circle, rgba(0,255,255,0.15), transparent);
  top: -150px; left: -100px;
  animation: orbFloat1 12s ease-in-out infinite;
}
.glow-orb-2 {
  width: 400px; height: 400px;
  background: radial-gradient(circle, rgba(168,85,247,0.12), transparent);
  bottom: -100px; right: -100px;
  animation: orbFloat2 15s ease-in-out infinite;
}
.glow-orb-3 {
  width: 350px; height: 350px;
  background: radial-gradient(circle, rgba(255,165,0,0.08), transparent);
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  animation: orbFloat3 10s ease-in-out infinite;
}
@keyframes orbFloat1 {
  0%, 100% { transform: translate(0,0) scale(1); }
  33% { transform: translate(80px,60px) scale(1.1); }
  66% { transform: translate(-40px,30px) scale(0.9); }
}
@keyframes orbFloat2 {
  0%, 100% { transform: translate(0,0) scale(1); }
  33% { transform: translate(-60px,-40px) scale(1.15); }
  66% { transform: translate(30px,-20px) scale(0.85); }
}
@keyframes orbFloat3 {
  0%, 100% { transform: translate(-50%,-50%) scale(1); opacity: 0.5; }
  50% { transform: translate(-50%,-50%) scale(1.3); opacity: 0.8; }
}
.glass {
  background: rgba(15,23,42,0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(0,255,255,0.12);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.glass-card {
  background: rgba(15,23,42,0.6);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(0,255,255,0.1);
  border-radius: 1rem;
  box-shadow: 0 4px 24px rgba(0,0,0,0.3);
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
}
.glass-card:hover {
  border-color: rgba(0,255,255,0.25);
  box-shadow: 0 8px 40px rgba(0,255,255,0.1);
  transform: translateY(-2px);
}
@keyframes glowPulse {
  0%, 100% { box-shadow: 0 0 5px rgba(255,165,0,0.3), 0 0 10px rgba(255,165,0,0.2); }
  50% { box-shadow: 0 0 15px rgba(255,165,0,0.6), 0 0 30px rgba(255,165,0,0.3); }
}
@keyframes glowPulseRed {
  0%, 100% { box-shadow: 0 0 5px rgba(255,0,0,0.4), 0 0 15px rgba(255,0,0,0.3); }
  50% { box-shadow: 0 0 20px rgba(255,0,0,0.8), 0 0 40px rgba(255,0,0,0.4); }
}
.glow-timer { animation: glowPulse 2s ease-in-out infinite; }
.glow-timer-danger { animation: glowPulseRed 0.8s ease-in-out infinite; }
.glow-green { box-shadow: 0 0 10px rgba(34,197,94,0.3), 0 0 20px rgba(34,197,94,0.1); }
@keyframes glitch {
  0% { transform: translate(0); }
  20% { transform: translate(-2px, 1px); }
  40% { transform: translate(2px, -1px); }
  60% { transform: translate(-1px, -1px); }
  80% { transform: translate(1px, 2px); }
  100% { transform: translate(0); }
}
.glitch-effect { animation: glitch 0.3s ease-in-out infinite; }
@keyframes rowEnter {
  from { opacity: 0; transform: translateY(-20px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes rowExit {
  from { opacity: 1; transform: translateX(0) scale(1); max-height: 80px; }
  to { opacity: 0; transform: translateX(40px) scale(0.8); max-height: 0; padding: 0; margin: 0; }
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}
.anim-enter { animation: rowEnter 0.4s cubic-bezier(0.4,0,0.2,1) forwards; }
.anim-exit { animation: rowExit 0.5s cubic-bezier(0.4,0,0.2,1) forwards; overflow: hidden; }
.anim-fade-in { animation: fadeInUp 0.5s ease-out forwards; }
.checkbox-custom {
  appearance: none;
  -webkit-appearance: none;
  width: 22px; height: 22px;
  border: 2px solid rgba(0,255,255,0.3);
  border-radius: 6px;
  background: rgba(0,255,255,0.05);
  cursor: pointer;
  position: relative;
  transition: all 0.2s cubic-bezier(0.4,0,0.2,1);
}
.checkbox-custom:checked {
  background: #00ffff;
  border-color: #00ffff;
  transform: scale(1.15);
  box-shadow: 0 0 15px rgba(0,255,255,0.5);
}
.checkbox-custom:checked::after {
  content: '\2713';
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0a0e1a;
  font-weight: 900;
  font-size: 14px;
}
.checkbox-custom:active { transform: scale(0.85); }
.rename-input {
  background: rgba(0,255,255,0.08);
  border: 1px solid #00ffff;
  border-radius: 6px;
  padding: 2px 8px;
  color: #fff;
  outline: none;
  width: 120px;
  font-size: 0.875rem;
  transition: all 0.2s;
}
.rename-input:focus { box-shadow: 0 0 15px rgba(0,255,255,0.3); }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: rgba(15,23,42,0.5); }
::-webkit-scrollbar-thumb { background: rgba(0,255,255,0.2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,255,255,0.4); }
.header-glow { text-shadow: 0 0 20px rgba(0,255,255,0.3), 0 0 40px rgba(0,255,255,0.1); }
.stat-number {
  font-size: 2rem;
  font-weight: 900;
  background: linear-gradient(135deg, #00ffff, #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.border-pulse { border-color: rgba(255,165,0,0.3); animation: borderPulse 2s ease-in-out infinite; }
@keyframes borderPulse {
  0%, 100% { border-color: rgba(255,165,0,0.2); }
  50% { border-color: rgba(255,165,0,0.5); }
}
.spinner {
  width: 24px; height: 24px;
  border: 3px solid rgba(0,255,255,0.1);
  border-top-color: #00ffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.toast {
  position: fixed;
  bottom: 30px; left: 50%;
  transform: translateX(-50%) translateY(100px);
  background: rgba(15,23,42,0.95);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(0,255,255,0.2);
  border-radius: 12px;
  padding: 14px 28px;
  color: white;
  font-weight: 600;
  z-index: 9999;
  opacity: 0;
  transition: all 0.5s cubic-bezier(0.4,0,0.2,1);
  pointer-events: none;
}
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.toast.success { border-color: rgba(34,197,94,0.5); box-shadow: 0 0 20px rgba(34,197,94,0.2); }
.toast.error { border-color: rgba(239,68,68,0.5); box-shadow: 0 0 20px rgba(239,68,68,0.2); }
.toast.info { border-color: rgba(0,255,255,0.5); box-shadow: 0 0 20px rgba(0,255,255,0.2); }
.login-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.login-box { width: 100%; max-width: 420px; padding: 40px; }
.login-title {
  font-size: 1.5rem;
  font-weight: 800;
  text-align: center;
  margin-bottom: 8px;
  background: linear-gradient(135deg, #00ffff, #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.login-subtitle { text-align: center; color: rgba(148,163,184,0.7); margin-bottom: 32px; font-size: 0.9rem; }
.login-input {
  width: 100%;
  padding: 14px 18px;
  background: rgba(15,23,42,0.8);
  border: 1px solid rgba(0,255,255,0.15);
  border-radius: 10px;
  color: white;
  font-size: 1rem;
  transition: all 0.3s;
  outline: none;
  direction: ltr;
  text-align: left;
}
.login-input:focus { border-color: #00ffff; box-shadow: 0 0 20px rgba(0,255,255,0.15); }
.login-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #00ffff, #0891b2);
  border: none;
  border-radius: 10px;
  color: #0a0e1a;
  font-weight: 800;
  font-size: 1.05rem;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 16px;
}
.login-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,255,255,0.3); }
.login-btn:active { transform: scale(0.97); }
.section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.section-line { flex: 1; height: 1px; background: linear-gradient(90deg, rgba(0,255,255,0.3), transparent); }
.section-title { font-size: 1.2rem; font-weight: 800; color: #e2e8f0; white-space: nowrap; }
.section-icon { font-size: 1.3rem; }
.empty-state { text-align: center; padding: 40px 20px; color: rgba(148,163,184,0.5); }
.empty-state-icon { font-size: 3rem; margin-bottom: 12px; }
.table-wrapper { overflow-x: auto; border-radius: 0.75rem; }
table { width: 100%; border-collapse: collapse; }
th {
  padding: 12px 16px;
  text-align: center;
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgba(148,163,184,0.7);
  border-bottom: 1px solid rgba(0,255,255,0.08);
  white-space: nowrap;
}
td {
  padding: 12px 16px;
  text-align: center;
  border-bottom: 1px solid rgba(0,255,255,0.04);
  font-size: 0.9rem;
  color: #cbd5e1;
  white-space: nowrap;
  transition: all 0.3s;
}
tr:hover td { background: rgba(0,255,255,0.03); }
.btn-action {
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
}
.btn-approve { background: rgba(34,197,94,0.15); color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
.btn-approve:hover { background: rgba(34,197,94,0.25); box-shadow: 0 0 20px rgba(34,197,94,0.2); transform: translateY(-1px); }
.btn-block { background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
.btn-block:hover { background: rgba(239,68,68,0.25); box-shadow: 0 0 20px rgba(239,68,68,0.2); transform: translateY(-1px); }
.btn-unban { background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }
.btn-unban:hover { background: rgba(59,130,246,0.25); box-shadow: 0 0 20px rgba(59,130,246,0.2); transform: translateY(-1px); }
.btn-rename { background: rgba(168,85,247,0.15); color: #a855f7; border: 1px solid rgba(168,85,247,0.3); }
.btn-rename:hover { background: rgba(168,85,247,0.25); }
.country-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  background: rgba(0,255,255,0.06);
  border-radius: 20px;
  font-size: 0.8rem;
}
.ip-mono { font-family: 'Courier New', monospace; font-weight: 600; font-size: 0.82rem; color: #e2e8f0; letter-spacing: 0.03em; }
@media (max-width: 768px) {
  .glass-card { padding: 16px !important; }
  .stat-number { font-size: 1.5rem; }
  th, td { padding: 8px 10px; font-size: 0.78rem; }
  .login-box { padding: 24px; margin: 16px; }
}
.logout-btn {
  padding: 8px 20px;
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: 8px;
  color: #ef4444;
  font-weight: 700;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.3s;
}
.logout-btn:hover { background: rgba(239,68,68,0.2); box-shadow: 0 0 15px rgba(239,68,68,0.15); }
.checkbox-label { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
.checkbox-text { font-size: 0.85rem; color: #94a3b8; transition: color 0.3s; }
.checkbox-custom:checked ~ .checkbox-text { color: #00ffff; }
.stat-icon-bg { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; }
</style>
</head>
<body>
"""

    with open(outpath, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Part 1 written to {outpath}")

if __name__ == "__main__":
    main()
