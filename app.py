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

# Warning Fix
warnings.filterwarnings("ignore")

# API KEYS SETUP
keys_string = os.environ.get("API_KEYS", "")
API_KEYS = [k.strip() for k in keys_string.replace(',', ' ').replace('\n', ' ').split() if k.strip()]

# DATABASE SETUP
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

app = Flask(__name__)
current_key_index = 0

# MODEL FUNCTIONS
def get_working_model(key):
    try:
        genai.configure(api_key=key)
        models = list(genai.list_models())
        chat_models = [m for m in models if 'generateContent' in m.supported_generation_methods]
        for m in chat_models:
            if "flash" in m.name.lower() and "1.5" in m.name: return m.name
        if chat_models: return chat_models[0].name
    except: return None
    return None

def process_image(image_data):
    try:
        if "base64," in image_data: image_data = image_data.split("base64,")[1]
        image_bytes = base64.b64decode(image_data)
        return Image.open(io.BytesIO(image_bytes))
    except: return None

def generate_with_retry(prompt, image_data=None, file_text=None, history_messages=[], user_context=""):
    global current_key_index
    if not API_KEYS: return "🚨 API Keys Missing."
    formatted_history = []
    for m in history_messages[-6:]:
        role = "user" if m["role"] == "user" else "model"
        formatted_history.append({"role": role, "parts": [m["content"]]})
    
    current_parts = []
    full_prompt = prompt
    if user_context: full_prompt = f"[User Context: {user_context}]\nQuestion: {prompt}"
    if file_text: current_parts.append(f"File content:\n{file_text}\n\n")
    current_parts.append(full_prompt)
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
            model = genai.GenerativeModel(model_name=model_name)
            if image_data or file_text: response = model.generate_content(current_parts)
            else:
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(full_prompt)
            return response.text
        except Exception as e:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            time.sleep(1)
    return "⚠️ System Busy. Please try again."
    HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, interactive-widget=resizes-content, viewport-fit=cover">
    <meta name="theme-color" content="#09090b">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="manifest" href="/manifest.json">
    
    <title>Student's AI</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Outfit:wght@500;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>window.MathJax = { tex: { inlineMath: [['$', '$']] }, svg: { fontCache: 'global' } };</script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

    <style>
        :root { 
            --bg: #09090b; --card: #18181b; --user-msg: #27272a; --text: #e4e4e7; 
            --border: #27272a; --dim: #71717a; --accent: #fff; --input-bg: #131315;
        }
        [data-theme="light"] {
            --bg: #f4f4f5; --card: #ffffff; --user-msg: #e4e4e7; --text: #18181b;
            --border: #d4d4d8; --dim: #71717a; --accent: #000; --input-bg: #ffffff;
        }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; -webkit-user-select: none; user-select: none; }
        input, textarea { -webkit-user-select: text; user-select: text; }

        /* --- LAYOUT LOCK (Keyboard Fix) --- */
        body { 
            margin: 0; background: var(--bg); color: var(--text); 
            font-family: 'Inter', sans-serif; 
            height: 100dvh; width: 100vw; 
            display: flex; flex-direction: column; 
            overflow: hidden; 
        }
        
        /* --- HEADER FIXED --- */
        header { 
            height: 70px; padding: 0 20px; background: var(--bg); 
            border-bottom: 1px solid var(--border); 
            display: flex; align-items: center; justify-content: space-between; 
            flex-shrink: 0; 
            z-index: 3000; 
            position: fixed; top: 0; left: 0; right: 0; 
        }
        .app-title { font-family: 'Outfit', sans-serif; font-size: 24px; font-weight: 800; color: var(--text); text-align:center; flex:1; }
        .menu-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; cursor: pointer; color:var(--text); z-index:3001; }
        
        /* --- CHAT BOX AUTO ADJUST --- */
        #chat-box { 
            flex-grow: 1; 
            overflow-y: auto; 
            padding: 20px 5%; 
            padding-top: 90px; 
            display: flex; flex-direction: column; gap: 20px; width:100%; 
            scroll-behavior: smooth; -webkit-overflow-scrolling: touch;
        }

        /* --- INPUT AREA PWA FIX --- */
        .input-wrapper { 
            background: var(--bg); padding: 15px; 
            border-top: 1px solid var(--border); width: 100%; 
            flex-shrink: 0; 
            z-index: 40; 
            padding-bottom: max(15px, env(safe-area-inset-bottom)); 
        }
        .input-container { max-width: 900px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 24px; padding: 10px 15px; display: flex; align-items: flex-end; gap: 12px; }
        textarea { flex: 1; background: transparent; border: none; color: var(--text); font-size: 16px; max-height: 120px; padding: 8px 5px; resize: none; outline: none; font-family: 'Inter', sans-serif; }
        
        /* SIDEBAR */
        #sidebar { 
            position: fixed; top: 0; left: 0; 
            width: 100vw; height: 100dvh; 
            background: var(--bg); 
            z-index: 5000; 
            padding: 25px; padding-top: 80px; 
            transform: translateY(-100%); 
            transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex; flex-direction: column; overflow-y: auto;
        }
        #sidebar.open { transform: translateY(0); }
        .history-item { display: flex; justify-content: space-between; align-items: center; padding: 15px; margin-bottom: 8px; background: var(--card); border-radius: 12px; cursor: pointer; color: var(--dim); font-size: 14px; }
        .h-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-right: 10px; }
        .h-actions { display: flex; gap: 20px; }

        /* --- COMPACT DATA BOX & POSITION FIX --- */
        .data-box { 
            width: 90%; max-width: 350px; background: var(--card); 
            border: 1px solid var(--border); border-radius: 20px; 
            padding: 20px; 
            display:flex; flex-direction:column; gap:12px; 
            box-shadow: 0 10px 40px rgba(0,0,0,0.5); 
            flex-shrink: 0; 
            margin-top: 15vh; /* Safe Spot */
            margin-bottom: 50px; 
            animation: fadeInUp 0.6s ease-out;
        }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        
        .form-label { font-size: 11px; color: var(--dim); margin-left: 2px; margin-bottom:-8px; margin-top: 2px; font-weight:600; text-transform:uppercase; }
        
        input, select { width: 100%; padding: 12px; background: var(--input-bg); border: 1px solid var(--border); color: var(--text); border-radius: 10px; outline: none; font-size: 16px; font-family: 'Inter', sans-serif; appearance: none; }
        select { background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='gray' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e"); background-repeat: no-repeat; background-position: right 15px center; background-size: 15px; }
        
        /* --- RED ALERT VALIDATION --- */
        .input-error { border: 1px solid #ef4444 !important; box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2); animation: shake 0.4s ease-in-out; }
        @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-5px); } 75% { transform: translateX(5px); } }

        /* --- BEAUTIFUL INTRO --- */
        .submit-btn, .get-started-btn { 
            width: 100%; padding: 14px; border-radius: 12px; border: none; 
            background: linear-gradient(90deg, #fff, #e4e4e7); color: #000; 
            font-weight: 800; font-size: 16px; cursor: pointer; margin-top: 10px; 
            font-family: 'Outfit', sans-serif; box-shadow: 0 4px 15px rgba(255,255,255,0.1); transition: transform 0.2s;
        }
        .submit-btn:active { transform: scale(0.98); }
        .welcome-title { 
            font-family: 'Outfit', sans-serif; font-size: 38px; font-weight: 800; line-height: 1.2; margin-bottom: 15px; 
            background: linear-gradient(135deg, #fff 0%, #a1a1aa 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        
        /* --- INTRO AUTO CENTER --- */
        #intro-container { margin: auto; width: 100%; padding: 0 25px; text-align: center; pointer-events: none; animation: fadeIn 0.8s ease-out; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

        /* --- SEARCH X ICON --- */
        .search-bar-container { position:relative; width:100%; margin-bottom:20px; display: flex; align-items: center; }
        .search-input { width:100%; background:var(--card); border:none; padding-right:35px; }
        .search-clear { position:absolute; right:10px; color:var(--dim); cursor:pointer; display:none; font-size: 14px; background: rgba(255,255,255,0.1); border-radius: 50%; width: 20px; height: 20px; align-items: center; justify-content: center; }
        
        /* SETTINGS & MODAL */
        .settings-container { display:flex; flex-direction:column; gap:0; background: var(--card); border-radius:15px; border:1px solid var(--border); overflow:hidden; }
        .settings-option { padding:15px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; color: var(--text); font-size:16px; }
        .divider { height:1px; background: var(--border); width:100%; }
        .nav-back-btn { font-size: 16px; font-weight: 600; color: var(--text); cursor: pointer; display: flex; align-items: center; gap: 5px; font-family: 'Outfit', sans-serif; }
        .overlay { position: fixed; inset: 0; background: var(--bg); z-index: 2000; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 0; overflow-y: auto; }
        .overlay.hidden { display: none !important; }
        #custom-modal { position: fixed; inset:0; background: rgba(0,0,0,0.8); z-index: 6000; display:none; align-items:center; justify-content:center; }
        .modal-box { background: var(--card); padding:25px; border-radius:20px; width:85%; max-width:320px; text-align:center; border:1px solid var(--border); }
        .modal-btn-row { display:flex; gap:10px; margin-top:20px; }
        
        /* CHAT UI */
        .msg { display: flex; flex-direction: column; margin-bottom: 20px; opacity: 0; animation: fadeInstant 0.3s forwards; }
        @keyframes fadeInstant { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .user-msg { align-items: flex-end; } .user-content { background: var(--user-msg); padding: 12px 18px; border-radius: 18px 18px 4px 18px; max-width: 85%; color: var(--text); font-size: 16px; line-height: 1.5; }
        .ai-msg { align-items: flex-start; width: 100%; } .ai-content { width: 100%; color: var(--text); font-size: 16px; line-height: 1.6; }
        .msg-actions { display: flex; gap: 15px; margin-top: 5px; opacity: 0.7; padding-left: 5px; }
        .action-icon, .icon-btn, .send-btn { cursor: pointer; } .icon-btn { background: transparent; color: var(--dim); } .send-btn { background: var(--text); color: var(--bg); }
        .icon-btn, .send-btn { width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: none; font-size: 18px; flex-shrink: 0; }
        .typing-indicator { display: flex; align-items: center; gap: 4px; padding: 5px 0; } .typing-dot { width: 8px; height: 8px; background-color: var(--dim); border-radius: 50%; animation: wave 1.3s linear infinite; }
        .typing-dot:nth-child(2) { animation-delay: -1.1s; } .typing-dot:nth-child(3) { animation-delay: -0.9s; }
        @keyframes wave { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-6px); } }
        #preview-area { display:none; position:absolute; bottom:85px; left:20px; z-index:50; }
        .preview-box { width:60px; height:60px; background:#222; border:2px solid #fff; border-radius:12px; overflow:hidden; } .preview-img { width:100%; height:100%; object-fit:cover; }
        .profile-header { display: flex; flex-direction: column; align-items: center; margin-bottom: 5px; position: relative; }
        .profile-avatar { width: 80px; height: 80px; border-radius: 50%; background: #222; border: 2px solid var(--text); position: relative; margin-bottom: 15px; display: flex; align-items: center; justify-content: center; }
        .no-results { color: var(--dim); text-align: center; padding: 20px; display: none; }
    </style>
    </head>
<body>
    <div id="custom-modal">
        <div class="modal-box">
            <h3 id="modal-title" style="margin:0 0 10px 0; color:var(--text);">Alert</h3>
            <input type="text" id="modal-input" style="display:none; margin-top:10px;" placeholder="Enter text...">
            <div class="modal-btn-row">
                <button class="submit-btn" style="background:var(--dim); flex:1;" onclick="closeModal()">Cancel</button>
                <button class="submit-btn" style="flex:1;" id="modal-confirm-btn">Confirm</button>
            </div>
        </div>
    </div>

    <div id="welcome-overlay" class="overlay">
        <div class="welcome-container" style="margin-top: 25vh;">
            <h1 class="welcome-title">Welcome to<br>Student's AI</h1>
            <p class="welcome-desc">Your smart academic companion. Ask doubts, solve problems, and master your subjects.</p>
            <button class="get-started-btn" onclick="showNameBox()">Get Started</button>
        </div>
    </div>

    <div id="name-overlay" class="overlay hidden">
        <div class="data-box">
            <h2 style="color:var(--text); margin:0 0 10px 0; font-family:'Outfit',sans-serif;">Who are you?</h2>
            <input type="text" id="username-input" placeholder="Enter your Name" onfocus="clearError(this)" onkeydown="if(event.key==='Enter') handleNameSubmit()">
            <button class="submit-btn" onclick="handleNameSubmit()">Next</button>
        </div>
    </div>

    <div id="details-overlay" class="overlay hidden">
        <div class="data-box">
            <h2 style="color:var(--text); margin:0 0 5px 0; font-family:'Outfit',sans-serif;">Student Details</h2>
            <span class="form-label">Education Level</span>
            <select id="edu-level" onchange="updateEduOptions()" onfocus="clearError(this)">
                <option value="" disabled selected>Select Level</option>
                <option value="school">School (6th - 12th)</option>
                <option value="college">College (Arts/Engg)</option>
            </select>
            <span class="form-label" id="lbl-year-select">Class / Year</span>
            <select id="edu-year" onchange="updateSemesterOptions()" onfocus="clearError(this)">
                <option value="" disabled selected>Select</option>
            </select>
            <div id="sem-container" style="display:none; flex-direction:column; gap:5px;">
                <span class="form-label">Semester</span>
                <select id="edu-sem" onfocus="clearError(this)"><option value="" disabled selected>Select Semester</option></select>
            </div>
            <span class="form-label">Main Subject</span>
            <input type="text" id="edu-subject" placeholder="Ex: Maths, CS..." onfocus="clearError(this)" onkeydown="if(event.key==='Enter') handleDetailsSubmit()">
            <button class="submit-btn" onclick="handleDetailsSubmit()">Start Learning</button>
        </div>
    </div>

    <div id="settings-overlay" class="overlay hidden">
        <div style="width:100%; display:flex; justify-content:flex-start; padding:0 20px; max-width:400px; margin-bottom:10px; margin-top:20px;">
            <div class="nav-back-btn" onclick="closeSettings()"><i class="fas fa-arrow-left"></i> Back</div>
        </div>
        <div style="width:90%; max-width:350px;">
            <div class="search-bar-container">
                <input type="text" id="setting-search" class="search-input" placeholder="Search settings..." oninput="toggleSearchClear(this); handleSearch(this)" onkeydown="if(event.key==='Enter') this.blur()">
                <i class="fas fa-times search-clear" id="search-clear-btn" onclick="clearSearch()"></i>
            </div>
            <div id="settings-list" class="settings-container">
                <div class="settings-option" data-search="student profile" onclick="openProfileFromSettings()"><span>Student Profile</span> <i class="fas fa-chevron-right" style="font-size:12px;"></i></div>
                <div class="divider"></div>
                <div class="settings-option" data-search="theme light dark system" style="padding:15px; display:block; cursor:default;">
                    <div style="font-size:12px; color:var(--dim); margin-bottom:10px; font-weight:600; letter-spacing:1px;">THEME</div>
                    <div style="display:flex; gap:10px;">
                        <button class="icon-btn" onclick="setTheme('light')" style="border:1px solid var(--border); flex:1;"><i class="fas fa-sun"></i></button>
                        <button class="icon-btn" onclick="setTheme('dark')" style="border:1px solid var(--border); flex:1;"><i class="fas fa-moon"></i></button>
                        <button class="icon-btn" onclick="setTheme('system')" style="border:1px solid var(--border); flex:1;"><i class="fas fa-desktop"></i></button>
                    </div>
                </div>
            </div>
            <div id="search-no-results" class="no-results">No results found</div>
        </div>
    </div>

    <div id="profile-overlay" class="overlay hidden">
        <div style="width:100%; display:flex; justify-content:flex-start; padding:0 20px; max-width:400px; margin-bottom:10px; margin-top:20px;">
            <div class="nav-back-btn" onclick="backToSettings()"><i class="fas fa-arrow-left"></i> Back</div>
        </div>
        <div class="data-box profile-box" style="margin-top:5px;">
            <div class="profile-header">
                <div class="profile-avatar">
                    <img id="profile-pic-display" style="width:100%; height:100%; object-fit:cover; display:none; border-radius:50%;">
                    <i class="fas fa-user" id="profile-icon" style="font-size:30px; color:#fff;"></i>
                    <label for="profile-upload" style="position:absolute; bottom:0; right:-5px; background:var(--text); width:25px; height:25px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer;"><i class="fas fa-camera" style="font-size:12px; color:var(--bg);"></i></label>
                </div>
                <input type="file" id="profile-upload" hidden accept="image/*" onchange="handleProfilePic(this)">
            </div>
            <span class="form-label">Name</span> <div class="profile-val" id="p-name">--</div>
            <span class="form-label">Level</span> <div class="profile-val" id="p-level">--</div>
            <span class="form-label" id="lbl-year-display">Class/Year</span> <div class="profile-val" id="p-year">--</div>
            <div id="p-sem-box" style="display:none; flex-direction:column; gap:5px;"><span class="form-label">Semester</span><div class="profile-val" id="p-sem" style="margin-top:2px;">--</div></div>
            <span class="form-label">Subject (Tap to Edit)</span>
            <input type="text" id="p-subj-edit" value="" onkeydown="handleSubjectKey(event)">
            <button class="submit-btn" style="background:var(--text); color:var(--bg); margin-top:10px;" onclick="saveProfileChanges()">Save Changes</button>
            <button class="submit-btn" style="background:#ef4444; color:#fff; margin-top:10px;" onclick="handleLogout()">Log Out</button>
        </div>
    </div>

    <header id="main-header" class="hidden-header">
        <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-bars"></i></div>
        <span class="app-title">Student's AI</span>
        <div style="width:40px;"></div>
    </header>

    <div id="sidebar">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div style="display:flex; align-items:center; gap:10px; font-size:18px; font-weight:700; color:var(--text);">
                <img id="sidebar-pic" src="" style="width:30px; height:30px; border-radius:50%; display:none; object-fit:cover;">
                <span>Hi <span id="display-name">User</span></span>
            </div>
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-times"></i></div>
        </div>
        <button class="submit-btn" style="margin:0 0 20px 0; padding:12px; font-size:15px; border-radius:12px;" onclick="newChat()">New Chat</button>
        <div style="color:var(--dim); font-size:12px; font-weight:600; text-transform:uppercase;">Chat History</div>
        <div id="history-list" style="margin-top:10px; flex:1; overflow-y:auto;"></div>
        <div style="margin-top:auto; padding-top:20px; border-top:1px solid var(--border);">
            <div style="display:flex; align-items:center; gap:15px; color:var(--text); cursor:pointer;" onclick="openSettings()"><i class="fas fa-cog"></i><span style="margin-left:10px;">Settings</span></div>
        </div>
    </div>

    <div id="chat-box"></div> 
    <div class="input-wrapper">
        <div id="preview-area"><div class="preview-box"><img id="preview-img" class="preview-img"></div><button onclick="clearAttachment()" style="background:red; color:white; border:none; border-radius:50%; width:20px; height:20px; position:absolute; top:-5px; right:-5px; z-index:60;">×</button></div>
        <div class="input-container">
            <button class="icon-btn" onclick="document.getElementById('file-input').click()"><i class="fas fa-paperclip"></i></button>
            <input type="file" id="file-input" hidden onchange="handleFile(this)">
            <textarea id="input" placeholder="Type a message..." rows="1" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'" onkeydown="if(event.key==='Enter' && !event.shiftKey){event.preventDefault(); send();}"></textarea>
            <button class="send-btn" onclick="send()"><i class="fas fa-arrow-up"></i></button>
        </div>
    </div>
    <script>
        let currentUser = null, currentChatId = null, userContext = "", currentAttachment = null;
        
        function getIntroHtml(name) { 
            return `<div id="intro-container"><div class="welcome-title" style="font-size:28px; margin-bottom:5px; text-align:center;">Hi ${name},</div><p style="color:var(--dim); text-align:center;">Ready to master ${userContext ? userContext.split(',')[0] : "studies"}?</p></div>`; 
        }

        function checkLogin() {
            const t = localStorage.getItem("student_theme"); if(t) setTheme(t);
            const u = localStorage.getItem("student_ai_user");
            const c = localStorage.getItem("student_ai_context");
            if(u) {
                currentUser = u;
                document.getElementById('welcome-overlay').style.display = 'none';
                if(c) {
                    userContext = c;
                    document.getElementById('name-overlay').style.display = 'none';
                    document.getElementById('details-overlay').style.display = 'none';
                    showApp();
                } else {
                    document.getElementById('name-overlay').style.display = 'none';
                    const sel = document.getElementById('details-overlay');
                    sel.classList.remove('hidden'); sel.style.display = 'flex';
                }
            } else {
                document.getElementById('main-header').classList.add('hidden-header');
            }
        }
        function clearError(input) { input.classList.remove('input-error'); }
        function showNameBox() { document.getElementById("welcome-overlay").style.display = 'none'; const nameBox = document.getElementById("name-overlay"); nameBox.classList.remove('hidden'); nameBox.style.display = 'flex'; }
        
        // FIX: Red Alert Validation
        function handleNameSubmit() {
            const input = document.getElementById("username-input");
            const name = input.value.trim();
            if(!name) { input.classList.add('input-error'); return; }
            localStorage.setItem("student_ai_user", name);
            currentUser = name;
            document.getElementById("name-overlay").style.display = 'none';
            const details = document.getElementById("details-overlay");
            details.classList.remove('hidden'); details.style.display = 'flex';
        }

        function updateEduOptions() {
            const level = document.getElementById('edu-level').value;
            const yearSelect = document.getElementById('edu-year');
            const semContainer = document.getElementById('sem-container');
            const label = document.getElementById('lbl-year-select');
            yearSelect.innerHTML = '<option value="" disabled selected>Select</option>';
            document.getElementById('edu-sem').innerHTML = '<option value="" disabled selected>Select Semester</option>';
            if(level === 'college') {
                label.innerText = "Year";
                semContainer.style.display = 'flex';
                ["1st Year", "2nd Year", "3rd Year", "4th Year"].forEach(o => yearSelect.innerHTML += `<option value="${o}">${o}</option>`);
            } else {
                label.innerText = "Standard";
                semContainer.style.display = 'none';
                ["6th Std", "7th Std", "8th Std", "9th Std", "10th Std", "11th Std", "12th Std"].forEach(o => yearSelect.innerHTML += `<option value="${o}">${o}</option>`);
            }
        }
        function updateSemesterOptions() {
            const level = document.getElementById('edu-level').value;
            const year = document.getElementById('edu-year').value;
            const semSelect = document.getElementById('edu-sem');
            if (level !== 'college') return;
            semSelect.innerHTML = '<option value="" disabled selected>Select Semester</option>';
            let sems = [];
            if (year === "1st Year") sems = ["Semester 1", "Semester 2"];
            else if (year === "2nd Year") sems = ["Semester 3", "Semester 4"];
            else if (year === "3rd Year") sems = ["Semester 5", "Semester 6"];
            else if (year === "4th Year") sems = ["Semester 7", "Semester 8"];
            sems.forEach(s => semSelect.innerHTML += `<option value="${s}">${s}</option>`);
        }
        function handleDetailsSubmit() {
            const lElem = document.getElementById('edu-level');
            const yElem = document.getElementById('edu-year');
            const sElem = document.getElementById('edu-subject');
            const semElem = document.getElementById('edu-sem');
            const l = lElem.value, y = yElem.value, s = sElem.value.trim();
            let isValid = true;
            if(!l) { lElem.classList.add('input-error'); isValid = false; }
            if(!y) { yElem.classList.add('input-error'); isValid = false; }
            if(!s) { sElem.classList.add('input-error'); isValid = false; }
            let semVal = "";
            if(l === 'college') {
                semVal = semElem.value;
                if(!semVal) { semElem.classList.add('input-error'); isValid = false; }
            }
            if(!isValid) return;
            userContext = l === 'college' ? `${l}, ${y}, ${semVal}, ${s}` : `${l}, ${y}, ${s}`;
            localStorage.setItem("student_ai_context", userContext);
            document.getElementById('details-overlay').style.display = 'none';
            showApp();
        }

        function showApp() {
            document.getElementById('display-name').innerText = currentUser;
            loadHistory();
            if(!currentChatId && !document.getElementById('intro-container')) {
                document.getElementById('chat-box').innerHTML = getIntroHtml(currentUser);
            }
            updateSidebarPic();
        }
        function updateSidebarPic() {
            const pic = localStorage.getItem("student_profile_pic");
            if(pic) {
                const sb = document.getElementById('sidebar-pic');
                sb.src = pic; sb.style.display = 'block';
            }
        }

        function openSettings() {
             document.getElementById('settings-overlay').classList.remove('hidden');
             document.getElementById('settings-overlay').style.display = 'flex';
             document.getElementById('sidebar').classList.remove('open');
             clearSearch();
        }
        function closeSettings() { document.getElementById('settings-overlay').style.display = 'none'; }
        function openProfileFromSettings() { 
            document.getElementById('settings-overlay').style.display = 'none'; 
            openProfile(); 
        }
        function backToSettings() { 
            document.getElementById('profile-overlay').style.display = 'none'; 
            document.getElementById('settings-overlay').style.display = 'flex';
        }
        
        function openProfile() {
            document.getElementById('p-name').innerText = currentUser;
            const parts = userContext.split(',');
            const level = parts[0];
            document.getElementById('p-level').innerText = level.toUpperCase();
            document.getElementById('p-year').innerText = parts[1];
            document.getElementById('lbl-year-display').innerText = level === 'college' ? "Year" : "Standard";
            if(level === 'college' && parts.length >= 4) {
                 document.getElementById('p-sem-box').style.display = 'flex';
                 document.getElementById('p-sem').innerText = parts[2];
                 document.getElementById('p-subj-edit').value = parts[3];
            } else {
                 document.getElementById('p-sem-box').style.display = 'none';
                 document.getElementById('p-subj-edit').value = parts[2];
            }
            const prof = document.getElementById('profile-overlay');
            prof.classList.remove('hidden'); prof.style.display = 'flex';
            const pic = localStorage.getItem("student_profile_pic");
            if(pic) {
                document.getElementById('profile-pic-display').src = pic;
                document.getElementById('profile-pic-display').style.display = 'block';
                document.getElementById('profile-icon').style.display = 'none';
            }
        }

        // FIX: No Popup Save & Enter Key
        function handleSubjectKey(event) {
            if(event.key === 'Enter') {
                event.preventDefault(); 
                saveProfileChanges();
                document.getElementById('p-subj-edit').blur();
            }
        }

        function saveProfileChanges() {
            const newSubj = document.getElementById('p-subj-edit').value;
            const parts = userContext.split(',');
            if(parts[0] === 'college') parts[3] = newSubj;
            else parts[2] = newSubj;
            userContext = parts.join(',');
            localStorage.setItem("student_ai_context", userContext);
            
            // VISUAL FEEDBACK
            const btn = document.querySelector('#profile-overlay .submit-btn');
            const originalText = btn.innerText;
            btn.innerText = "Saved! ✓";
            btn.style.background = "#22c55e"; 
            
            setTimeout(() => {
                btn.innerText = originalText;
                btn.style.background = "var(--text)";
                document.getElementById('profile-overlay').style.display = 'none';
                document.getElementById('main-header').classList.remove('hidden-header');
            }, 800);
        }

        function handleProfilePic(input) {
            if (input.files && input.files[0]) {
                const r = new FileReader();
                r.onload = function(e) {
                    localStorage.setItem("student_profile_pic", e.target.result);
                    document.getElementById('profile-pic-display').src = e.target.result;
                    document.getElementById('profile-pic-display').style.display = 'block';
                    document.getElementById('profile-icon').style.display = 'none';
                    updateSidebarPic();
                }
                r.readAsDataURL(input.files[0]);
            }
        }
        function setTheme(t) {
             localStorage.setItem("student_theme", t);
             if(t === 'light') document.documentElement.setAttribute('data-theme', 'light');
             else if(t === 'dark') document.documentElement.removeAttribute('data-theme');
             else { if(window.matchMedia('(prefers-color-scheme: light)').matches) document.documentElement.setAttribute('data-theme', 'light'); else document.documentElement.removeAttribute('data-theme'); }
        }
        
        // FIX: Search Logic
        function toggleSearchClear(el) { document.getElementById('search-clear-btn').style.display = el.value ? 'flex' : 'none'; }
        function clearSearch() { const el = document.getElementById('setting-search'); el.value = ''; toggleSearchClear(el); handleSearch(el); }
        function handleSearch(el) {
            const term = el.value.toLowerCase();
            const items = document.querySelectorAll('.settings-option');
            let hasResult = false;
            items.forEach(item => {
                const keywords = item.getAttribute('data-search');
                if(keywords && keywords.includes(term)) {
                    item.style.display = 'flex'; hasResult = true;
                } else {
                    item.style.display = 'none';
                }
            });
            document.querySelector('.divider').style.display = term ? 'none' : 'block';
            document.getElementById('search-no-results').style.display = hasResult ? 'none' : 'block';
        }

        // FIX: Logout Refresh
        function handleLogout() { 
            localStorage.clear(); 
            location.reload(); 
        }
        
        function newChat() {
            currentChatId = null;
            document.getElementById('chat-box').innerHTML = getIntroHtml(currentUser);
            document.getElementById('sidebar').classList.remove('open');
        }

        async function send() {
            const txt = document.getElementById('input').value.trim();
            if(!txt && !currentAttachment) return;
            document.getElementById('intro-container').style.display = 'none';
            const box = document.getElementById('chat-box');
            let imgHtml = currentAttachment ? `<br><img src="${currentAttachment}" style="max-height:100px;border-radius:8px;">` : "";
            
            box.insertAdjacentHTML('beforeend', `
                <div class="msg user-msg">
                    <div class="user-content">${txt.replace(/</g, "&lt;")}${imgHtml}</div>
                    <div class="msg-actions">
                         <i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText('${txt}')"></i>
                         <i class="fas fa-pen action-icon" onclick="document.getElementById('input').value='${txt}'; document.getElementById('input').focus();"></i>
                    </div>
                </div>`);
            
            document.getElementById('input').value = ""; document.getElementById('input').style.height = 'auto';
            let imgData = currentAttachment; clearAttachment();
            box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
            
            const msgId = "ai-" + Date.now();
            box.insertAdjacentHTML('beforeend', `<div id="${msgId}" class="msg ai-msg"><div class="ai-content"><div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div></div>`);
            
            try {
                if(!currentChatId) {
                     const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                     const d = await r.json(); currentChatId = d.chat_id; loadHistory();
                }
                const res = await fetch('/chat', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({message:txt, image:imgData, username:currentUser, chat_id:currentChatId, user_context:userContext})
                });
                const data = await res.json();
                
                const aiMsgDiv = document.getElementById(msgId);
                const contentDiv = aiMsgDiv.querySelector('.ai-content');
                let words = data.response.split(" "); let currentText = ""; contentDiv.innerHTML = "";
                
                aiMsgDiv.insertAdjacentHTML('beforeend', `
                    <div class="msg-actions" style="opacity:0; transition:opacity 0.5s;">
                        <i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText(this.closest('.ai-msg').querySelector('.ai-content').innerText)"></i>
                        <i class="fas fa-share-alt action-icon" onclick="if(navigator.share) navigator.share({text:this.closest('.ai-msg').querySelector('.ai-content').innerText})"></i>
                        <i class="fas fa-redo action-icon" onclick="document.getElementById('input').value='${txt}'; send();"></i>
                    </div>`);

                for (let i = 0; i < words.length; i++) {
                    currentText += words[i] + " "; contentDiv.innerHTML = marked.parse(currentText);
                    box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' }); await new Promise(r => setTimeout(r, 20));
                }
                contentDiv.innerHTML = marked.parse(data.response);
                if(window.hljs) hljs.highlightAll(); if(window.MathJax) MathJax.typesetPromise([contentDiv]);
                aiMsgDiv.querySelector('.msg-actions').style.opacity = '1';
                if(data.new_title) loadHistory();
            } catch(e) { document.getElementById(msgId).innerHTML = "Error."; }
        }

        function showCustomModal(title, isInput, callback) {
            const m = document.getElementById('custom-modal');
            document.getElementById('modal-title').innerText = title;
            const inp = document.getElementById('modal-input');
            inp.style.display = isInput ? 'block' : 'none'; inp.value = "";
            m.style.display = 'flex';
            document.getElementById('modal-confirm-btn').onclick = function() { callback(inp.value); m.style.display = 'none'; };
        }
        function closeModal() { document.getElementById('custom-modal').style.display = 'none'; }

        // FIX: Instant Rename (Optimistic UI)
        async function renameChat(cid) { 
            showCustomModal("Rename Chat", true, async (val) => { 
                if(val) { 
                    const titleEl = document.getElementById('chat-'+cid).querySelector('.h-title');
                    if(titleEl) titleEl.innerText = val; // Instant Update
                    await fetch('/rename_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid, title:val})}); 
                } 
            }); 
        }
        async function deleteChat(cid) { 
            showCustomModal("Delete Chat?", false, async () => { 
                const item = document.getElementById('chat-'+cid); if(item) item.remove();
                await fetch('/delete_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})}); 
                if(currentChatId === cid) newChat(); 
            }); 
        }

        async function loadHistory() {
             const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
             const data = await res.json();
             const list = document.getElementById('history-list'); list.innerHTML = "";
             Object.keys(data.chats).reverse().forEach(cid => {
                 list.innerHTML += `<div class="history-item" id="chat-${cid}" onclick="loadChat('${cid}')"><span class="h-title">${data.chats[cid].title || "Chat"}</span><div class="h-actions"><i class="fas fa-pen action-icon" onclick="event.stopPropagation(); renameChat('${cid}')"></i><i class="fas fa-trash action-icon" onclick="event.stopPropagation(); deleteChat('${cid}')"></i></div></div>`;
             });
        }
        async function loadChat(cid) {
            currentChatId = cid;
            const res = await fetch('/get_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
            const data = await res.json();
            const box = document.getElementById('chat-box'); box.innerHTML = "";
            data.messages.forEach(m => {
                let cls = m.role === 'user' ? 'user' : 'ai';
                let content = m.role === 'user' ? m.content : marked.parse(m.content);
                let actions = cls === 'ai' ? `<div class="msg-actions"><i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText(this.closest('.ai-msg').innerText)"></i><i class="fas fa-share-alt action-icon"></i><i class="fas fa-redo action-icon" onclick="document.getElementById('input').value='Regenerate'; send();"></i></div>` : `<div class="msg-actions"><i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText('${m.content}')"></i><i class="fas fa-pen action-icon" onclick="document.getElementById('input').value='${m.content}'; document.getElementById('input').focus();"></i></div>`;
                box.insertAdjacentHTML('beforeend', `<div class="msg ${cls}-msg"><div class="${cls}-content">${content}</div>${actions}</div>`);
            });
            document.getElementById('sidebar').classList.remove('open');
            hljs.highlightAll();
        }
        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }
        function handleFile(input) { if(input.files[0]) { const r = new FileReader(); r.onload=(e)=>{ currentAttachment=e.target.result; document.getElementById('preview-area').style.display='block'; document.getElementById('preview-img').src=currentAttachment; }; r.readAsDataURL(input.files[0]); } }
        function clearAttachment() { currentAttachment=null; document.getElementById('preview-area').style.display='none'; document.getElementById('file-input').value=""; }
        const inp = document.getElementById('input'); const intro = document.getElementById('intro-container');
        if(inp && intro) { inp.addEventListener('focus', () => intro.style.opacity = '0'); inp.addEventListener('blur', () => { if(!document.getElementById('chat-box').innerHTML.includes('msg')) intro.style.opacity = '1'; }); }
        
        checkLogin();
    </script>
</body>
</html>
"""
# --- ROUTES ---
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
    u, cid, msg, ctx = d.get("username"), d.get("chat_id"), d.get("message"), d.get("user_context", "")
    img = d.get("image")
    if u not in user_db: user_db[u] = {}
    if cid not in user_db[u]: user_db[u][cid] = {"messages": []}
    user_db[u][cid]["messages"].append({"role": "user", "content": msg})
    reply = generate_with_retry(msg, img, None, user_db[u][cid]["messages"][:-1], ctx)
    user_db[u][cid]["messages"].append({"role": "model", "content": reply})
    new_title = False
    if len(user_db[u][cid]["messages"]) <= 2:
        user_db[u][cid]["title"] = " ".join(msg.split()[:4])
        new_title = True
    save_db(user_db)
    return jsonify({"response": reply, "new_title": new_title})

# PWA MANIFEST ROUTE
@app.route('/manifest.json')
def manifest():
    data = {
        "name": "Student's AI",
        "short_name": "StudentAI",
        "start_url": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#09090b",
        "theme_color": "#09090b",
        "icons": [
            {
                "src": "https://huggingface.co/spaces/Shirpi/Student-s_AI/resolve/main/1000177401.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://huggingface.co/spaces/Shirpi/Student-s_AI/resolve/main/1000177401.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return Response(json.dumps(data), mimetype='application/json')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)