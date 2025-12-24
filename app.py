# ==========================================
# 👇 PART 1: PYTHON BACKEND 👇
# ==========================================
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

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

# --- CONFIGURATION ---
keys_string = os.environ.get("API_KEYS", "")
API_KEYS = [k.strip() for k in keys_string.replace(',', ' ').replace('\n', ' ').split() if k.strip()]
current_key_index = 0

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- DATABASE ---
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

# --- GEMINI LOGIC ---
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

def process_image_data(image_data):
    try:
        if "base64," in image_data: image_data = image_data.split("base64,")[1]
        image_bytes = base64.b64decode(image_data)
        return Image.open(io.BytesIO(image_bytes))
    except: return None

def generate_with_retry(prompt, image_data=None, history_messages=[], user_context=""):
    global current_key_index
    if not API_KEYS: return "🚨 API Keys Missing."
    
    formatted_history = []
    for m in history_messages[-10:]:
        role = "user" if m["role"] == "user" else "model"
        formatted_history.append({"role": role, "parts": [m["content"]]})
        
    current_parts = []
    system_instruction = f"You are a professional academic AI assistant. The student's profile: {user_context}. Answer precisely."
    full_prompt = f"{system_instruction}\n\nQuestion: {prompt}"
    
    current_parts.append(full_prompt)
    if image_data:
        img = process_image_data(image_data)
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
            if image_data:
                response = model.generate_content(current_parts)
            else:
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(full_prompt)
            return response.text
        except Exception:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            time.sleep(1)
    return "⚠️ Server Busy. Please try again later."
    # ==========================================
