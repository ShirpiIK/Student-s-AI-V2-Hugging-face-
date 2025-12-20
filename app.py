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

# --- UI TEMPLATE (Fixed Quotes & Logic) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, interactive-widget=resizes-content">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#09090b">
    <link rel="manifest" href="/manifest.json">
    <title>Student's AI</title>
    
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
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
        :root {
            --bg: #09090b; --card: #18181b; --user-msg: #27272a; --text: #e4e4e7;
            --accent: #fff; --border: #27272a; --dim: #71717a;
        }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        
        body, html { 
            margin: 0; padding: 0; height: 100dvh; width: 100%; max-width: 100%;
            background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; 
            overflow: hidden; font-size: 17px;
            -webkit-user-select: none; user-select: none;
        }

        textarea, input { -webkit-user-select: text !important; user-select: text !important; }
        .user-content, .ai-content, code, pre { -webkit-user-select: none !important; user-select: none !important; }

        /* --- APP CONTAINER (Pushed down for Header) --- */
        #app-container { 
            display: flex; flex-direction: column; 
            height: 100dvh; width: 100%; 
            position: relative; overflow-x: hidden;
            padding-top: 70px; /* Space for fixed header */
        }

        /* --- HEADER LOCKED --- */
        header {
            height: 70px; padding: 0 20px; background: rgba(9,9,11, 0.98);
            border-bottom: 1px solid var(--border-color);
            display: flex; align-items: center; justify-content: space-between; 
            z-index: 50;
            padding-top: env(safe-area-inset-top);
            position: absolute; top: 0; left: 0; right: 0;
        }
        .menu-btn {
            width: 40px; height: 40px; border-radius: 50%; border: 1px solid #333;
            display: flex; align-items: center; justify-content: center; cursor: pointer;
            transition: 0.2s; color: #fff;
        }
        .menu-btn:active { transform: scale(0.95); background: #222; }
        .app-title { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; color: #fff; }

        /* --- SIDEBAR ANIMATION --- */
        #sidebar {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: var(--bg); z-index: 100; 
            display: flex; flex-direction: column; padding: 25px;
            padding-top: calc(70px + env(safe-area-inset-top));
            transform: translateY(-100%);
            transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            overflow-y: auto;
        }
        #sidebar.open { transform: translateY(0); }
        
        @media (min-width: 768px) {
            #sidebar { width: 350px; border-right: 1px solid var(--border); }
            .input-container { max-width: 800px; }
            #chat-box { padding: 20px 15%; }
        }

        .user-info { margin-bottom: 30px; font-size: 20px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 15px; flex-shrink: 0; }
        .new-chat-btn {
            width: 100%; padding: 15px; background: #fff; color: #000; border: none; 
            border-radius: 12px; font-weight: 700; font-size: 16px; cursor: pointer; margin-bottom: 25px; flex-shrink: 0;
        }
        
        .history-label { color: var(--dim); font-size: 13px; font-weight: 600; margin-bottom: 10px; letter-spacing: 1px; text-transform: uppercase; flex-shrink: 0; }
        #history-list { flex: 1; overflow-y: auto; padding: 10px 0; min-height: 100px; }
        
        .history-item { 
            display: flex; justify-content: space-between; align-items: center;
            padding: 15px; margin-bottom: 12px; background: var(--card); border: 1px solid var(--border); border-radius: 12px;
            cursor: pointer; color: #a1a1aa; font-size: 15px; transition: 0.2s;
        }
        .history-item:active { background: #222; color: #fff; border-color: #444; }
        .h-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px; flex: 1; margin-right: 10px; }
        .h-actions { display: none; gap: 15px; }
        .history-item.active-mode .h-actions { display: flex; }
        .h-icon { font-size: 16px; color: #fff; padding: 5px; }
        
        .rename-input {
            background: transparent; border: none; border-bottom: 1px solid #fff;
            color: #fff; font-family: 'Outfit', sans-serif; font-size: 15px;
            width: 100%; outline: none; padding: 0;
        }

        .brand-section { text-align: center; margin-top: 20px; padding-bottom: env(safe-area-inset-bottom); flex-shrink: 0; }
        .brand-name { font-family: 'Outfit', sans-serif; font-weight: 600; font-size: 12px; color: var(--dim); letter-spacing: 2px; margin-bottom: 10px; opacity: 0.6; }
        .logout-btn { color: #ef4444; cursor: pointer; font-size: 15px; font-weight: 600; padding: 10px; }

        #chat-box {
            flex: 1; overflow-y: auto; padding: 20px 5%; padding-bottom: 80px; 
            display: flex; flex-direction: column; gap: 25px;
            -webkit-overflow-scrolling: touch; overscroll-behavior-y: contain; min-height: 0; 
        }
        
        /* --- LOCKED INTRO TEXT --- */
        #intro-container {
            position: absolute;
            top: 140px; /* Fixed from top so it won't move up with keyboard */
            left: 50%;
            transform: translateX(-50%);
            width: 90%; max-width: 600px;
            text-align: center;
            z-index: 10;
            pointer-events: none;
        }

        .msg { width: 100%; line-height: 1.7; font-size: 17px; opacity: 0; animation: fadeInstant 0.3s forwards; display: flex; flex-direction: column; }
        @keyframes fadeInstant { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        .user-msg { align-items: flex-end; }
        .user-content { display: inline-block; width: fit-content; max-width: 85%; background: var(--user-msg); padding: 10px 16px; border-radius: 18px 18px 4px 18px; text-align: left; color: #fff; word-wrap: break-word; }
        
        .ai-msg { align-items: flex-start; }
        .ai-content { width: 100%; color: #d4d4d8; word-wrap: break-word; }
        .ai-content strong { color: #fff; font-weight: 700; }
        .ai-content h1, .ai-content h2 { margin-top: 20px; color: #fff; font-weight: 700; }
        .ai-content img, .user-content img { cursor: pointer; transition: 0.2s; }
        .ai-content img:active, .user-content img:active { transform: scale(0.98); }

        pre { background: #1e1e1e !important; border-radius: 12px; padding: 15px; overflow-x: auto; margin: 15px 0; border: 1px solid #333; max-width: 100%; }
        code { font-family: 'JetBrains Mono', monospace; font-size: 14px; }
        .mjx-chtml { background: #18181b; padding: 10px; border-radius: 8px; border: 1px solid #333; overflow-x: auto; margin: 10px 0; text-align: center; max-width: 100%; }
        .mermaid { background: #111; padding: 15px; border-radius: 10px; text-align: center; margin: 15px 0; overflow-x: auto; }

        .msg-actions { margin-top: 10px; opacity: 0; transition: opacity 0.2s; display: flex; gap: 20px; align-items: center; }
        .user-msg .msg-actions { justify-content: flex-end; }
        .msg:hover .msg-actions { opacity: 1; }
        .action-icon { cursor: pointer; color: var(--dim); font-size: 18px; transition: 0.2s; }
        .action-icon:hover { color: #fff; transform: scale(1.1); }

        .input-wrapper { background: var(--bg); padding: 15px; border-top: 1px solid var(--border); flex-shrink: 0; z-index: 60; padding-bottom: max(15px, env(safe-area-inset-bottom)); }
        .input-container { max-width: 900px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 24px; padding: 8px 12px; display: flex; align-items: flex-end; gap: 12px; }
        textarea { flex: 1; background: transparent; border: none; color: #fff; font-size: 17px; max-height: 120px; padding: 10px 5px; resize: none; outline: none; font-family: 'Outfit', sans-serif; }
        .icon-btn { width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: none; background: transparent; color: #a1a1aa; cursor: pointer; font-size: 18px; }
        .send-btn { background: #fff; color: #000; width: 38px; height: 38px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 18px; }

        #preview-area { position: absolute; bottom: 85px; left: 20px; display: none; z-index: 70; }
        .preview-box { width: 60px; height: 60px; border-radius: 12px; border: 2px solid #fff; background: #222; overflow: hidden; position: relative; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        .preview-img { width: 100%; height: 100%; object-fit: cover; }
        .remove-preview { position: absolute; top: -8px; right: -8px; background: red; color: white; border-radius: 50%; width: 20px; height: 20px; font-size: 12px; cursor: pointer; border: none; display: flex; align-items: center; justify-content: center; }

        /* --- LOGIN PAGE LOCKED (FIXED) --- */
        #login-overlay { 
            position: fixed; inset: 0; background: #000; z-index: 2000; 
            display: flex; 
            /* Align to START (Top) to prevent centering jump */
            align-items: flex-start; justify-content: center;
            /* Force padding from top so it never moves */
            padding-top: 180px; 
            transition: opacity 0.8s ease; opacity: 1; pointer-events: auto;
        }
        #login-overlay.hidden { opacity: 0; pointer-events: none; }
        
        .login-box { 
            width: 90%; max-width: 350px; text-align: center; 
            padding: 40px; border: 1px solid var(--border); border-radius: 20px; background: #0a0a0a; 
            /* No auto margins */
        }

        #image-modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 3000; display: none; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.3s; }
        #image-modal img { max-width: 95%; max-height: 90%; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.8); }
        #image-modal.active { opacity: 1; }
    </style>
</head>
<body>

    <div id="login-overlay">
        <div class="login-box">
            <h1 class="app-title" style="margin-bottom:10px;">Student's AI</h1>
            <input type="text" id="username-input" placeholder="Your Name" style="width:100%; padding:15px; border-radius:12px; border:1px solid #333; background:#111; color:#fff; text-align:center; outline:none; margin-bottom:20px; font-size: 16px;" onkeydown="if(event.key==='Enter') handleLogin()">
            <button onclick="handleLogin()" style="width:100%; padding:15px; border-radius:12px; border:none; background:#fff; font-weight:800; cursor:pointer; font-size: 16px;">Start Learning</button>
        </div>
    </div>

    <div id="image-modal" onclick="closeImagePreview()">
        <img id="modal-img" src="" alt="Preview">
    </div>

    <div id="sidebar">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-shrink:0;">
            <div class="user-info"><span id="display-name">User</span></div>
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-times"></i></div>
        </div>
        <button class="new-chat-btn" onclick="newChat()">New Chat</button>
        <div class="history-label">Chat History</div>
        <div id="history-list"></div>
        <div class="brand-section">
            <div class="brand-name">Designed by Shirpi</div>
            <div class="logout-btn" onclick="handleLogout()">Log Out</div>
        </div>
    </div>

    <div id="app-container">
        <header>
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-bars"></i></div>
            <span class="app-title">Student's AI</span>
            <div style="width:40px;"></div>
        </header>

        <div id="chat-box"></div>

        <div class="input-wrapper">
            <div id="preview-area">
                <div class="preview-box"><div id="preview-visual"></div></div>
                <button class="remove-preview" onclick="clearAttachment()">×</button>
            </div>
            
            <div class="input-container">
                <button class="icon-btn" onclick="document.getElementById('file-input').click()"><i class="fas fa-paperclip"></i></button>
                <input type="file" id="file-input" accept="image/*,.txt,.py,.js,.html,.css,.md,.csv,.json" hidden onchange="handleFileSelect(this)">
                
                <button class="icon-btn" onclick="document.getElementById('camera-input').click()"><i class="fas fa-camera"></i></button>
                <input type="file" id="camera-input" accept="image/*" capture="environment" hidden onchange="handleFileSelect(this)">
                
                <textarea id="input" placeholder="Type a message..." rows="1" oninput="resizeInput(this)"></textarea>
                
                <button class="send-btn" onclick="send()"><i class="fas fa-arrow-up"></i></button>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let currentChatId = null;
        let currentAttachment = { type: null, data: null, name: null };
        let longPressTimer;
        
        // --- FIXED INTRO: LOCKED CONTAINER ---
        function getIntroHtml(name) {
            return `<div id="intro-container"><div class="msg ai-msg"><div class="ai-content"><h1>Hi ${name},</h1><p>Ready to master your studies today?</p></div></div></div>`;
        }

        // --- AUTH LOGIC (SMOOTH TRANSITION) ---
        function checkLogin() {
            try {
                const stored = localStorage.getItem("student_ai_user");
                if (stored) { 
                    currentUser = stored; 
                    document.getElementById("login-overlay").classList.add('hidden'); 
                    showApp(); 
                }
            } catch(e) { console.log("Storage access denied"); }
        }
        
        function handleLogin() {
            const input = document.getElementById("username-input");
            const name = input.value.trim();
            if(name) { 
                try { localStorage.setItem("student_ai_user", name); } catch(e){}
                currentUser = name; 
                // FORCE HIDE DIRECTLY
                const overlay = document.getElementById("login-overlay");
                overlay.classList.add('hidden');
                setTimeout(() => overlay.style.display = 'none', 500); 
                showApp(); 
            } else {
                input.style.border = "1px solid red"; 
                setTimeout(() => input.style.border = "1px solid #333", 2000);
            }
        }
        function handleLogout() { 
            try { localStorage.removeItem("student_ai_user"); } catch(e){}
            const overlay = document.getElementById("login-overlay");
            overlay.style.display = 'flex';
            setTimeout(() => overlay.classList.remove('hidden'), 10);
            document.getElementById('sidebar').classList.remove('open');
            setTimeout(() => {
                document.getElementById('chat-box').innerHTML = "";
                currentChatId = null;
                document.getElementById("username-input").value = "";
            }, 500);
        }
        
        function showApp() {
            document.getElementById("display-name").innerText = "Hi " + currentUser;
            loadHistory();
            if(!currentChatId) {
                const box = document.getElementById("chat-box");
                if(box.innerHTML === "") {
                    box.innerHTML = getIntroHtml(currentUser);
                }
            }
        }

        function resizeInput(el) {
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 150) + 'px';
        }

        function handleFileSelect(input) {
            if (input.files && input.files[0]) {
                const file = input.files[0];
                const reader = new FileReader();
                reader.onload = function(e) {
                    const result = e.target.result;
                    const isImage = file.type.startsWith('image/');
                    currentAttachment = { type: isImage ? 'image' : 'file', data: isImage ? result : atob(result.split(',')[1]), name: file.name };
                    const previewArea = document.getElementById('preview-area');
                    const visual = document.getElementById('preview-visual');
                    previewArea.style.display = 'block';
                    visual.innerHTML = isImage ? `<img src="${result}" class="preview-img">` : `<div class="preview-file-icon"><i class="fas fa-file-alt"></i></div>`;
                }
                reader.readAsDataURL(file);
            }
            input.value = "";
        }

        function clearAttachment() {
            currentAttachment = { type: null, data: null, name: null };
            document.getElementById('preview-area').style.display = 'none';
        }

        function scrollToBottom() {
            const box = document.getElementById('chat-box');
            setTimeout(() => {
                box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
            }, 100);
        }

        async function send() {
            const input = document.getElementById('input');
            const text = input.value.trim();
            if (!text && !currentAttachment.data) return;

            // --- REMOVE INTRO TEXT AUTOMATICALLY ---
            const intro = document.getElementById('intro-container');
            if(intro) { intro.style.display = 'none'; intro.remove(); }

            const chatBox = document.getElementById('chat-box');
            let attachHtml = '';
            if (currentAttachment.type === 'image') attachHtml = `<br><img src="${currentAttachment.data}" style="max-height:100px; margin-top:10px; border-radius:8px;">`;
            if (currentAttachment.type === 'file') attachHtml = `<br><small>📄 ${currentAttachment.name}</small>`;

            const userHtml = `
                <div class="msg user-msg">
                    <div class="user-content">${text.replace(/</g, "&lt;")}${attachHtml}</div>
                    <div class="msg-actions">
                         <i class="fas fa-copy action-icon" onclick="copyText('${text}')"></i>
                         <i class="fas fa-pen action-icon" onclick="editMessage('${text}')"></i>
                    </div>
                </div>`;
            chatBox.insertAdjacentHTML('beforeend', userHtml);
            
            const promptText = text;
            const imgData = currentAttachment.type === 'image' ? currentAttachment.data : null;
            const fileText = currentAttachment.type === 'file' ? currentAttachment.data : null;

            input.value = ''; input.style.height = 'auto';
            clearAttachment();
            scrollToBottom();

            const msgId = "ai-" + Date.now();
            chatBox.insertAdjacentHTML('beforeend', `<div id="${msgId}" class="msg ai-msg"><i class="fas fa-circle-notch fa-spin"></i></div>`);
            scrollToBottom();

            try {
                if (!currentChatId) {
                    const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                    const d = await r.json(); currentChatId = d.chat_id;
                    loadHistory();
                }
                const res = await fetch('/chat', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: promptText, image: imgData, file_text: fileText, username: currentUser, chat_id: currentChatId })
                });
                const data = await res.json();
                
                const aiDiv = document.getElementById(msgId);
                aiDiv.innerHTML = ""; 
                const contentDiv = document.createElement('div');
                contentDiv.className = 'ai-content';
                aiDiv.appendChild(contentDiv);

                await typeWriter(contentDiv, data.response);

                aiDiv.insertAdjacentHTML('beforeend', `
                    <div class="msg-actions">
                        <i class="fas fa-copy action-icon" onclick="copyAiResponse(this)"></i>
                        <i class="fas fa-share-alt action-icon" onclick="shareResponse(this)"></i>
                        <i class="fas fa-redo action-icon" onclick="regenerate('${promptText}')"></i>
                    </div>`);

                scrollToBottom();
                if(data.new_title) loadHistory();
            } catch (e) { document.getElementById(msgId).innerHTML = "⚠️ Error: " + e.message; }
        }

        function copyText(text) { navigator.clipboard.writeText(text); }
        function copyAiResponse(btn) {
            const text = btn.closest('.ai-msg').querySelector('.ai-content').innerText;
            navigator.clipboard.writeText(text);
        }
        function shareResponse(btn) {
            const text = btn.closest('.ai-msg').querySelector('.ai-content').innerText;
            if (navigator.share) navigator.share({ title: 'Student AI', text: text });
            else navigator.clipboard.writeText(text);
        }
        function editMessage(oldText) { document.getElementById('input').value = oldText; document.getElementById('input').focus(); }
        function regenerate(text) { document.getElementById('input').value = text; send(); }
        
        document.getElementById('chat-box').addEventListener('click', function(e) {
            if(e.target.tagName === 'IMG') {
                const modal = document.getElementById('image-modal');
                const modalImg = document.getElementById('modal-img');
                modalImg.src = e.target.src;
                modal.style.display = 'flex';
                setTimeout(() => modal.classList.add('active'), 10);
            }
        });
        function closeImagePreview() {
            const modal = document.getElementById('image-modal');
            modal.classList.remove('active');
            setTimeout(() => modal.style.display = 'none', 300);
        }

        function handleHistoryTouchStart(e, cid) {
            longPressTimer = setTimeout(() => {
                e.target.closest('.history-item').classList.add('active-mode');
            }, 600);
        }
        function handleHistoryTouchEnd(e) { clearTimeout(longPressTimer); }
        
        function startRename(cid) {
            const item = document.getElementById('chat-' + cid);
            const titleSpan = item.querySelector('.h-title');
            const currentTitle = titleSpan.innerText;
            const input = document.createElement('input');
            input.type = 'text'; input.value = currentTitle; input.className = 'rename-input';
            
            async function save() {
                const newTitle = input.value.trim();
                if(newTitle && newTitle !== currentTitle) {
                    await fetch('/rename_chat', {
                        method:'POST', headers:{'Content-Type':'application/json'}, 
                        body:JSON.stringify({username:currentUser, chat_id:cid, title:newTitle})
                    });
                    loadHistory();
                } else { loadHistory(); }
            }
            input.addEventListener('blur', save);
            input.addEventListener('keydown', (e) => { if(e.key === 'Enter') { input.blur(); } });
            titleSpan.replaceWith(input); input.focus();
        }

        async function deleteChat(cid) {
            const el = document.getElementById('chat-' + cid);
            if(el) el.remove();
            await fetch('/delete_chat', {
                method:'POST', headers:{'Content-Type':'application/json'}, 
                body:JSON.stringify({username:currentUser, chat_id:cid})
            });
            if(currentChatId === cid) newChat(); 
            loadHistory();
        }

        async function loadHistory() {
            try {
                const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                const data = await res.json();
                const list = document.getElementById('history-list'); list.innerHTML = "";
                if (data.chats) {
                    Object.keys(data.chats).reverse().forEach(cid => {
                        const title = data.chats[cid].title || "New Chat";
                        list.innerHTML += `
                        <div class="history-item" id="chat-${cid}" onclick="loadChat('${cid}')" oncontextmenu="return false;"
                             ontouchstart="handleHistoryTouchStart(event, '${cid}')" ontouchend="handleHistoryTouchEnd(event)">
                            <span class="h-title">${title}</span>
                            <div class="h-actions">
                                <i class="fas fa-pen h-icon" onclick="event.stopPropagation(); startRename('${cid}')"></i>
                                <i class="fas fa-trash h-icon" onclick="event.stopPropagation(); deleteChat('${cid}')"></i>
                            </div>
                        </div>`;
                    });
                }
            } catch(e) {}
        }

        async function typeWriter(element, markdownText) {
            element.innerHTML = marked.parse(markdownText);
            hljs.highlightAll(); 
            if (window.MathJax) await MathJax.typesetPromise([element]);
            if (window.mermaid) {
                 const m = element.querySelectorAll('code.language-mermaid');
                 m.forEach(c => { const d = document.createElement('div'); d.className='mermaid'; d.innerHTML=c.innerText; c.parentElement.replaceWith(d); });
                 window.mermaid.init(undefined, element.querySelectorAll('.mermaid'));
            }
            element.style.opacity = 0; element.style.transition = 'opacity 0.4s';
            setTimeout(() => { element.style.opacity = 1; scrollToBottom(); }, 50);
        }

        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }
        async function newChat() {
            currentChatId = null; 
            document.getElementById('chat-box').innerHTML = getIntroHtml(currentUser);
            const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
            const d = await r.json(); currentChatId = d.chat_id; loadHistory();
            document.getElementById('sidebar').classList.remove('open');
        }
        async function loadChat(cid) {
            currentChatId = cid; const res = await fetch('/get_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
            const data = await res.json(); const box = document.getElementById('chat-box'); box.innerHTML = "";
            data.messages.forEach(msg => {
                const isUser = msg.role === 'user';
                if(isUser) {
                    box.insertAdjacentHTML('beforeend', `<div class="msg user-msg"><div class="user-content">${msg.content.replace(/</g, "&lt;")}</div></div>`);
                } else {
                    const div = document.createElement('div'); div.className = 'msg ai-msg';
                    div.innerHTML = `<div class="ai-content">${marked.parse(msg.content)}</div>`;
                    box.appendChild(div);
                    hljs.highlightAll();
                    if(window.MathJax) MathJax.typesetPromise([div]);
                    div.insertAdjacentHTML('beforeend', `<div class="msg-actions"><i class="fas fa-copy action-icon" onclick="copyAiResponse(this)"></i></div>`);
                }
            });
            document.getElementById('sidebar').classList.remove('open');
            box.scrollTop = box.scrollHeight;
        }

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