import os
import uuid
import time
import json
import base64
import io
import warnings
from PIL import Image
from flask import Flask, request, jsonify, render_template_string, Response
import google.generativeai as genai

# --- FIX: IGNORE DEPRECATION WARNINGS ---
warnings.filterwarnings("ignore")

# ==========================================
# 👇 API KEYS SETUP 👇
# ==========================================
keys_string = os.environ.get("API_KEYS", "")
API_KEYS = [k.strip() for k in keys_string.replace(',', ' ').replace('\n', ' ').split() if k.strip()]

# --- 💾 DATABASE ---
DB_FILE = "chat_db.json"
def load_db():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f: return json.load(f)
    except: pass
    return {}
def save_db(db):
    try:
        with open(DB_FILE, 'w') as f: json.dump(db, f, indent=2)
    except: pass
user_db = load_db()

current_key_index = 0
app = Flask(__name__)

# --- 🧠 SYSTEM INSTRUCTION ---
SYSTEM_INSTRUCTION = """
ROLE: You are "Student's AI", a professional academic tutor.
RULES:
1. **MATH:** Use LaTeX for formulas ($$ ... $$).
2. **DIAGRAMS:** Use Mermaid.js (```mermaid ... ```).
3. **LANGUAGE:** English by default. Use Tamil/Tanglish ONLY if requested.
4. **FORMAT:** Markdown. Bold key terms.
5. **CODE:** Use Python/Java/C++ blocks. Explain logic briefly.
"""

# --- 🧬 MODEL & FILE HANDLING ---
def get_working_model(key):
    try:
        genai.configure(api_key=key)
        models = list(genai.list_models())
        chat_models = [m for m in models if 'generateContent' in m.supported_generation_methods]
        for m in chat_models:
            if "flash" in m.name.lower() and "1.5" in m.name: return m.name
        for m in chat_models:
            if "pro" in m.name.lower() and "1.5" in m.name: return m.name
        if chat_models: return chat_models[0].name
    except: return None
    return None

def process_image(image_data):
    try:
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]
        image_bytes = base64.b64decode(image_data)
        return Image.open(io.BytesIO(image_bytes))
    except: return None

def generate_with_retry(prompt, image_data=None, file_text=None, history_messages=[]):
    global current_key_index
    if not API_KEYS: return "🚨 API Keys Missing."

    formatted_history = []
    for m in history_messages[-6:]:
        role = "user" if m["role"] == "user" else "model"
        formatted_history.append({"role": role, "parts": [m["content"]]})

    current_parts = []
    if file_text: current_parts.append(f"analyzing file:\n{file_text}\n\n")
    current_parts.append(prompt)
    if image_data:
        img = process_image(image_data)
        if img: current_parts.append(img)

    for i in range(len(API_KEYS)):
        key = API_KEYS[current_key_index]
        model_name = get_working_model(key)
        
        if not model_name:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            continue

        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_INSTRUCTION)
            
            if image_data or file_text:
                response = model.generate_content(current_parts)
            else:
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(prompt)
            return response.text
        except Exception as e:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            time.sleep(1)

    return "⚠️ System Busy. Please try again."