# 👇 PART 2: CSS & HEAD 👇
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#000000">
    <title>Student's AI</title>
    
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

    <style>
    /* --- VARIABLES --- */
    :root { 
        --bg: #000000; --card: #18181b; --user-msg: #27272a; 
        --text: #ffffff; --dim: #a1a1aa; --border: #333;
        --input-bg: #1a1a1a;
    }

    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; outline: none; }
    body { 
        margin: 0; background: var(--bg); color: var(--text); 
        font-family: 'Inter', sans-serif; 
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
        overflow: hidden; display: flex; flex-direction: column;
    }

    /* --- HEADER (IMPROVED) --- */
    header {
        height: 70px; padding: 0 15px; 
        background: rgba(0,0,0,0.85); backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--border);
        display: flex; align-items: center; justify-content: space-between; 
        z-index: 50; flex-shrink: 0;
    }
    .header-content { text-align: center; }
    /* 👇 User Requirement: Bigger Name & Professional Font */
    .app-title { font-family: 'Outfit', sans-serif; font-size: 22px; font-weight: 800; letter-spacing: 0.5px; }
    .header-status { font-size: 11px; color: var(--dim); font-weight: 500; margin-top: 2px; }
    .menu-btn { font-size: 20px; padding: 10px; cursor: pointer; color: #fff; }

    /* --- CHAT BOX (GAP FIXED) --- */
    #chat-box { 
        flex: 1; overflow-y: auto; padding: 20px 15px; 
        padding-bottom: 20px; display: flex; flex-direction: column; gap: 20px; 
        scroll-behavior: smooth;
    }

    .msg { display: flex; flex-direction: column; width: 100%; margin-bottom: 5px; }
    .user-msg { align-items: flex-end; }
    .ai-msg { align-items: flex-start; }

    .msg-bubble { 
        padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.6; 
        /* 👇 FIX: Width adjusted to avoid huge gaps */
        max-width: 90%; word-wrap: break-word; position: relative;
    }
    .user-msg .msg-bubble { 
        background: var(--user-msg); color: #fff; border-bottom-right-radius: 4px;
    }
    .ai-msg .msg-bubble { 
        background: transparent; padding-left: 0; color: #ececec; width: 100%; max-width: 100%;
    }

    /* Image in Chat */
    .chat-img { 
        max-width: 100%; border-radius: 12px; margin-bottom: 8px; border: 1px solid var(--border); 
        display: block; max-height: 300px; object-fit: contain; background: #111;
    }
    .user-msg .msg-text { margin-top: 5px; }

    /* Actions */
    .msg-actions { 
        display: flex; gap: 15px; margin-top: 5px; opacity: 0.7; 
        font-size: 12px; padding: 0 2px;
    }
    .action-icon { cursor: pointer; color: var(--dim); transition: color 0.2s; }
    .action-icon:hover { color: #fff; }

    /* --- INPUT AREA (CAMERA OPTION ADDED) --- */
    .input-wrapper { 
        background: var(--bg); padding: 10px 15px; 
        padding-bottom: max(15px, env(safe-area-inset-bottom));
        border-top: 1px solid var(--border); z-index: 60;
    }
    .input-container { 
        background: var(--input-bg); border: 1px solid var(--border); 
        border-radius: 30px; padding: 6px 10px; 
        display: flex; align-items: flex-end; gap: 10px;
    }
    
    /* Plus Button */
    .attach-btn {
        width: 38px; height: 38px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        background: #333; color: #fff; font-size: 18px; cursor: pointer; flex-shrink: 0;
    }
    
    /* Attachment Menu (Popup) */
    #attach-menu {
        position: absolute; bottom: 80px; left: 15px;
        background: #18181b; border: 1px solid var(--border);
        border-radius: 16px; padding: 10px; display: none;
        flex-direction: column; gap: 5px; width: 150px;
        box-shadow: 0 5px 20px rgba(0,0,0,0.5); z-index: 70;
    }
    .attach-opt { 
        padding: 10px; border-radius: 8px; display: flex; align-items: center; gap: 10px; 
        color: #fff; cursor: pointer; font-size: 14px; 
    }
    .attach-opt:active { background: #333; }

    textarea { 
        flex: 1; background: transparent; border: none; color: #fff; 
        font-size: 16px; max-height: 120px; padding: 10px 0; 
        resize: none; font-family: 'Outfit', sans-serif;
    }
    .send-btn { 
        width: 38px; height: 38px; border-radius: 50%;
        background: #fff; color: #000; display: flex; 
        align-items: center; justify-content: center; 
        cursor: pointer; font-size: 16px; flex-shrink: 0; margin-bottom: 2px;
    }

    /* Preview Box */
    #preview-box {
        display: none; padding: 10px 15px; background: var(--bg);
        border-top: 1px solid var(--border);
    }
    .preview-thumb { width: 60px; height: 60px; border-radius: 8px; object-fit: cover; border: 1px solid #444; }
    .preview-close { 
        position: absolute; left: 65px; margin-top: -65px; 
        background: red; color: white; border-radius: 50%; 
        width: 20px; height: 20px; text-align: center; line-height: 20px; font-size: 12px; cursor: pointer; 
    }

    /* --- SIDEBAR & SETTINGS --- */
    #sidebar-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 99; opacity: 0; pointer-events: none; transition: 0.3s; }
    #sidebar-overlay.active { opacity: 1; pointer-events: auto; }

    #sidebar {
        position: fixed; top: 0; left: 0; width: 280px; height: 100%; 
        background: #09090b; z-index: 100; border-right: 1px solid var(--border);
        transform: translateX(-100%); transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
        display: flex; flex-direction: column;
    }
    #sidebar.open { transform: translateX(0); }

    .history-item { 
        padding: 15px; margin: 5px 10px; border-radius: 10px; 
        color: var(--dim); font-size: 14px; 
        display: flex; justify-content: space-between; align-items: center;
        cursor: pointer; transition: 0.2s;
    }
    .history-item:active { background: #222; color: #fff; }

    /* --- SETTINGS PAGES (NEW PAGE STYLE) --- */
    .sub-page {
        position: fixed; inset: 0; background: #000; z-index: 200;
        transform: translateX(100%); transition: transform 0.3s ease;
        display: flex; flex-direction: column;
    }
    .sub-page.active { transform: translateX(0); }
    
    .page-header {
        padding: 20px; border-bottom: 1px solid var(--border);
        display: flex; align-items: center; gap: 15px; font-size: 18px; font-weight: 700;
    }
    .search-bar-wrap {
        margin: 20px; background: #1a1a1a; border-radius: 12px; padding: 12px;
        display: flex; align-items: center; gap: 10px; border: 1px solid var(--border);
    }
    .settings-list { padding: 0 20px; }
    .setting-row {
        padding: 15px 0; border-bottom: 1px solid #222; font-size: 16px;
        display: flex; justify-content: space-between; align-items: center; cursor: pointer;
    }
    
    /* --- LOGIN OVERLAYS --- */
    .overlay { position: fixed; inset: 0; z-index: 6000; background: transparent; display: flex; align-items: center; justify-content: center; }
    .glass-box { width: 90%; max-width: 380px; background: rgba(20,20,20,0.9); border: 1px solid #333; padding: 30px; border-radius: 24px; text-align: center; }
    .global-bg { position: fixed; inset: 0; z-index: 1; background: radial-gradient(circle, #1a0b2e 0%, #000000 100%); }
    .btn-primary { width: 100%; padding: 14px; background: #fff; color: #000; border: none; border-radius: 12px; font-weight: 700; margin-top: 15px; }
    
    /* --- MODAL --- */
    #modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 3000; display: none; align-items: center; justify-content: center; }
    .modal-box { background: #18181b; padding: 25px; border-radius: 20px; width: 85%; max-width: 300px; text-align: center; border: 1px solid #333; }
    .m-btn { flex: 1; padding: 12px; border-radius: 10px; border: none; font-weight: 600; margin-top: 15px; }
    </style>
</head>
# ==========================================
# 👇 PART 3: HTML BODY & JS 👇
# ==========================================
<body>
    <div class="global-bg" id="bg-anim"></div>

    <div id="page-welcome" class="overlay">
        <div class="glass-box">
            <h1 style="font-size:32px; font-weight:800; color:#fff; font-family:'Outfit',sans-serif;">Student's AI</h1>
            <p style="color:#aaa; font-size:14px;">Your ultimate AI companion.</p>
            <button class="btn-primary" onclick="navTo('name')">Get Started</button>
        </div>
    </div>

    <div id="page-name" class="overlay" style="display:none;">
        <div class="glass-box">
            <h2 style="color:#fff;">Who are you?</h2>
            <input type="text" id="inp-name" placeholder="Enter Name" style="width:100%; padding:12px; border-radius:10px; border:1px solid #333; background:#000; color:#fff; margin-top:10px;">
            <button class="btn-primary" onclick="saveName()">Next</button>
        </div>
    </div>

    <div id="page-details" class="overlay" style="display:none;">
        <div class="glass-box">
            <h2 style="color:#fff;">Details</h2>
            <input type="text" id="inp-det" placeholder="Class / Subject" style="width:100%; padding:12px; border-radius:10px; border:1px solid #333; background:#000; color:#fff; margin-top:10px;">
            <button class="btn-primary" onclick="finishSetup()">Start Learning</button>
        </div>
    </div>

    <header id="app-header" style="display:none;">
        <div class="menu-btn" onclick="toggleSidebar(true)"><i class="fas fa-bars"></i></div>
        <div class="header-content">
            <div class="app-title" id="display-name">Student's AI</div>
            <div class="header-status">Ready to master?</div>
        </div>
        <div style="width:40px;"></div>
    </header>

    <div id="chat-box" style="display:none;"></div>

    <div class="input-wrapper" id="app-input" style="display:none;">
        <div id="preview-box">
            <img id="preview-img" class="preview-thumb">
            <div class="preview-close" onclick="clearFile()">×</div>
        </div>

        <div class="input-container">
            <div class="attach-btn" onclick="toggleAttachMenu()"><i class="fas fa-plus"></i></div>
            <textarea id="msg-input" placeholder="Message..." rows="1" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
            <div class="send-btn" onclick="send()"><i class="fas fa-arrow-up"></i></div>
        </div>
        
        <div id="attach-menu">
            <label class="attach-opt"><i class="fas fa-camera" style="color:#00d2ff;"></i> Camera <input type="file" hidden accept="image/*" capture="environment" onchange="handleFile(this)"></label>
            <label class="attach-opt"><i class="fas fa-image" style="color:#bf5af2;"></i> Gallery <input type="file" hidden accept="image/*" onchange="handleFile(this)"></label>
            <label class="attach-opt"><i class="fas fa-file-pdf" style="color:#ff3b30;"></i> File <input type="file" hidden accept="application/pdf" onchange="handleFile(this)"></label>
        </div>
    </div>

    <div id="sidebar-overlay" onclick="toggleSidebar(false)"></div>
    <div id="sidebar">
        <div style="padding:20px; display:flex; justify-content:space-between; border-bottom:1px solid #333;">
            <span style="font-weight:700; font-size:18px;">Menu</span>
            <i class="fas fa-times" style="cursor:pointer; color:#aaa;" onclick="toggleSidebar(false)"></i>
        </div>
        <div style="padding:15px;"><button class="btn-primary" onclick="newChat()">+ New Chat</button></div>
        <div id="history-list" style="flex:1; overflow-y:auto;"></div>
        <div style="padding:20px; border-top:1px solid #333; cursor:pointer;" onclick="openPage('settings')">
            <i class="fas fa-cog"></i> Settings
        </div>
    </div>

    <div id="page-settings" class="sub-page">
        <div class="page-header">
            <i class="fas fa-arrow-left" style="cursor:pointer;" onclick="closePage('settings')"></i> Settings
        </div>
        <div class="search-bar-wrap">
            <i class="fas fa-search" style="color:#aaa;"></i>
            <input type="text" id="set-search" placeholder="Search..." style="background:transparent; border:none; color:#fff; width:100%; outline:none;" oninput="filterSettings(this.value)">
            <i class="fas fa-times" onclick="document.getElementById('set-search').value=''; filterSettings('')" style="color:#aaa; cursor:pointer;"></i>
        </div>
        <div class="settings-list" id="set-list">
            <div class="setting-row" onclick="openPage('profile')"><span>Student Profile</span> <i class="fas fa-chevron-right" style="font-size:12px; color:#666;"></i></div>
            <div class="setting-row" onclick="openPage('theme')"><span>Theme</span> <i class="fas fa-chevron-right" style="font-size:12px; color:#666;"></i></div>
            <div class="setting-row" style="color:#ef4444;" onclick="handleLogout()">Log Out</div>
        </div>
    </div>

    <div id="page-profile" class="sub-page">
        <div class="page-header"><i class="fas fa-arrow-left" style="cursor:pointer;" onclick="closePage('profile')"></i> Profile</div>
        <div style="padding:20px;">
            <p style="color:#aaa; font-size:12px;">NAME</p>
            <div style="font-size:18px; margin-bottom:20px;" id="p-name">--</div>
            <p style="color:#aaa; font-size:12px;">DETAILS</p>
            <div style="font-size:18px;" id="p-det">--</div>
        </div>
    </div>

    <div id="page-theme" class="sub-page">
        <div class="page-header"><i class="fas fa-arrow-left" style="cursor:pointer;" onclick="closePage('theme')"></i> Theme</div>
        <div style="padding:20px;">
            <div class="setting-row" onclick="alert('Dark Mode Active')">Dark Mode <i class="fas fa-check"></i></div>
            <div class="setting-row" onclick="alert('Light Mode Coming Soon')">Light Mode</div>
        </div>
    </div>

    <div id="modal-bg">
        <div class="modal-box">
            <h3 style="margin-top:0; color:#fff;" id="m-title">Alert</h3>
            <input type="text" id="m-input" style="width:100%; padding:10px; background:#000; border:1px solid #333; color:#fff; display:none;">
            <div style="display:flex; gap:10px;">
                <button class="m-btn" style="background:#333; color:#fff;" onclick="closeModal()">Cancel</button>
                <button class="m-btn" style="background:#fff; color:#000;" id="m-ok">Confirm</button>
            </div>
        </div>
    </div>

    <script>
        let currentUser = "", currentChatId = null, currentFile = null;

        // --- NAVIGATION ---
        function navTo(id) {
            document.querySelectorAll('.overlay').forEach(el => el.style.display = 'none');
            document.getElementById('page-' + id).style.display = 'flex';
        }
        function saveName() { currentUser = document.getElementById('inp-name').value; navTo('details'); }
        function finishSetup() {
            document.getElementById('bg-anim').style.display = 'none';
            document.querySelectorAll('.overlay').forEach(el => el.style.display = 'none');
            document.getElementById('app-header').style.display = 'flex';
            document.getElementById('chat-box').style.display = 'flex';
            document.getElementById('app-input').style.display = 'block';
            document.getElementById('display-name').innerText = currentUser || "Student's AI";
            
            // Update Profile Page Data
            document.getElementById('p-name').innerText = currentUser;
            document.getElementById('p-det').innerText = document.getElementById('inp-det').value;
            
            newChat();
        }

        // --- CHAT ---
        function toggleAttachMenu() {
            const m = document.getElementById('attach-menu');
            m.style.display = m.style.display === 'flex' ? 'none' : 'flex';
        }

        function handleFile(input) {
            if(input.files[0]) {
                const r = new FileReader();
                r.onload = (e) => {
                    currentFile = e.target.result;
                    document.getElementById('preview-img').src = currentFile;
                    document.getElementById('preview-box').style.display = 'block';
                    document.getElementById('attach-menu').style.display = 'none';
                };
                r.readAsDataURL(input.files[0]);
            }
        }
        function clearFile() { currentFile = null; document.getElementById('preview-box').style.display = 'none'; }

        async function send() {
            const txt = document.getElementById('msg-input').value.trim();
            if(!txt && !currentFile) return;

            document.getElementById('msg-input').value = "";
            document.getElementById('preview-box').style.display = 'none';
            
            addMsg('user', txt, currentFile);
            let fileData = currentFile; currentFile = null;

            // AI Typing...
            const msgId = "ai-" + Date.now();
            document.getElementById('chat-box').insertAdjacentHTML('beforeend', 
                `<div id="${msgId}" class="msg ai-msg"><div class="msg-bubble" style="color:#aaa;">Thinking...</div></div>`
            );

            // Backend Call
            if(!currentChatId) {
                const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                const d = await r.json(); currentChatId = d.chat_id; loadHistory();
            }

            const res = await fetch('/chat', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body:JSON.stringify({ message: txt, image: fileData, username: currentUser, chat_id: currentChatId })
            });
            const data = await res.json();
            
            // Render Response (Typewriter not needed for simple raw fetch, but Markdown is)
            const aiDiv = document.getElementById(msgId);
            aiDiv.innerHTML = `
                <div class="msg-bubble">
                    ${marked.parse(data.response)}
                    <div class="msg-actions">
                        <i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText('${data.response.substr(0,50)}...')"></i>
                        <i class="fas fa-redo action-icon" onclick="alert('Regenerate')"></i>
                    </div>
                </div>`;
            document.getElementById('chat-box').scrollTo(0, document.getElementById('chat-box').scrollHeight);
        }

        function addMsg(role, text, img) {
            const box = document.getElementById('chat-box');
            let content = "";
            
            if(img) content += `<img src="${img}" class="chat-img" onclick="viewImage('${img}')">`;
            if(text) content += `<div class="msg-text">${text}</div>`;

            box.insertAdjacentHTML('beforeend', 
                `<div class="msg ${role}-msg">
                    <div class="msg-bubble">
                        ${content}
                        ${role==='user' ? `<div class="msg-actions" style="justify-content:flex-end;"><i class="fas fa-pen action-icon"></i></div>` : ''}
                    </div>
                </div>`
            );
            box.scrollTo(0, box.scrollHeight);
        }

        // --- MENU & SETTINGS ---
        function toggleSidebar(open) {
            document.getElementById('sidebar').style.transform = open ? 'translateX(0)' : 'translateX(-100%)';
            document.getElementById('sidebar-overlay').style.opacity = open ? '1' : '0';
            document.getElementById('sidebar-overlay').style.pointerEvents = open ? 'auto' : 'none';
        }

        function newChat() {
            currentChatId = null;
            document.getElementById('chat-box').innerHTML = `
                <div style="text-align:center; margin-top:50px; color:#444;">
                    <h1>Hi ${currentUser},</h1><p>Ready to master?</p>
                </div>`;
            toggleSidebar(false);
        }

        function openPage(id) {
            document.getElementById('page-' + id).style.transform = 'translateX(0)';
        }
        function closePage(id) {
            document.getElementById('page-' + id).style.transform = 'translateX(100%)';
        }

        function filterSettings(val) {
            val = val.toLowerCase();
            const rows = document.querySelectorAll('#set-list .setting-row');
            rows.forEach(row => {
                row.style.display = row.innerText.toLowerCase().includes(val) ? 'flex' : 'none';
            });
        }

        // --- HISTORY & MODAL ---
        let modalCb = null;
        function openModal(title, input, cb) {
            document.getElementById('m-title').innerText = title;
            const inp = document.getElementById('m-input');
            if(input) { inp.style.display='block'; inp.value=''; inp.focus(); } 
            else inp.style.display='none';
            
            document.getElementById('modal-bg').style.display = 'flex';
            modalCb = cb;
        }
        function closeModal() { document.getElementById('modal-bg').style.display='none'; }
        document.getElementById('m-ok').onclick = () => {
            if(modalCb) modalCb(document.getElementById('m-input').value);
            closeModal();
        }

        async function loadHistory() {
            const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
            const data = await res.json();
            const list = document.getElementById('history-list'); list.innerHTML = "";
            Object.keys(data.chats).reverse().forEach(cid => {
                list.innerHTML += `
                <div class="history-item">
                    <span onclick="loadChat('${cid}')">${data.chats[cid].title || 'Chat'}</span>
                    <div style="display:flex; gap:10px;">
                        <i class="fas fa-pen" onclick="renameChat('${cid}')"></i>
                        <i class="fas fa-trash" onclick="deleteChat('${cid}')"></i>
                    </div>
                </div>`;
            });
        }

        function renameChat(cid) {
            openModal("Rename Chat", true, (val) => {
                if(val) fetch('/rename_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid, title:val})}).then(loadHistory);
            });
        }
        function deleteChat(cid) {
            openModal("Delete Chat?", false, () => {
                fetch('/delete_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})}).then(loadHistory);
            });
        }
        async function loadChat(cid) {
            currentChatId = cid; toggleSidebar(false);
            const res = await fetch('/get_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
            const data = await res.json();
            document.getElementById('chat-box').innerHTML = "";
            data.messages.forEach(m => addMsg(m.role==='user'?'user':'ai', m.content));
        }

        function handleLogout() { localStorage.clear(); location.reload(); }
        
        // Initial Check
        if(localStorage.getItem('sai_user')) {
            currentUser = localStorage.getItem('sai_user');
            // Mock skipping login for demo continuity
            // finishSetup(); 
        }
    </script>
</body>
</html>
"""

# ==========================================
# 👇 ROUTES (Paste at end of app.py) 👇
# ==========================================
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
    reply = generate_with_retry(msg, img, user_db[u][cid]["messages"][:-1], ctx)
    user_db[u][cid]["messages"].append({"role": "model", "content": reply})
    
    new_title = False
    if len(user_db[u][cid]["messages"]) <= 2:
        user_db[u][cid]["title"] = " ".join(msg.split()[:4])
        new_title = True
    save_db(user_db)
    return jsonify({"response": reply, "new_title": new_title})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)