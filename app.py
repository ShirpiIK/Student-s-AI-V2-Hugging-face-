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

warnings.filterwarnings("ignore")

# API KEYS
keys_string = os.environ.get("API_KEYS", "")
API_KEYS = [k.strip() for k in keys_string.replace(',', ' ').replace('\n', ' ').split() if k.strip()]

# DATABASE
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

# PROMPT
BASE_INSTRUCTION = """
ROLE: You are "Student's AI", a professional academic tutor.
RULES:
1. **MATH:** Use LaTeX for formulas ($$ ... $$).
2. **FORMAT:** Markdown. Bold key terms.
"""

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
    if user_context: full_prompt = f"[Context: {user_context}]\nQuestion: {prompt}"
    if file_text: current_parts.append(f"File:\n{file_text}\n\n")
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
            model = genai.GenerativeModel(model_name=model_name, system_instruction=BASE_INSTRUCTION)
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
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

        body { 
            margin: 0; background: var(--bg); color: var(--text); 
            font-family: 'Inter', sans-serif; 
            height: 100dvh; width: 100%; overflow: hidden; position: fixed; 
        }
        
        /* HEADER - FIXED TOP (Visible only on Chat) */
        header { 
            height: 70px; padding: 0 20px; background: var(--bg); 
            border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; 
            position: fixed; top: 0; left: 0; right: 0; z-index: 3000; 
            backdrop-filter: blur(10px);
            transition: transform 0.3s ease;
        }
        /* Class to hide header on non-chat pages */
        header.hidden-header { transform: translateY(-100%); pointer-events: none; }
        
        .app-title { font-family: 'Outfit', sans-serif; font-size: 20px; font-weight: 700; color: var(--text); text-align:center; flex:1; }
        .menu-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; cursor: pointer; color:var(--text); z-index:3001; }
        
        /* CONTAINER */
        #app-container { display: flex; flex-direction: column; height: 100%; padding-top: 70px; width:100%; position:relative; }
        #chat-box { 
            flex: 1; overflow-y: auto; padding: 20px 5%; padding-bottom: 120px; 
            display: flex; flex-direction: column; gap: 20px; width:100%; 
            scroll-behavior: smooth; -webkit-overflow-scrolling: touch;
        }
        
        /* INTRO - ANIMATED & PADDED */
        #intro-container { 
            position: absolute; top: 40%; left: 0; width: 100%; 
            padding-left: 25px; padding-right: 25px;
            text-align: left; pointer-events: none; z-index: 10; 
            transition: opacity 0.3s ease;
            animation: fadeIn 0.8s ease-out;
        }

        /* OVERLAYS - FIXED TOP LOCK (NO HEADER GAP NEEDED FOR SOME) */
        .overlay { 
            position: fixed; inset: 0; background: var(--bg); z-index: 2000; 
            display: flex; flex-direction: column; 
            align-items: center; 
            justify-content: flex-start; /* FIX: Top aligned */
            padding-top: 20px; /* Reduced gap since header is hidden */
            padding-bottom: 50px;
            overflow-y: auto; -webkit-overflow-scrolling: touch;
            transition: opacity 0.3s; 
        }
        .overlay.hidden { display: none !important; opacity: 0; pointer-events: none; }
        
        /* DATA BOX - LOCKED & ANIMATED */
        .data-box { 
            width: 90%; max-width: 350px; background: var(--card); 
            border: 1px solid var(--border); border-radius: 20px; 
            padding: 25px; display:flex; flex-direction:column; gap:15px; 
            box-shadow: 0 10px 40px rgba(0,0,0,0.5); 
            flex-shrink: 0; 
            margin-top: 10px; 
            margin-bottom: 50px; 
            position: relative;
            animation: fadeInUp 0.6s ease-out; /* FADE ANIMATION */
        }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        
        .form-label { font-size: 12px; color: var(--dim); margin-left: 2px; margin-bottom:-8px; font-weight:600; text-transform:uppercase; }
        
        input, select { 
            width: 100%; padding: 14px; background: var(--input-bg); 
            border: 1px solid var(--border); color: var(--text); border-radius: 10px; 
            outline: none; font-size: 16px; font-family: 'Inter', sans-serif; appearance: none;
        }
        select { background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='gray' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e"); background-repeat: no-repeat; background-position: right 15px center; background-size: 15px; }
        input:focus, select:focus { border-color: var(--text); }
        .input-error { border: 1px solid #ef4444 !important; }
        
        /* PROFESSIONAL RECTANGULAR CURVE BUTTON */
        .submit-btn, .get-started-btn { 
            width: 100%; padding: 14px; 
            border-radius: 12px; /* Rectangular Curve */
            border: none; background: var(--text); color: var(--bg); 
            font-weight: 700; font-size: 16px; cursor: pointer; 
            margin-top: 10px; font-family: 'Outfit', sans-serif; 
            transition: transform 0.1s;
        }
        .submit-btn:active { transform: scale(0.98); }

        /* WELCOME SCREEN */
        .welcome-container { 
            width: 85%; max-width: 400px; text-align: left; 
            margin-bottom: 30px; margin-top: 50px; 
            animation: fadeIn 1s ease-out; /* Fade Animation */
        }
        .welcome-title { 
            font-family: 'Outfit', sans-serif; font-size: 34px; font-weight: 800; line-height: 1.2; margin-bottom: 15px; 
            background: linear-gradient(to right, var(--text), var(--dim)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .welcome-desc { color: var(--dim); font-size: 15px; line-height: 1.6; margin-bottom: 30px; }

        /* CHAT BUBBLES */
        .msg { display: flex; flex-direction: column; margin-bottom: 20px; opacity: 0; animation: fadeInstant 0.3s forwards; }
        @keyframes fadeInstant { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .user-msg { align-items: flex-end; }
        .user-content { background: var(--user-msg); padding: 12px 18px; border-radius: 18px 18px 4px 18px; max-width: 85%; color: var(--text); font-size: 16px; line-height: 1.5; }
        .ai-msg { align-items: flex-start; width: 100%; }
        .ai-content { width: 100%; color: var(--text); font-size: 16px; line-height: 1.6; }
        .ai-content strong { color: var(--text); font-weight: 700; }
        .ai-content h1, .ai-content h2 { margin-top: 20px; color: var(--text); font-family: 'Outfit', sans-serif; }
        .ai-content pre { background: #111 !important; padding: 15px; border-radius: 10px; overflow-x: auto; margin: 15px 0; border: 1px solid #333; }
        .msg-actions { display: flex; gap: 15px; margin-top: 5px; opacity: 0.7; padding-left: 5px; }
        .action-icon { cursor: pointer; color: var(--dim); font-size: 16px; transition: 0.2s; }
        .action-icon:hover { color: var(--text); transform: scale(1.1); }

        /* INPUT BAR - FIXED BOTTOM */
        .input-wrapper { background: var(--bg); padding: 15px; border-top: 1px solid var(--border); width: 100%; position: fixed; bottom: 0; left: 0; z-index: 40; }
        .input-container { max-width: 900px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 24px; padding: 10px 15px; display: flex; align-items: flex-end; gap: 12px; }
        textarea { flex: 1; background: transparent; border: none; color: var(--text); font-size: 16px; max-height: 120px; padding: 8px 5px; resize: none; outline: none; font-family: 'Inter', sans-serif; }
        .icon-btn, .send-btn { width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: none; cursor: pointer; font-size: 18px; flex-shrink: 0; }
        .icon-btn { background: transparent; color: var(--dim); }
        .send-btn { background: var(--text); color: var(--bg); }

        /* SIDEBAR */
        #sidebar { 
            position: fixed; top: 0; left: 0; width: 300px; height: 100%; 
            background: var(--bg); z-index: 3002; /* Higher than header */
            padding: 25px; padding-top: 80px; 
            transform: translateY(-100%); transition: transform 0.3s ease-in-out; 
            display: flex; flex-direction: column; border-right: 1px solid var(--border); 
            overflow-y: auto;
        }
        #sidebar.open { transform: translateY(0); }
        .history-item { display: flex; justify-content: space-between; align-items: center; padding: 15px; margin-bottom: 8px; background: var(--card); border-radius: 12px; cursor: pointer; color: var(--dim); font-size: 14px; }
        .history-item:active { background: var(--border); color: var(--text); }
        .h-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-right: 10px; }
        
        /* SETTINGS & SEARCH */
        .search-bar-container { position:relative; width:100%; margin-bottom:20px; margin-top: 0px; }
        .search-input { width:100%; background:var(--card); border:none; padding-right:35px; }
        .search-clear { position:absolute; right:10px; top:50%; transform:translateY(-50%); color:var(--dim); cursor:pointer; display:none; }
        
        .settings-container { display:flex; flex-direction:column; gap:0; background: var(--card); border-radius:15px; border:1px solid var(--border); overflow:hidden; }
        .settings-option { padding:15px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; color: var(--text); font-size:16px; }
        .divider { height:1px; background: var(--border); width:100%; }
        
        /* "BACK" BUTTON STYLE */
        .nav-back-btn { font-size: 16px; font-weight: 600; color: var(--text); cursor: pointer; display: flex; align-items: center; gap: 5px; font-family: 'Outfit', sans-serif; }

        /* PROFILE */
        .profile-header { display: flex; flex-direction: column; align-items: center; margin-bottom: 20px; position: relative; }
        .profile-avatar { 
            width: 80px; height: 80px; border-radius: 50%; background: #222; 
            border: 2px solid var(--text); position: relative; margin-bottom: 15px; 
            display: flex; align-items: center; justify-content: center;
        }
        
        /* MODAL */
        #custom-modal { position: fixed; inset:0; background: rgba(0,0,0,0.8); z-index: 4000; display:none; align-items:center; justify-content:center; }
        .modal-box { background: var(--card); padding:25px; border-radius:20px; width:85%; max-width:320px; text-align:center; border:1px solid var(--border); }
        .modal-btn-row { display:flex; gap:10px; margin-top:20px; }

        #preview-area { display:none; position:absolute; bottom:85px; left:20px; z-index:50; }
        .preview-box { width:60px; height:60px; background:#222; border:2px solid #fff; border-radius:12px; overflow:hidden; }
        .preview-img { width:100%; height:100%; object-fit:cover; }

        /* NO RESULTS */
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
        <div class="welcome-container">
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
            
            <div id="sem-container" style="display:none; flex-direction:column; gap:10px;">
                <span class="form-label">Semester</span>
                <select id="edu-sem" onfocus="clearError(this)">
                    <option value="" disabled selected>Select Semester</option>
                </select>
            </div>

            <span class="form-label">Main Subject</span>
            <input type="text" id="edu-subject" placeholder="Ex: Maths, CS..." onfocus="clearError(this)" onkeydown="if(event.key==='Enter') handleDetailsSubmit()">

            <button class="submit-btn" onclick="handleDetailsSubmit()">Start Learning</button>
        </div>
    </div>

    <div id="settings-overlay" class="overlay hidden">
        <div style="width:100%; display:flex; justify-content:flex-start; padding:0 20px; max-width:400px; margin-bottom:10px;">
            <div class="nav-back-btn" onclick="closeSettings()"><i class="fas fa-arrow-left"></i> Back</div>
        </div>
        
        <div style="width:90%; max-width:350px;">
            <div class="search-bar-container">
                <input type="text" id="setting-search" class="search-input" placeholder="Search settings..." oninput="handleSearch(this)">
                <i class="fas fa-times search-clear" id="search-clear-btn" onclick="clearSearch()"></i>
            </div>
            
            <div id="settings-list" class="settings-container">
                <div class="settings-option" data-search="student profile" onclick="openProfileFromSettings()">
                    <span>Student Profile</span> <i class="fas fa-chevron-right" style="font-size:12px;"></i>
                </div>
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
        <div style="width:100%; display:flex; justify-content:flex-start; padding:0 20px; max-width:400px; margin-bottom:10px;">
            <div class="nav-back-btn" onclick="backToSettings()"><i class="fas fa-arrow-left"></i> Back</div>
        </div>
        
        <div class="data-box profile-box" style="margin-top:0;">
            <div class="profile-header">
                <div class="profile-avatar">
                    <img id="profile-pic-display" style="width:100%; height:100%; object-fit:cover; display:none; border-radius:50%;">
                    <i class="fas fa-user" id="profile-icon" style="font-size:30px; color:#fff;"></i>
                    <label for="profile-upload" style="position:absolute; bottom:0; right:-5px; background:var(--text); width:25px; height:25px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer;"><i class="fas fa-camera" style="font-size:12px; color:var(--bg);"></i></label>
                </div>
                <input type="file" id="profile-upload" hidden accept="image/*" onchange="handleProfilePic(this)">
            </div>

            <span class="form-label">Name</span>
            <div class="profile-val" id="p-name">--</div>

            <span class="form-label">Level</span>
            <div class="profile-val" id="p-level">--</div>

            <span class="form-label" id="lbl-year-display">Class/Year</span>
            <div class="profile-val" id="p-year">--</div>
            
            <div id="p-sem-box" style="display:none; flex-direction:column; gap:5px;">
                 <span class="form-label">Semester</span>
                 <div class="profile-val" id="p-sem">--</div>
            </div>

            <span class="form-label">Subject (Tap to Edit)</span>
            <input type="text" id="p-subj-edit" value="">

            <button class="submit-btn" style="background:var(--text); color:var(--bg); margin-top:10px;" onclick="saveProfileChanges()">Save Changes</button>
            <button class="submit-btn" style="background:#ef4444; color:#fff; margin-top:10px;" onclick="handleLogout()">Log Out</button>
        </div>
    </div>

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

    <div id="app-container">
        <header id="main-header" class="hidden-header">
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-bars"></i></div>
            <span class="app-title">Student's AI</span>
            <div style="width:40px;"></div>
        </header>
        <div id="chat-box"></div>
        <div class="input-wrapper">
             <div id="preview-area">
                <div class="preview-box"><img id="preview-img" class="preview-img"></div>
                <button onclick="clearAttachment()" style="background:red; color:white; border:none; border-radius:50%; width:20px; height:20px; position:absolute; top:-5px; right:-5px; z-index:60;">×</button>
            </div>
            <div class="input-container">
                <button class="icon-btn" onclick="document.getElementById('file-input').click()"><i class="fas fa-paperclip"></i></button>
                <input type="file" id="file-input" hidden onchange="handleFile(this)">
                <textarea id="input" placeholder="Type a message..." rows="1" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'" onkeydown="if(event.key==='Enter' && !event.shiftKey){event.preventDefault(); send();}"></textarea>
                <button class="send-btn" onclick="send()"><i class="fas fa-arrow-up"></i></button>
            </div>
        </div>
    </div>
    <script>
        let currentUser = null, currentChatId = null, userContext = "", currentAttachment = null;
        
        function getIntroHtml(name) { 
            return `<div id="intro-container"><div class="welcome-title" style="font-size:28px; margin-bottom:5px; text-align:left;">Hi ${name},</div><p style="color:var(--dim); text-align:left;">Ready to master ${userContext ? userContext.split(',')[0] : "studies"}?</p></div>`; 
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
                // Intro Page - Ensure Header is Hidden
                document.getElementById('main-header').classList.add('hidden-header');
            }
        }
        function clearError(input) { input.classList.remove('input-error'); }
        function showNameBox() { 
            document.getElementById("welcome-overlay").style.display = 'none'; 
            const nameBox = document.getElementById("name-overlay"); 
            nameBox.classList.remove('hidden'); nameBox.style.display = 'flex'; 
        }
        
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
            // SHOW HEADER ONLY ON APP START
            document.getElementById('main-header').classList.remove('hidden-header');
            
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

        // SETTINGS (Search Logic & Header Hiding)
        function openSettings() {
             document.getElementById('settings-overlay').classList.remove('hidden');
             document.getElementById('settings-overlay').style.display = 'flex';
             document.getElementById('sidebar').classList.remove('open');
             // HIDE HEADER
             document.getElementById('main-header').classList.add('hidden-header');
             clearSearch();
        }
        function closeSettings() { 
            document.getElementById('settings-overlay').style.display = 'none'; 
            // SHOW HEADER AGAIN
            document.getElementById('main-header').classList.remove('hidden-header');
        }
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
            // Hide Header for Profile
            document.getElementById('main-header').classList.add('hidden-header');
            
            const pic = localStorage.getItem("student_profile_pic");
            if(pic) {
                document.getElementById('profile-pic-display').src = pic;
                document.getElementById('profile-pic-display').style.display = 'block';
                document.getElementById('profile-icon').style.display = 'none';
            }
        }
        function saveProfileChanges() {
            const newSubj = document.getElementById('p-subj-edit').value;
            const parts = userContext.split(',');
            if(parts[0] === 'college') parts[3] = newSubj;
            else parts[2] = newSubj;
            userContext = parts.join(',');
            localStorage.setItem("student_ai_context", userContext);
            document.getElementById('profile-overlay').style.display = 'none';
            document.getElementById('main-header').classList.remove('hidden-header');
            alert("Saved!");
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
        
        // SEARCH LOGIC
        function toggleSearchClear(el) { document.getElementById('search-clear-btn').style.display = el.value ? 'block' : 'none'; }
        function clearSearch() { 
            const el = document.getElementById('setting-search'); el.value = ''; toggleSearchClear(el); handleSearch(el); 
        }
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

        function handleLogout() { localStorage.clear(); location.reload(); }

        // CHAT & ACTIONS
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
            box.insertAdjacentHTML('beforeend', `<div id="${msgId}" class="msg ai-msg"><div class="ai-content">...</div></div>`);
            
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
                        <i class="fas fa-redo action-icon" onclick="document.getElementById('input').value='Regenerate'; send();"></i>
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

        async function renameChat(cid) { 
            showCustomModal("Rename Chat", true, async (val) => { 
                if(val) { 
                    await fetch('/rename_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid, title:val})}); 
                    loadHistory(); 
                } 
            }); 
        }
        async function deleteChat(cid) { 
            showCustomModal("Delete Chat?", false, async () => { 
                const item = document.getElementById('chat-'+cid); if(item) item.remove();
                await fetch('/delete_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})}); 
                if(currentChatId === cid) newChat(); else loadHistory(); 
            }); 
        }

        async function loadHistory() {
             const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
             const data = await res.json();
             const list = document.getElementById('history-list'); list.innerHTML = "";
             Object.keys(data.chats).reverse().forEach(cid => {
                 list.innerHTML += `<div class="history-item" id="chat-${cid}" onclick="loadChat('${cid}')"><span class="h-title">${data.chats[cid].title || "Chat"}</span><div style="display:flex; gap:10px;"><i class="fas fa-pen action-icon" onclick="event.stopPropagation(); renameChat('${cid}')"></i><i class="fas fa-trash action-icon" onclick="event.stopPropagation(); deleteChat('${cid}')"></i></div></div>`;
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)
