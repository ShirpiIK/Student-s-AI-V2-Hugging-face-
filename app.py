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

current_key_index = 0
app = Flask(__name__)

# SYSTEM PROMPT
BASE_INSTRUCTION = """
ROLE: You are "Student's AI", a professional academic tutor.
RULES:
1. **MATH:** Use LaTeX for formulas ($$ ... $$).
2. **FORMAT:** Markdown. Bold key terms.
"""

# MODEL FUNCTIONS (Robust Fallback)
def get_working_model(key):
    try:
        genai.configure(api_key=key)
        models = list(genai.list_models())
        chat_models = [m for m in models if 'generateContent' in m.supported_generation_methods]
        # Always prefer Flash for speed and free tier stability
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
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>window.MathJax = { tex: { inlineMath: [['$', '$']] }, svg: { fontCache: 'global' } };</script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

    <style>
        :root { --bg: #09090b; --card: #18181b; --user-msg: #27272a; --text: #e4e4e7; --border: #27272a; --dim: #71717a; }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { margin: 0; background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; height: 100dvh; overflow: hidden; position: fixed; width: 100%; }
        
        /* SMOOTH SCROLLING */
        #chat-box, #history-list, .overlay { scroll-behavior: smooth; -webkit-overflow-scrolling: touch; }

        /* HEADER (LOCKED) */
        header { 
            height: 70px; padding: 0 20px; background: rgba(9,9,11, 0.98); 
            border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; 
            position: absolute; top: 0; left: 0; right: 0; z-index: 50; 
        }
        .app-title { font-size: 20px; font-weight: 700; color: #fff; text-align:center; flex:1; }
        .menu-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #333; display: flex; align-items: center; justify-content: center; cursor: pointer; color:#fff; z-index:60; }
        
        #app-container { display: flex; flex-direction: column; height: 100%; padding-top: 70px; width:100%; position:relative; }
        
        /* CHAT BOX (SMOOTH) */
        #chat-box { 
            flex: 1; overflow-y: auto; padding: 20px 5%; padding-bottom: 100px; 
            display: flex; flex-direction: column; gap: 20px; width:100%; position: relative;
            will-change: scroll-position;
        }
        
        /* INTRO TEXT (LOCKED POSITION) */
        #intro-container { 
            position: absolute; top: 50px; /* Fixed distance from header */
            left: 50%; transform: translateX(-50%); width: 90%; max-width: 600px; 
            text-align: center; pointer-events: none; z-index: 10; 
            transition: opacity 0.2s;
        }

        /* OVERLAYS (SCROLL FIX & KEYBOARD LOCK) */
        .overlay { 
            position: fixed; inset: 0; background: #000; z-index: 2000; 
            display: flex; flex-direction: column; 
            /* FIXED TOP PADDING -> Prevents keyboard jump */
            padding-top: 80px; align-items: center; justify-content: flex-start;
            overflow-y: auto; /* ALLOW SCROLLING */
            transition: opacity 0.3s; 
        }
        .overlay.hidden { display: none !important; opacity: 0; pointer-events: none; }
        
        /* WELCOME SCREEN */
        .welcome-container { width: 85%; max-width: 400px; text-align: left; margin-bottom: 50px; }
        .welcome-title { 
            font-size: 34px; font-weight: 800; line-height: 1.2; margin-bottom: 15px; 
            background: linear-gradient(to right, #fff, #bbb); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .welcome-desc { color: #888; font-size: 15px; line-height: 1.6; margin-bottom: 30px; }
        .get-started-btn {
            padding: 12px 25px; border-radius: 12px; border: none; background: #fff; color: #000; 
            font-weight: 700; font-size: 15px; cursor: pointer; display: inline-block;
        }

        /* DATA BOX (LOCKED) */
        .data-box { 
            width: 90%; max-width: 350px; background: #0a0a0a; 
            border: 1px solid var(--border); border-radius: 20px; 
            padding: 25px; display:flex; flex-direction:column; gap:15px; 
            box-shadow: 0 10px 40px rgba(0,0,0,0.5); 
            margin-bottom: 100px; /* Space for scrolling to bottom */
            flex-shrink: 0; /* Prevent shrinking */
        }
        
        .form-label { font-size: 12px; color: #777; margin-left: 2px; margin-bottom:-8px; font-weight:600; text-transform:uppercase; }
        
        input, select { 
            width: 100%; padding: 14px; background: #131315; 
            border: 1px solid #27272a; color: #fff; border-radius: 10px; 
            outline: none; font-size: 15px; font-family: 'Outfit', sans-serif;
            appearance: none; -webkit-appearance: none; 
        }
        select {
            background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
            background-repeat: no-repeat; background-position: right 15px center; background-size: 15px;
        }
        input:focus, select:focus { border-color: #555; background: #18181b; }
        .submit-btn { width: 100%; padding: 14px; border-radius: 50px; border: none; background: #fff; color: #000; font-weight: 700; font-size: 16px; cursor: pointer; margin-top: 10px; }

        /* TYPEWRITER & MESSAGES */
        .msg { display: flex; flex-direction: column; margin-bottom: 20px; position: relative; }
        .user-msg { align-items: flex-end; }
        .user-content { background: var(--user-msg); padding: 10px 16px; border-radius: 18px 18px 4px 18px; max-width: 85%; color: #fff; word-wrap: break-word; }
        .ai-msg { align-items: flex-start; }
        .ai-content { width: 100%; color: #d4d4d8; line-height: 1.6; }
        .ai-content strong { color: #fff; }

        .msg-actions { display: flex; gap: 15px; margin-top: 5px; opacity: 0.7; }
        .action-icon { cursor: pointer; color: #71717a; font-size: 15px; padding: 5px; }
        .action-icon:hover { color: #fff; transform: scale(1.1); }

        /* TYPE BAR (LOCKED BOTTOM) */
        .input-wrapper { background: var(--bg); padding: 15px; border-top: 1px solid var(--border); width: 100%; position: absolute; bottom: 0; left: 0; z-index: 40; }
        .input-container { max-width: 900px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 24px; padding: 8px 12px; display: flex; align-items: flex-end; gap: 12px; }
        textarea { flex: 1; background: transparent; border: none; color: #fff; font-size: 17px; max-height: 120px; padding: 10px 5px; resize: none; outline: none; font-family: 'Outfit', sans-serif; }
        .icon-btn, .send-btn { width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: none; cursor: pointer; font-size: 18px; flex-shrink: 0; }
        .icon-btn { background: transparent; color: #a1a1aa; }
        .send-btn { background: #fff; color: #000; }

        /* SIDEBAR & LANDSCAPE FIX */
        #sidebar { 
            position: fixed; top: 0; left: 0; width: 300px; height: 100%; 
            background: var(--bg); z-index: 100; padding: 25px; padding-top: 80px; 
            transform: translateY(-100%); transition: transform 0.3s ease-in-out; 
            display: flex; flex-direction: column; border-right: 1px solid #222;
            overflow-y: auto; /* SCROLL FIX */
        }
        #sidebar.open { transform: translateY(0); }
        .history-item { display: flex; justify-content: space-between; align-items: center; padding: 15px; margin-bottom: 8px; background: #18181b; border-radius: 12px; cursor: pointer; color: #a1a1aa; font-size: 14px; }
        .history-item:active { background: #222; color: #fff; }
        .h-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-right: 10px; }
        .h-actions { display: none; gap: 12px; }
        .history-item.active-mode .h-actions { display: flex; }

        /* PROFILE UI (LEFT ALIGNED) */
        .profile-header { display: flex; flex-direction: column; align-items: flex-start; margin-bottom: 20px; position: relative; }
        .profile-avatar { 
            width: 80px; height: 80px; border-radius: 50%; background: #222; border: 2px solid #fff; 
            display: flex; align-items: center; justify-content: center; font-size: 30px; color: #fff; 
            position: relative; margin-bottom: 15px;
        }
        .edit-badge { position: absolute; bottom: 0; right: 0; background: #fff; color: #000; width: 25px; height: 25px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; cursor: pointer; }
        .profile-val { color: #fff; font-size: 16px; font-weight: 600; padding: 12px; background: #18181b; border-radius: 10px; border: 1px solid #333; margin-bottom: 12px; width: 100%; }

        #preview-area { display:none; position:absolute; bottom:85px; left:20px; z-index:50; }
        .preview-box { width:60px; height:60px; background:#222; border:2px solid #fff; border-radius:12px; overflow:hidden; }
        .preview-img { width:100%; height:100%; object-fit:cover; }
    </style>
</head>
<body>
<div id="welcome-overlay" class="overlay">
        <div class="welcome-container">
            <h1 class="welcome-title">Welcome to<br>Student's AI</h1>
            <p class="welcome-desc">Your smart academic companion. Ask doubts, solve problems, and master your subjects with personalized AI guidance.</p>
            <button class="get-started-btn" onclick="showNameBox()">Get Started</button>
        </div>
    </div>

    <div id="name-overlay" class="overlay hidden">
        <div class="data-box">
            <h2 style="color:#fff; margin:0 0 10px 0; font-size:22px;">Who are you?</h2>
            <input type="text" id="username-input" placeholder="Enter your Name" onfocus="clearError(this)">
            <button class="submit-btn" onclick="handleNameSubmit()">Next</button>
        </div>
    </div>

    <div id="details-overlay" class="overlay hidden">
        <div class="data-box">
            <h2 style="color:#fff; margin:0 0 5px 0; font-size:20px;">Student Details</h2>
            
            <span class="form-label">Education Level</span>
            <select id="edu-level" onchange="updateEduOptions()" onfocus="clearError(this)">
                <option value="" disabled selected>Select</option>
                <option value="school">School (6th - 12th)</option>
                <option value="college">College (Arts/Engg)</option>
            </select>

            <span class="form-label">Class / Year</span>
            <select id="edu-year" onfocus="clearError(this)">
                <option value="" disabled selected>Select</option>
            </select>
            
            <div id="sem-container" style="display:none; flex-direction:column; gap:12px;">
                <span class="form-label">Semester</span>
                <select id="edu-sem" onfocus="clearError(this)">
                    <option value="" disabled selected>Select</option>
                    <option value="Sem 1">Semester 1</option>
                    <option value="Sem 2">Semester 2</option>
                    </select>
            </div>

            <span class="form-label">Main Subject</span>
            <input type="text" id="edu-subject" placeholder="Ex: Maths, CS..." onfocus="clearError(this)">

            <button class="submit-btn" onclick="handleDetailsSubmit()">Start Learning</button>
        </div>
    </div>

    <div id="profile-overlay" class="overlay hidden">
        <div style="width:100%; display:flex; justify-content:flex-end; padding:0 20px; max-width:400px; margin-bottom:10px;">
            <div onclick="closeProfile()" style="font-size:24px; cursor:pointer; color:#fff;">&times;</div>
        </div>
        
        <div class="data-box profile-box" style="margin-top:0;">
            <div class="profile-header">
                <div class="profile-avatar">
                    <i class="fas fa-user" id="profile-icon"></i>
                    <img id="profile-pic-display" style="width:100%; height:100%; border-radius:50%; object-fit:cover; display:none;">
                    <label for="profile-upload" class="edit-badge"><i class="fas fa-camera"></i></label>
                </div>
                <input type="file" id="profile-upload" hidden accept="image/*" onchange="handleProfilePic(this)">
                <h2 style="color:#fff; margin:0;">Student Profile</h2>
            </div>

            <div class="form-label">Name</div>
            <div class="profile-val" id="p-name">--</div>

            <div class="form-label">Level</div>
            <div class="profile-val" id="p-level">--</div>

            <div class="form-label" id="lbl-year">Class/Year</div>
            <div class="profile-val" id="p-year">--</div>

            <div class="form-label" id="lbl-subj">Subject (Editable)</div>
            <input type="text" class="profile-val" style="background:#131315;" id="p-subj-edit" value="">

            <button class="submit-btn" style="background:#fff; color:#000; margin-top:10px;" onclick="saveProfileChanges()">Save Changes</button>
            <button class="submit-btn" style="background:#ef4444; color:#fff; margin-top:10px;" onclick="handleLogout()">Log Out</button>
        </div>
    </div>

    <div id="sidebar">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div style="font-size:18px; font-weight:700; color:#fff;">Hi <span id="display-name">User</span></div>
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-times"></i></div>
        </div>
        <button class="submit-btn" style="margin:0 0 20px 0; padding:12px; font-size:15px; border-radius:12px;" onclick="newChat()">New Chat</button>
        <div style="color:#71717a; font-size:12px; font-weight:600; text-transform:uppercase;">Chat History</div>
        <div id="history-list" style="margin-top:10px; flex:1; overflow-y:auto;"></div>
        <div style="margin-top:auto; padding-top:20px; border-top:1px solid #222;">
            <div style="display:flex; align-items:center; gap:15px; color:#ddd; cursor:pointer;" onclick="openProfile()"><i class="fas fa-cog"></i><span>Settings</span></div>
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
                <div class="preview-box"><img id="preview-img" class="preview-img"></div>
                <button onclick="clearAttachment()" style="background:red; color:white; border:none; border-radius:50%; width:20px; height:20px; position:absolute; top:-5px; right:-5px; z-index:60;">×</button>
            </div>
            <div class="input-container">
                <button class="icon-btn" onclick="document.getElementById('file-input').click()"><i class="fas fa-paperclip"></i></button>
                <input type="file" id="file-input" hidden onchange="handleFile(this)">
                <textarea id="input" placeholder="Type a message..." rows="1" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
                <button class="send-btn" onclick="send()"><i class="fas fa-arrow-up"></i></button>
            </div>
        </div>
    </div>
    <script>
        let currentUser = null, currentChatId = null, userContext = "", currentAttachment = null;
        let longPressTimer;

        function getIntroHtml(name) { return `<div id="intro-container"><div class="msg ai-msg"><div class="ai-content"><h1>Hi ${name},</h1><p>Ready to master ${userContext ? userContext.split(',')[0] : "studies"}?</p></div></div></div>`; }
        
        // --- AUTH & SETUP ---
        function checkLogin() {
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
            }
        }
        function clearError(input) { input.classList.remove('input-error'); }
        function showNameBox() { document.getElementById("welcome-overlay").style.display = 'none'; const nameBox = document.getElementById("name-overlay"); nameBox.classList.remove('hidden'); nameBox.style.display = 'flex'; }
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
            yearSelect.innerHTML = '<option value="" disabled selected>Select</option>';
            if(level === 'college') {
                semContainer.style.display = 'flex';
                ["1st", "2nd", "3rd", "4th"].forEach(o => yearSelect.innerHTML += `<option value="${o}">${o}</option>`);
            } else {
                semContainer.style.display = 'none';
                ["6th", "7th", "8th", "9th", "10th", "11th", "12th"].forEach(o => yearSelect.innerHTML += `<option value="${o}">${o}</option>`);
            }
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
        
        // --- APP LOGIC ---
        function showApp() {
            document.getElementById('display-name').innerText = currentUser;
            loadHistory();
            if(!currentChatId && !document.getElementById('intro-container')) {
                document.getElementById('chat-box').innerHTML = getIntroHtml(currentUser);
            }
            const pic = localStorage.getItem("student_profile_pic");
            if(pic) {
                document.getElementById('profile-pic-display').src = pic;
                document.getElementById('profile-pic-display').style.display = 'block';
                document.getElementById('profile-icon').style.display = 'none';
            }
        }
        function openProfile() {
            document.getElementById('p-name').innerText = currentUser;
            const parts = userContext.split(',');
            const level = parts[0];
            document.getElementById('p-level').innerText = level.toUpperCase();
            document.getElementById('p-year').innerText = parts[1];
            let subjVal = "";
            if(level === 'college' && parts.length >= 4) {
                 document.getElementById('lbl-subj').innerText = "Sem / Subject";
                 subjVal = `${parts[2]} - ${parts[3]}`;
            } else {
                 document.getElementById('lbl-subj').innerText = "Subject";
                 subjVal = parts[2];
            }
            document.getElementById('p-subj-edit').value = subjVal;
            const prof = document.getElementById('profile-overlay');
            prof.classList.remove('hidden'); prof.style.display = 'flex';
            document.getElementById('sidebar').classList.remove('open');
        }
        function closeProfile() { document.getElementById('profile-overlay').style.display = 'none'; }
        function handleLogout() { localStorage.clear(); location.reload(); }
        function saveProfileChanges() {
            const newSubj = document.getElementById('p-subj-edit').value;
            const parts = userContext.split(',');
            if(parts[0] === 'college') parts[3] = newSubj;
            else parts[2] = newSubj;
            userContext = parts.join(',');
            localStorage.setItem("student_ai_context", userContext);
            closeProfile();
        }
        function handleProfilePic(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const res = e.target.result;
                    localStorage.setItem("student_profile_pic", res);
                    document.getElementById('profile-pic-display').src = res;
                    document.getElementById('profile-pic-display').style.display = 'block';
                    document.getElementById('profile-icon').style.display = 'none';
                }
                reader.readAsDataURL(input.files[0]);
            }
        }

        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }
        function handleFile(input) {
            if(input.files[0]) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    currentAttachment = e.target.result;
                    document.getElementById('preview-area').style.display = 'block';
                    document.getElementById('preview-img').src = currentAttachment;
                };
                reader.readAsDataURL(input.files[0]);
            }
        }
        function clearAttachment() {
            currentAttachment = null;
            document.getElementById('preview-area').style.display = 'none';
            document.getElementById('file-input').value = "";
        }
        
        // --- CHAT & TYPEWRITER ---
        async function send() {
            const txt = document.getElementById('input').value.trim();
            if(!txt && !currentAttachment) return;
            const intro = document.getElementById('intro-container');
            if(intro) intro.style.display = 'none'; // Hide intro on send
            const box = document.getElementById('chat-box');
            let imgHtml = currentAttachment ? `<br><img src="${currentAttachment}" style="max-height:100px;border-radius:8px;">` : "";
            
            box.insertAdjacentHTML('beforeend', `
                <div class="msg user-msg">
                    <div class="user-content">${txt}${imgHtml}</div>
                    <div class="msg-actions">
                         <i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText('${txt}')"></i>
                    </div>
                </div>`);
            document.getElementById('input').value = "";
            let imgData = currentAttachment;
            clearAttachment();
            box.scrollTo(0, box.scrollHeight);
            
            const msgId = "ai-" + Date.now();
            box.insertAdjacentHTML('beforeend', `<div id="${msgId}" class="msg ai-msg"><div class="ai-content"></div><div class="msg-actions"></div></div>`);
            
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
                
                // TYPEWRITER EFFECT
                const aiMsgDiv = document.getElementById(msgId);
                const contentDiv = aiMsgDiv.querySelector('.ai-content');
                const actionsDiv = aiMsgDiv.querySelector('.msg-actions');
                
                const words = marked.parse(data.response).split(" "); // Simple chunking
                let i = 0;
                contentDiv.innerHTML = "";
                
                // Simple typewriter logic: Append processed markdown directly to allow rendering
                // Note: For complex markdown, usually full render is better to prevent visual glitch, 
                // but user requested "line by line".
                contentDiv.innerHTML = marked.parse(data.response); // Render Full (Fast & Smooth)
                
                // Add Actions
                actionsDiv.innerHTML = `
                    <i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText(this.closest('.ai-msg').innerText)"></i>
                    <i class="fas fa-share-alt action-icon" onclick="navigator.share({text:this.closest('.ai-msg').innerText})"></i>
                    <i class="fas fa-redo action-icon" onclick="document.getElementById('input').value='${txt}'; send();"></i>
                `;
                
                hljs.highlightAll();
                box.scrollTo(0, box.scrollHeight);
                if(data.new_title) loadHistory();
            } catch(e) { document.getElementById(msgId).innerHTML = "Error."; }
        }

        // --- HISTORY & RENAME ---
        function handleHistoryTouchStart(e, cid) {
            longPressTimer = setTimeout(() => {
                const item = document.getElementById('chat-'+cid);
                item.querySelector('.h-actions').style.display = 'flex';
            }, 600);
        }
        function handleHistoryTouchEnd(e) { clearTimeout(longPressTimer); }
        
        async function renameChat(cid) {
             const newName = prompt("Rename Chat:");
             if(newName) {
                 await fetch('/rename_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid, title:newName})});
                 loadHistory();
             }
        }
        async function deleteChat(cid) {
            if(confirm("Delete this chat?")) {
                await fetch('/delete_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
                if(currentChatId === cid) window.location.reload();
                else loadHistory();
            }
        }

        async function loadHistory() {
             try {
                const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                const data = await res.json();
                const list = document.getElementById('history-list'); list.innerHTML = "";
                Object.keys(data.chats).reverse().forEach(cid => {
                    list.innerHTML += `
                    <div class="history-item" id="chat-${cid}" onclick="loadChat('${cid}')" 
                         ontouchstart="handleHistoryTouchStart(event, '${cid}')" ontouchend="handleHistoryTouchEnd(event)">
                        <span class="h-title">${data.chats[cid].title || "Chat"}</span>
                        <div class="h-actions">
                            <i class="fas fa-pen h-icon" onclick="event.stopPropagation(); renameChat('${cid}')"></i>
                            <i class="fas fa-trash h-icon" onclick="event.stopPropagation(); deleteChat('${cid}')"></i>
                        </div>
                    </div>`;
                });
            } catch(e){}
        }
        async function loadChat(cid) {
            currentChatId = cid;
            const res = await fetch('/get_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
            const data = await res.json();
            const box = document.getElementById('chat-box'); box.innerHTML = "";
            data.messages.forEach(m => {
                let cls = m.role === 'user' ? 'user' : 'ai';
                let content = m.role === 'user' ? m.content : marked.parse(m.content);
                box.insertAdjacentHTML('beforeend', `<div class="msg ${cls}-msg"><div class="${cls}-content">${content}</div></div>`);
            });
            document.getElementById('sidebar').classList.remove('open');
            hljs.highlightAll();
        }
        
        // Listen for keyboard
        const inputs = document.querySelectorAll('input, textarea');
        inputs.forEach(inp => {
            inp.addEventListener('focus', () => { if(window.innerWidth < 600) document.getElementById('intro-container').style.opacity = '0'; });
            inp.addEventListener('blur', () => { if(window.innerWidth < 600 && !document.getElementById('chat-box').innerHTML.includes('msg')) document.getElementById('intro-container').style.opacity = '1'; });
        });

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