# --- UI TEMPLATE ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, interactive-widget=resizes-content">
    <meta name="theme-color" content="#09090b">
    <title>Student's AI</title>
    
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>window.MathJax = { tex: { inlineMath: [['$', '$']] }, svg: { fontCache: 'global' } };</script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
      mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });
      window.mermaid = mermaid;
    </script>

    <style>
        :root { --bg: #09090b; --card: #18181b; --user-msg: #27272a; --text: #e4e4e7; --text-muted: #a1a1aa; --accent: #fff; --border: #27272a; --hover: #27272a; }
        body.light-mode { --bg: #ffffff; --card: #f4f4f5; --user-msg: #e4e4e7; --text: #09090b; --text-muted: #52525b; --accent: #000; --border: #e4e4e7; --hover: #f4f4f5; }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body, html { margin: 0; padding: 0; height: 100dvh; width: 100%; background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; overflow: hidden; font-size: 16px; transition: background 0.3s ease; }
        i, .fas, .fab, .far { font-family: "Font Awesome 6 Free" !important; font-weight: 900; }

        /* HEADER */
        header { height: 60px; padding: 0 15px; background: var(--bg); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; z-index: 50; position: absolute; top: 0; left: 0; right: 0; }
        .menu-btn { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text); }
        .app-title { font-size: 20px; font-weight: 700; color: var(--text); letter-spacing: -0.5px; }

        /* SIDEBAR (FIXED SMOOTH) */
        #sidebar { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 3000; visibility: hidden; transition: visibility 0.4s; display: flex; }
        #sidebar.open { visibility: visible; }
        .sidebar-content { 
            width: 280px; height: 100%; background: var(--bg); border-right: 1px solid var(--border); 
            transform: translateX(-100%); transition: transform 0.4s cubic-bezier(0.25, 0.8, 0.25, 1); 
            display: flex; flex-direction: column; padding: 20px;
        }
        #sidebar.open .sidebar-content { transform: translateX(0); }
        .sidebar-overlay-gap { flex: 1; background: rgba(0,0,0,0); transition: background 0.4s ease; }
        #sidebar.open .sidebar-overlay-gap { background: rgba(0,0,0,0.5); }

        .new-chat-btn { width: 100%; height: 45px; background: var(--text); color: var(--bg); border: none; border-radius: 10px; font-weight: 600; cursor: pointer; margin-bottom: 20px; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .history-label { color: var(--text-muted); font-size: 12px; font-weight: 600; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }
        #history-list { flex: 1; overflow-y: auto; padding-right: 5px; }
        .history-item { padding: 12px; margin-bottom: 8px; border-radius: 8px; cursor: pointer; color: var(--text); display: flex; justify-content: space-between; font-size: 14px; }
        .history-item:hover { background: var(--card); }
        .history-actions { display: flex; gap: 10px; opacity: 0; }
        .history-item:hover .history-actions { opacity: 1; }
        .sidebar-footer { margin-top: auto; border-top: 1px solid var(--border); padding-top: 15px; }
        .footer-link { display: flex; align-items: center; gap: 10px; padding: 12px; color: var(--text); cursor: pointer; border-radius: 8px; font-weight: 500; }

        /* CHAT AREA */
        #app-container { display: flex; flex-direction: column; height: 100dvh; padding-top: 60px; }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px 15px; padding-bottom: 40px; display: flex; flex-direction: column; gap: 20px; scroll-behavior: smooth; }
        .msg { width: 100%; display: flex; flex-direction: column; opacity: 0; animation: fadeIn 0.4s forwards; }
        @keyframes fadeIn { to { opacity: 1; } }
        
        .user-msg { align-self: flex-end; align-items: flex-end; width: 100%; }
        .user-content { border-radius: 12px; background: var(--user-msg); color: var(--text); padding: 12px 16px; font-size: 17px; max-width: 85%; width: fit-content; margin-left: auto; word-wrap: break-word; }
        
        .ai-msg { align-self: flex-start; align-items: flex-start; width: 100%; }
        .ai-content { width: 100%; font-size: 18px; line-height: 1.8; }
        
        .msg-actions { display: flex; gap: 15px; margin-top: 8px; opacity: 1; font-size: 13px; color: var(--text-muted); }
        .action-icon { cursor: pointer; display: flex; align-items: center; gap: 5px; }
        pre { background: #1e1e1e !important; border-radius: 12px; padding: 15px; overflow-x: auto; margin: 15px 0; border: 1px solid #333; }
        code { font-family: 'JetBrains Mono', monospace; font-size: 14px; }

        /* INPUT AREA */
        .input-wrapper { background: var(--bg); padding: 10px 15px; border-top: 1px solid var(--border); padding-bottom: max(15px, env(safe-area-inset-bottom)); }
        .input-container { background: rgba(20,20,20,0.95); border: 1px solid #333; border-radius: 40px; padding: 8px 10px; display: flex; align-items: flex-end; gap: 12px; }
        textarea { flex: 1; background: transparent; border: none; color: var(--text); font-size: 16px; padding: 12px 0; resize: none; outline: none; max-height: 150px; }
        .send-btn, .plus-btn { width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .send-btn { background: #fff; color: #000; }
        .plus-btn { background: #27272a; color: #aaa; border: 1px solid #333; }

        /* SETTINGS & MODALS */
        #settings-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: var(--bg); z-index: 2000; display: flex; flex-direction: column; transform: translateX(100%); transition: transform 0.4s cubic-bezier(0.25, 0.8, 0.25, 1); overflow-x: hidden !important; }
        #settings-overlay.active { transform: translateX(0); }
        .settings-header { padding: 20px; padding-top: calc(20px + env(safe-area-inset-top)); display: flex; align-items: center; gap: 15px; }
        .settings-option-btn { display: flex; justify-content: space-between; align-items: center; padding: 18px 20px; margin-bottom: 12px; background: var(--card); border: 1px solid var(--border); border-radius: 12px; cursor: pointer; color: var(--text); font-weight: 500; }
        
        .settings-sub-page { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: var(--bg); z-index: 2050; display: flex; flex-direction: column; transform: translateX(100%); transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); }
        .settings-sub-page.active { transform: translateX(0); }
        .sub-header { padding: 20px; padding-top: calc(20px + env(safe-area-inset-top)); display: flex; align-items: center; gap: 15px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }

        /* ONBOARDING & OTHERS */
        #onboarding-overlay { position: fixed; inset: 0; background: #050505; z-index: 3000; display: flex; align-items: center; justify-content: center; }
        #onboarding-overlay.hidden { display: none; }
        .step-content { display: none; } .step-content.active { display: block; }
        .wizard-container { width: 90%; max-width: 450px; text-align: center; }
        .btn-primary { background: #fff; color: #000; border: none; padding: 16px; border-radius: 12px; font-weight: 700; width: 100%; margin-top: 20px; cursor: pointer; }
        .input-field { width: 100%; padding: 18px; border-radius: 12px; border: 1px solid #333; background: #111; color: #fff; text-align: center; outline: none; font-size: 18px; }
        
        /* OTHER UTILS */
        .profile-card { background: var(--card); border-radius: 16px; padding: 20px; display: flex; flex-direction: column; align-items: center; border: 1px solid var(--border); }
        .detail-row { display: flex; justify-content: space-between; width: 100%; padding: 15px 0; border-bottom: 1px solid var(--border); }
        .subject-edit-input { background: var(--bg); color: var(--text); border: 1px solid var(--text); padding: 5px; border-radius: 5px; width: 60%; margin-left: 15px; text-align: right; }
        
        #custom-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: none; align-items: center; justify-content: center; z-index: 9999; }
        .modal-content { background: var(--card); border: 1px solid var(--border); padding: 25px; border-radius: 20px; width: 90%; max-width: 350px; text-align: center; }
        .modal-input { width: 100%; padding: 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--text); margin: 15px 0; outline: none; }
        .m-btn { flex: 1; padding: 12px; border-radius: 10px; border: none; font-weight: 600; cursor: pointer; }
    </style>
</head>
<body>

    <div id="settings-overlay">
        <div id="settings-main-view">
            <div class="settings-header">
                <div class="back-btn" onclick="closeSettings()"><i class="fas fa-arrow-left"></i></div>
                <h2 style="margin:0; font-size:20px; color:var(--text);">Settings</h2>
            </div>

            <div class="settings-search" style="width:90%; margin:0 auto 20px; background:var(--card); padding:12px 20px; border-radius:12px; display:flex; gap:10px; position:relative;">
                <i class="fas fa-search" style="position:absolute; left:15px; top:50%; transform:translateY(-50%); color:var(--text-muted);"></i>
                <input type="text" id="setting-search-input" placeholder="Search settings..." style="width:100%; padding-left:30px; background:transparent; border:none; color:var(--text); outline:none;" oninput="filterSettings(this.value)" onkeydown="if(event.key==='Enter') this.blur()">
                <i class="fas fa-times" id="clear-setting-search" onclick="clearSettingsSearch()" style="position:absolute; right:15px; top:50%; transform:translateY(-50%); cursor:pointer; display:none; color:var(--text-muted);"></i>
            </div>

            <div class="settings-content" style="padding:0 20px;">
                <div class="settings-option-btn" onclick="openSubPage('subpage-profile')">
                    <div style="display:flex; align-items:center; gap:15px;">
                        <div style="width:32px; height:32px; background:var(--bg); border-radius:8px; display:flex; align-items:center; justify-content:center;"><i class="fas fa-user-graduate" style="color:var(--text); font-size:16px;"></i></div>
                        <span>Student Details</span>
                    </div>
                    <i class="fas fa-chevron-right" style="color:var(--text-muted); font-size:14px;"></i>
                </div>
                <div class="settings-option-btn" onclick="openSubPage('subpage-themes')">
                    <div style="display:flex; align-items:center; gap:15px;">
                        <i class="fas fa-palette" style="color:var(--text);"></i>
                        <span>Themes</span>
                    </div>
                    <i class="fas fa-chevron-right" style="color:var(--text-muted); font-size:14px;"></i>
                </div>
            </div>
        </div>

        <div id="subpage-profile" class="settings-sub-page">
            <div class="sub-header">
                <div class="back-btn" onclick="closeSubPage('subpage-profile')"><i class="fas fa-arrow-left"></i></div>
                <h2 style="margin:0; font-size:20px; color:var(--text);">Student Details</h2>
            </div>
            <div class="settings-content" style="padding:0 20px;">
                <div class="profile-card">
                    <div style="position:relative; width:100px; height:100px; margin-bottom:20px;">
                        <img id="settings-pic" src="https://ui-avatars.com/api/?name=User&background=random" style="width:100%; height:100%; border-radius:50%; object-fit:cover; border:2px solid var(--border);">
                        <label for="pic-upload" style="position:absolute; bottom:0; right:0; background:var(--text); color:var(--bg); width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer;"><i class="fas fa-camera"></i></label>
                        <input type="file" id="pic-upload" hidden accept="image/*" onchange="uploadProfilePic(this)">
                    </div>
                    <div class="profile-details" style="width:100%;">
                        <div class="detail-row"><span style="color:var(--text-muted);">Name</span><span id="profile-name" style="font-weight:600;">User</span></div>
                        <div class="detail-row"><span style="color:var(--text-muted);">Education</span><span id="profile-edu" style="font-weight:600;">College</span></div>
                        <div class="detail-row"><span style="color:var(--text-muted);">Standard/Dept</span><span id="profile-std" style="font-weight:600;">AI & DS</span></div>
                        <div class="detail-row"><span style="color:var(--text-muted);">Subject</span><span id="profile-sub" class="editable-subject" onclick="editSubject(this)" style="font-weight:600; cursor:pointer; border-bottom:1px dashed var(--text-muted);">Maths</span></div>
                        <div style="margin-top:10px; color:#ef4444; font-weight:600; cursor:pointer; padding:15px 0; text-align:center;" onclick="handleLogout()">Log Out</div>
                    </div>
                </div>
            </div>
        </div>

        <div id="subpage-themes" class="settings-sub-page">
            <div class="sub-header">
                <div class="back-btn" onclick="closeSubPage('subpage-themes')"><i class="fas fa-arrow-left"></i></div>
                <h2 style="margin:0; font-size:20px; color:var(--text);">Themes</h2>
            </div>
            <div class="settings-content" style="padding:0 20px;">
                <div style="background:var(--card); border-radius:16px; border:1px solid var(--border); overflow:hidden;">
                    <div style="padding:15px 20px; display:flex; gap:15px; cursor:pointer; border-bottom:1px solid var(--border);" onclick="setTheme('light')"><i class="fas fa-sun"></i> <span>Light Mode</span></div>
                    <div style="padding:15px 20px; display:flex; gap:15px; cursor:pointer; border-bottom:1px solid var(--border);" onclick="setTheme('dark')"><i class="fas fa-moon"></i> <span>Dark Mode</span></div>
                    <div style="padding:15px 20px; display:flex; gap:15px; cursor:pointer;" onclick="setTheme('system')"><i class="fas fa-desktop"></i> <span>System Default</span></div>
                </div>
            </div>
        </div>
    </div>

    <div id="onboarding-overlay">
        <div class="wizard-container">
            <div id="step-1" class="step-content active">
                <div style="margin-bottom:20px;"><i class="fas fa-graduation-cap" style="font-size:60px; color:#fff;"></i></div>
                <h1 style="font-size:32px; font-weight:800; color:#fff;">Welcome to<br>Student's AI</h1>
                <p style="color:#a1a1aa; margin-bottom:40px;">Your personal AI tutor designed to simplify learning.</p>
                <button class="btn-primary" onclick="nextStep(2)">Get Started</button>
            </div>
            <div id="step-2" class="step-content">
                <h2 style="color:#fff; margin-bottom:20px;">What's your name?</h2>
                <input type="text" id="name-input" class="input-field" placeholder="Enter your Name" autocomplete="off">
                <button class="btn-primary" onclick="nextStep(3)">Next</button>
            </div>
            <div id="step-3" class="step-content">
                <h2 style="color:#fff; margin-bottom:20px;">Student Details</h2>
                <div style="display:flex; gap:10px; margin-bottom:20px;">
                    <div class="toggle-btn selected" id="btn-school" onclick="toggleType('school')" style="flex:1; padding:12px; border:1px solid #333; background:#fff; color:#000; border-radius:10px; cursor:pointer;">School</div>
                    <div class="toggle-btn" id="btn-college" onclick="toggleType('college')" style="flex:1; padding:12px; border:1px solid #333; background:#111; color:#777; border-radius:10px; cursor:pointer;">College</div>
                </div>
                <div id="school-opts">
                    <select id="school-std" class="input-field" style="margin-bottom:15px; text-align-last:center;"><option disabled selected>Select Standard</option><option>6th</option><option>7th</option><option>8th</option><option>9th</option><option>10th</option><option>11th</option><option>12th</option></select>
                    <input type="text" id="school-subject" class="input-field" placeholder="Enter Subject">
                </div>
                <div id="college-opts" style="display:none;">
                    <select id="college-dept" class="input-field" style="margin-bottom:15px; text-align-last:center;"><option disabled selected>Select Dept</option><option>CSE</option><option>IT</option><option>AI & DS</option></select>
                    <select id="college-year" class="input-field" style="margin-bottom:15px; text-align-last:center;"><option disabled selected>Select Year</option><option>1st Year</option><option>2nd Year</option></select>
                    <input type="text" id="college-subject" class="input-field" placeholder="Enter Subject">
                </div>
                <button class="btn-primary" onclick="finishSetup()">Start Learning</button>
            </div>
        </div>
    </div>

    <div id="sidebar">
        <div class="sidebar-content" style="position:relative;">
            <div onclick="toggleSidebar()" style="position:absolute; top:15px; right:15px; cursor:pointer; padding:5px; z-index:10;">
                <i class="fas fa-times" style="color:var(--text-muted); font-size:22px;"></i>
            </div>

            <div style="position:relative; margin-top:50px; margin-bottom:20px; flex-shrink:0;">
                <i class="fas fa-search" style="position:absolute; left:12px; top:50%; transform:translateY(-50%); color:var(--text-muted); font-size:14px; pointer-events:none;"></i>
                <input type="text" id="hist-search" placeholder="Search..." oninput="filterHistory(this.value)" 
                       style="width:100%; height:45px; padding:0 35px 0 40px; border-radius:12px; border:1px solid var(--border); background:var(--card); color:var(--text); outline:none; font-size:15px;">
                <i class="fas fa-times" id="clear-search" onclick="clearSearch()" 
                   style="position:absolute; right:12px; top:50%; transform:translateY(-50%); cursor:pointer; display:flex; align-items:center; justify-content:center; color:var(--text-muted); display:none;"></i>
            </div>
            
            <div style="margin-bottom:20px; padding-left:5px;">
                <span class="user-info-text" id="display-name" style="font-size:22px; font-weight:700;">User</span>
            </div>

            <button class="new-chat-btn" onclick="newChat()"><i class="fas fa-plus"></i> New Chat</button>
            
            <div class="history-label" style="flex-shrink:0;">Chat History</div>
            <div id="history-list" style="flex:1; overflow-y:auto; padding-right:5px; margin-bottom:10px;"></div>
            
            <div class="sidebar-footer">
                <div class="footer-link" onclick="openSettings()"><i class="fas fa-cog"></i> Settings</div>
                <div class="footer-link"><i class="fas fa-question-circle"></i> Help</div>
            </div>
        </div>
        <div class="sidebar-overlay-gap" onclick="toggleSidebar()"></div> 
    </div>

    <div id="app-container">
        <header>
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-bars"></i></div>
            <span class="app-title">Student's AI</span>
            <div style="width:40px;"></div>
        </header>

        <div id="chat-box"></div>

        <div class="input-wrapper">
            <div id="preview-box" style="display:none; padding:10px 15px; background:var(--bg); border-top:1px solid var(--border);">
                <div style="position:relative; display:inline-block;">
                    <img id="preview-img" style="width:60px; height:60px; border-radius:8px; object-fit:cover; border:1px solid #444;">
                    <div onclick="clearFile()" style="position:absolute; top:-8px; right:-8px; background:red; color:#fff; border-radius:50%; width:20px; height:20px; display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:12px;">×</div>
                </div>
            </div>
            <div id="attach-menu" style="display:none; position:absolute; bottom:75px; left:15px; background:#1a1a1a; border:1px solid #333; border-radius:16px; padding:8px; flex-direction:column; width:160px; z-index:100; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
                <label style="padding:12px; display:flex; align-items:center; gap:12px; color:#fff; cursor:pointer;"><i class="fas fa-camera" style="color:#00d2ff;"></i> Camera <input type="file" hidden accept="image/*" capture="environment" onchange="handleFile(this)"></label>
                <label style="padding:12px; display:flex; align-items:center; gap:12px; color:#fff; cursor:pointer;"><i class="fas fa-image" style="color:#bf5af2;"></i> Gallery <input type="file" hidden accept="image/*" onchange="handleFile(this)"></label>
                <label style="padding:12px; display:flex; align-items:center; gap:12px; color:#fff; cursor:pointer;"><i class="fas fa-file-pdf" style="color:#ff3b30;"></i> File <input type="file" hidden accept="application/pdf" onchange="handleFile(this)"></label>
            </div>

            <div class="input-container">
                <div class="plus-btn" onclick="toggleAttachMenu()"><i class="fas fa-plus"></i></div>
                <textarea id="msg-input" placeholder="Message..." rows="1" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
                <div class="send-btn" onclick="send()"><i class="fas fa-arrow-up"></i></div>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let userDetails = { type: 'school' };
        let currentChatId = null;
        let isGenerating = false;

        // --- ONBOARDING & SETUP ---
        function nextStep(targetStep) {
            if (targetStep === 3) { 
                const name = document.getElementById('name-input').value.trim();
                if (!name) return shakeElement('name-input');
                currentUser = name;
            }
            if (targetStep > 1) history.pushState({ step: targetStep }, null, "");
            document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
            document.getElementById('step-' + targetStep).classList.add('active');
        }

        function toggleType(type) {
            userDetails.type = type;
            const btnS = document.getElementById('btn-school');
            const btnC = document.getElementById('btn-college');
            if(type === 'school') { btnS.style.background='#fff'; btnS.style.color='#000'; btnC.style.background='#111'; btnC.style.color='#777'; }
            else { btnC.style.background='#fff'; btnC.style.color='#000'; btnS.style.background='#111'; btnS.style.color='#777'; }
            document.getElementById('school-opts').style.display = type === 'school' ? 'block' : 'none';
            document.getElementById('college-opts').style.display = type === 'college' ? 'block' : 'none';
        }

        function finishSetup() {
            userDetails.name = currentUser;
            let valid = true;
            if(userDetails.type === 'school') {
                userDetails.standard = document.getElementById('school-std').value;
                userDetails.subject = document.getElementById('school-subject').value.trim();
                if(!userDetails.subject) valid = false;
            } else {
                userDetails.dept = document.getElementById('college-dept').value;
                userDetails.subject = document.getElementById('college-subject').value.trim();
                if(!userDetails.subject) valid = false;
            }
            if(!valid) { alert("Please fill details"); return; }

            localStorage.setItem("student_ai_user", currentUser);
            localStorage.setItem("student_details", JSON.stringify(userDetails));
            document.getElementById("onboarding-overlay").classList.add('hidden');
            setTimeout(() => document.getElementById("onboarding-overlay").style.display = 'none', 600);
            showApp();
        }

        function shakeElement(id) {
            const el = document.getElementById(id);
            el.classList.add('input-error', 'shake');
            setTimeout(() => el.classList.remove('shake'), 500);
            el.addEventListener('input', () => el.classList.remove('input-error'), {once:true});
        }

        function checkLogin() {
            const stored = localStorage.getItem("student_ai_user");
            if (stored) { 
                currentUser = stored;
                userDetails = JSON.parse(localStorage.getItem("student_details") || "{}");
                document.getElementById("onboarding-overlay").style.display = 'none';
                showApp();
            }
            setTheme(localStorage.getItem('app_theme') || 'system');
        }

        function showApp() {
            document.getElementById("display-name").innerText = currentUser;
            updateProfileUI();
            const introDiv = document.getElementById("chat-box");
            if(introDiv.innerHTML === "") {
                const sub = userDetails.subject || 'your subjects';
                introDiv.innerHTML = `<div class="msg ai-msg"><div class="ai-content"><h1>Hi ${currentUser},</h1><p>Ready to study <b>${sub}</b>?</p></div></div>`;
            }
            loadHistory();
        }

        // --- SETTINGS ---
        function openSettings() {
            document.getElementById('settings-overlay').classList.add('active');
            history.pushState({view: 'settings'}, null, "");
            const sb = document.getElementById('sidebar');
            if(sb.classList.contains('open')) toggleSidebar();
            updateProfileUI();
        }
        function closeSettings() {
            if(history.state && history.state.view === 'settings') history.back();
            else document.getElementById('settings-overlay').classList.remove('active');
        }
        function openSubPage(pageId) {
            document.getElementById(pageId).classList.add('active');
            history.pushState({view: 'subpage'}, null, "");
        }
        function closeSubPage(pageId) {
            if(history.state && history.state.view === 'subpage') history.back();
            else document.getElementById(pageId).classList.remove('active');
        }

        function updateProfileUI() {
            document.getElementById('profile-name').innerText = currentUser;
            document.getElementById('profile-edu').innerText = userDetails.type === 'school' ? 'School' : 'College';
            document.getElementById('profile-std').innerText = userDetails.type === 'school' ? userDetails.standard : userDetails.dept;
            document.getElementById('profile-sub').innerText = userDetails.subject;
            const pic = localStorage.getItem('profile_pic');
            if(pic) {
                document.getElementById('settings-pic').src = pic;
                document.querySelector('.user-info-text').innerHTML = `<img src="${pic}" style="width:30px;height:30px;border-radius:50%;margin-right:10px;vertical-align:middle"> ${currentUser}`;
            }
        }

        function editSubject(el) {
            const currentSub = el.innerText;
            const input = document.createElement('input');
            input.value = currentSub;
            input.className = 'subject-edit-input';
            el.replaceWith(input);
            input.focus();
            const save = () => {
                const newVal = input.value.trim() || currentSub;
                userDetails.subject = newVal;
                localStorage.setItem("student_details", JSON.stringify(userDetails));
                const span = document.createElement('span');
                span.className = 'detail-value editable-subject';
                span.id = 'profile-sub';
                span.onclick = function() { editSubject(this) };
                span.innerText = newVal;
                span.style.cssText = "font-weight:600; cursor:pointer; border-bottom:1px dashed var(--text-muted);";
                input.replaceWith(span);
            };
            input.onblur = save;
            input.onkeydown = (e) => { if(e.key === 'Enter') save(); }
        }

        function setTheme(theme) {
            localStorage.setItem('app_theme', theme);
            document.body.classList.remove('light-mode');
            if (theme === 'light' || (theme === 'system' && !window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                document.body.classList.add('light-mode');
            }
        }
        function handleLogout() { localStorage.clear(); location.reload(); }
        function uploadProfilePic(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) { localStorage.setItem('profile_pic', e.target.result); updateProfileUI(); }
                reader.readAsDataURL(input.files[0]);
            }
        }

        // --- UTILS & SEARCH ---
        function filterSettings(query) {
            const btns = document.querySelectorAll('.settings-option-btn');
            const clearBtn = document.getElementById('clear-setting-search');
            if(clearBtn) clearBtn.style.display = query.length > 0 ? 'block' : 'none';
            btns.forEach(btn => {
                const text = btn.innerText.toLowerCase();
                btn.style.display = text.includes(query.toLowerCase()) ? 'flex' : 'none';
            });
        }
        function clearSettingsSearch() {
            const inp = document.getElementById('setting-search-input');
            inp.value = "";
            filterSettings("");
            inp.blur();
        }

        function toggleAttachMenu() {
            const menu = document.getElementById('attach-menu');
            menu.style.display = (menu.style.display === 'none' || menu.style.display === '') ? 'flex' : 'none';
        }
        function handleFile(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    window.currentFile = e.target.result; 
                    document.getElementById('preview-img').src = e.target.result;
                    document.getElementById('preview-box').style.display = 'block';
                    document.getElementById('attach-menu').style.display = 'none';
                };
                reader.readAsDataURL(input.files[0]);
            }
        }
        function clearFile() {
            window.currentFile = null;
            document.getElementById('preview-box').style.display = 'none';
            document.querySelectorAll('input[type="file"]').forEach(el => el.value = "");
        }
        document.addEventListener('click', function(e) {
            const menu = document.getElementById('attach-menu');
            const btn = document.querySelector('.plus-btn');
            if (menu && menu.style.display === 'flex' && !menu.contains(e.target) && !btn.contains(e.target)) {
                menu.style.display = 'none';
            }
        });

        function copyText(btn, text) {
            navigator.clipboard.writeText(text).then(() => {
                const originalIcon = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check" style="color:#4ade80;"></i> Copied';
                setTimeout(() => { btn.innerHTML = originalIcon; }, 2000);
            });
        }
        function shareContent(text) {
            if (navigator.share) { navigator.share({ title: 'Student AI', text: text }).catch(console.error); }
            else { alert("Sharing not supported. Text copied."); }
        }

        /* --- TOGGLE SIDEBAR (FIX: HIDE CHAT INPUT) --- */
        function toggleSidebar() {
            const sb = document.getElementById('sidebar');
            const chatInput = document.querySelector('.input-wrapper'); 
            
            sb.classList.toggle('open');
            
            if(sb.classList.contains('open')) {
                history.pushState({menu: 'open'}, null, "");
                // 👇 This fixes the keyboard overlap issue
                if(chatInput) chatInput.style.display = 'none';
            } else {
                if(chatInput) chatInput.style.display = 'block';
            }
        }

        // --- GLOBAL HISTORY HANDLER ---
        window.onpopstate = function(event) {
            const activeSubPage = document.querySelector('.settings-sub-page.active');
            if (activeSubPage) { activeSubPage.classList.remove('active'); return; }

            const settings = document.getElementById('settings-overlay');
            if (settings && settings.classList.contains('active')) { settings.classList.remove('active'); return; }

            const sidebar = document.getElementById('sidebar');
            if (sidebar && sidebar.classList.contains('open')) { toggleSidebar(); return; }

            if (event.state && event.state.step) {
                document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
                document.getElementById('step-' + event.state.step).classList.add('active');
            }
        };

        // --- KEYBOARD ENTER SUPPORT ---
        document.addEventListener("DOMContentLoaded", function() {
            const msgInput = document.getElementById('msg-input');
            if(msgInput) {
                msgInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); this.blur(); }
                });
            }
            const nameInput = document.getElementById('name-input');
            if(nameInput) {
                nameInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') { nextStep(3); this.blur(); }
                });
            }
            const schoolSub = document.getElementById('school-subject');
            const collegeSub = document.getElementById('college-subject');
            if(schoolSub) {
                schoolSub.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') { finishSetup(); this.blur(); }
                });
            }
            if(collegeSub) {
                collegeSub.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') { finishSetup(); this.blur(); }
                });
            }
        });

        // --- CHAT LOGIC ---
        function typeWriter(element, text, callback) {
            const chatBox = document.getElementById('chat-box');
            element.innerHTML = marked.parse(text);
            const finalHTML = element.innerHTML;
            element.innerHTML = "";
            element.style.minHeight = "20px";
            let i = 0;
            function type() {
                if (i < finalHTML.length) {
                    if (finalHTML.charAt(i) === '<') { let tagEnd = finalHTML.indexOf('>', i); i = tagEnd + 1; } 
                    else { i += 3; }
                    element.innerHTML = finalHTML.substring(0, i);
                    chatBox.scrollTop = chatBox.scrollHeight;
                    requestAnimationFrame(type);
                } else {
                    element.innerHTML = finalHTML;
                    if (window.mermaid && text.includes("```mermaid")) mermaid.run({ nodes: [element] });
                    chatBox.scrollTop = chatBox.scrollHeight;
                    if (callback) callback();
                }
            }
            type();
        }

        function addMsg(role, text, img) {
            const box = document.getElementById('chat-box');
            let contentHtml = "";
            if (img) contentHtml += `<img src="${img}" style="max-width:200px; border-radius:10px; margin-bottom:10px;">`;
            if (role === 'ai') { contentHtml += `<div class="ai-content">${marked.parse(text)}</div>`; } 
            else { contentHtml += `<div class="user-content">${text}</div>`; }

            const safeText = text.replace(/`/g, '\\`').replace(/"/g, '&quot;');
            let actionsHtml = "";
            if (role === 'user') {
                actionsHtml = `<div class="msg-actions" style="justify-content: flex-end;"><div class="action-icon" onclick="copyText(this, \`${safeText}\`)"><i class="fas fa-copy"></i> Copy</div></div>`;
            } else {
                actionsHtml = `<div class="msg-actions"><div class="action-icon" onclick="copyText(this, \`${safeText}\`)"><i class="fas fa-copy"></i> Copy</div><div class="action-icon" onclick="shareContent(\`${safeText}\`)"><i class="fas fa-share-alt"></i> Share</div></div>`;
            }

            const msgDiv = document.createElement('div');
            msgDiv.className = `msg ${role === 'user' ? 'user-msg' : 'ai-msg'}`;
            msgDiv.innerHTML = `<div class="msg-bubble" style="${role==='ai'?'background:transparent;padding:0;':''}">${contentHtml}</div>${actionsHtml}`;
            box.appendChild(msgDiv);
            box.scrollTo(0, box.scrollHeight);
        }

        async function send() {
            if (isGenerating) return;
            const inputEl = document.getElementById('msg-input');
            const txt = inputEl.value.trim();
            const fileData = window.currentFile;
            if (!txt && !fileData) return;

            inputEl.value = "";
            inputEl.style.height = 'auto';
            document.getElementById('preview-box').style.display = 'none';
            window.currentFile = null;

            addMsg('user', txt, fileData);

            const msgId = "ai-" + Date.now();
            const chatBox = document.getElementById('chat-box');
            chatBox.insertAdjacentHTML('beforeend', `<div id="${msgId}" class="msg ai-msg"><div class="msg-bubble" style="color:var(--text-muted);">Thinking...</div></div>`);
            chatBox.scrollTo(0, chatBox.scrollHeight);
            isGenerating = true;

            try {
                if (!currentChatId) {
                    const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                    const d = await r.json(); currentChatId = d.chat_id; loadHistory();
                }
                const res = await fetch('/chat', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: txt, image: fileData, username: currentUser, chat_id: currentChatId })
                });
                const data = await res.json();
                
                const aiDiv = document.getElementById(msgId);
                aiDiv.innerHTML = ""; 
                const bubble = document.createElement('div');
                bubble.className = "msg-bubble";
                aiDiv.appendChild(bubble);
                
                typeWriter(bubble, data.response, () => {
                    const safeText = data.response.replace(/`/g, '\\`').replace(/"/g, '&quot;');
                    const actionsHtml = `<div class="msg-actions"><div class="action-icon" onclick="copyText(this, \`${safeText}\`)"><i class="fas fa-copy"></i> Copy</div><div class="action-icon" onclick="shareContent(\`${safeText}\`)"><i class="fas fa-share-alt"></i> Share</div></div>`;
                    aiDiv.insertAdjacentHTML('beforeend', actionsHtml);
                    isGenerating = false; 
                    chatBox.scrollTop = chatBox.scrollHeight;
                });
            } catch (e) {
                document.getElementById(msgId).innerHTML = "Error.";
                isGenerating = false;
            }
        }

        // --- HISTORY & CHAT MGMT ---
        async function loadHistory() {
             const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
             const data = await res.json();
             const list = document.getElementById('history-list'); list.innerHTML = "";
             if(data.chats) {
                 Object.keys(data.chats).reverse().forEach(cid => {
                     list.innerHTML += `<div class="history-item"><span onclick="loadChat('${cid}')" style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${data.chats[cid].title}</span><div class="history-actions"><i class="fas fa-trash hist-icon" onclick="deleteChat('${cid}')"></i></div></div>`;
                 });
             }
        }
        
        async function loadChat(cid) {
            currentChatId = cid; 
            toggleSidebar();
            const res = await fetch('/get_chat', {
                method:'POST', headers:{'Content-Type':'application/json'}, 
                body:JSON.stringify({username:currentUser, chat_id:cid})
            });
            const d = await res.json();
            document.getElementById('chat-box').innerHTML = "";
            d.messages.forEach(m => addMsg(m.role === 'user' ? 'user' : 'ai', m.content));
        }

        async function deleteChat(cid) {
            if(confirm("Delete this chat?")) {
                await fetch('/delete_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
                loadHistory();
                if(currentChatId === cid) document.getElementById('chat-box').innerHTML = "";
            }
        }
        
        function newChat() {
            currentChatId = null;
            document.getElementById('chat-box').innerHTML = `<div class="msg ai-msg"><div class="ai-content"><h1>Hi ${currentUser},</h1><p>Start a new topic!</p></div></div>`;
            toggleSidebar();
        }

        function filterHistory(query) {
            const items = document.querySelectorAll('.history-item');
            const clearBtn = document.getElementById('clear-search');
            clearBtn.style.display = query.length > 0 ? 'flex' : 'none';
            items.forEach(item => {
                const title = item.querySelector('span').innerText.toLowerCase();
                item.style.display = title.includes(query.toLowerCase()) ? 'flex' : 'none';
            });
        }

        function clearSearch() {
            const input = document.getElementById('hist-search');
            input.value = "";
            filterHistory("");
            input.focus();
        }

        // INITIALIZE
        checkLogin();
    </script>
</body>       
</html>
"""

# --- BACKEND ROUTES ---
@app.route("/", methods=["GET"])
def home(): return render_template_string(HTML_TEMPLATE)

@app.route("/new_chat", methods=["POST"])
def new_chat():
    u = request.json.get("username")
    if u not in user_db: user_db[u] = {}
    nid = str(uuid.uuid4())
    user_db[u][nid] = {"title": "New Chat", "messages": []}
    save_db(user_db)
    return jsonify({"chat_id": nid})

@app.route("/rename_chat", methods=["POST"])
def rename_chat():
    d = request.json
    u, cid, t = d.get("username"), d.get("chat_id"), d.get("title")
    if u in user_db and cid in user_db[u]:
        user_db[u][cid]["title"] = t
        save_db(user_db)
    return jsonify({"status":"ok"})

@app.route("/delete_chat", methods=["POST"])
def delete_chat():
    d = request.json
    u, cid = d.get("username"), d.get("chat_id")
    if u in user_db and cid in user_db[u]:
        del user_db[u][cid]
        save_db(user_db)
    return jsonify({"status":"ok"})

@app.route("/get_history", methods=["POST"])
def get_history():
    u = request.json.get("username")
    return jsonify({"chats": user_db.get(u, {})})

@app.route("/get_chat", methods=["POST"])
def get_chat():
    d = request.json
    return jsonify({"messages": user_db.get(d["username"], {}).get(d["chat_id"], {}).get("messages", [])})

@app.route("/chat", methods=["POST"])
def chat():
    d = request.json
    u, cid, msg = d.get("username"), d.get("chat_id"), d.get("message")
    img_data = d.get("image")
    file_text = d.get("file_text")

    if u not in user_db: user_db[u] = {}
    if cid not in user_db[u]: user_db[u][cid] = {"messages": []}

    user_db[u][cid]["messages"].append({"role": "user", "content": msg})
    reply = generate_with_retry(msg, img_data, file_text, user_db[u][cid]["messages"][:-1])
    user_db[u][cid]["messages"].append({"role": "model", "content": reply})
    
    new_title = False
    if len(user_db[u][cid]["messages"]) <= 2:
        user_db[u][cid]["title"] = " ".join(msg.split()[:4])
        new_title = True
        
    save_db(user_db) 
    return jsonify({"response": reply, "new_title": new_title})

@app.route('/manifest.json')
def manifest():
    data = {
        "name": "Student's AI",
        "short_name": "Student's AI",
        "start_url": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#09090b",
        "theme_color": "#09090b",
        "icons": [
            { "src": "[https://huggingface.co/spaces/Shirpi/Student-s_AI/resolve/main/1000177401.png](https://huggingface.co/spaces/Shirpi/Student-s_AI/resolve/main/1000177401.png)", "sizes": "192x192", "type": "image/png" },
            { "src": "[https://huggingface.co/spaces/Shirpi/Student-s_AI/resolve/main/1000177401.png](https://huggingface.co/spaces/Shirpi/Student-s_AI/resolve/main/1000177401.png)", "sizes": "512x512", "type": "image/png" }
        ]
    }
    return Response(json.dumps(data), mimetype='application/json')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)