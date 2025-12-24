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

# --- UI TEMPLATE (UPDATED: 3-Page Onboarding) ---

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

        textarea, input, select { -webkit-user-select: text !important; user-select: text !important; }
        .user-content, .ai-content, code, pre { -webkit-user-select: none !important; user-select: none !important; }

        /* --- APP CONTAINER --- */
        #app-container { 
            display: flex; flex-direction: column; height: 100dvh; width: 100%; 
            position: relative; overflow-x: hidden; padding-top: 70px;
        }

        /* --- HEADER --- */
        header {
            height: 70px; padding: 0 20px; background: rgba(9,9,11, 0.98);
            border-bottom: 1px solid var(--border-color);
            display: flex; align-items: center; justify-content: space-between; 
            z-index: 50; padding-top: env(safe-area-inset-top);
            position: absolute; top: 0; left: 0; right: 0;
        }
        .menu-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #333; display: flex; align-items: center; justify-content: center; cursor: pointer; color: #fff; }
        .app-title { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; color: #fff; }

        /* --- SIDEBAR --- */
        #sidebar {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: var(--bg); z-index: 100; display: flex; flex-direction: column; padding: 25px;
            padding-top: calc(70px + env(safe-area-inset-top));
            transform: translateY(-100%); transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            overflow-y: auto;
        }
        #sidebar.open { transform: translateY(0); }
        .user-info { font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 30px; }
        .new-chat-btn { width: 100%; padding: 15px; background: #fff; color: #000; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; margin-bottom: 25px; }
        .history-label { color: var(--dim); font-size: 13px; font-weight: 600; margin-bottom: 10px; text-transform: uppercase; }
        #history-list { flex: 1; overflow-y: auto; }
        .history-item { padding: 15px; margin-bottom: 12px; background: var(--card); border: 1px solid var(--border); border-radius: 12px; cursor: pointer; color: #a1a1aa; display: flex; justify-content: space-between; align-items: center; }
        .brand-section { text-align: center; margin-top: 20px; }
        .logout-btn { color: #ef4444; cursor: pointer; font-size: 15px; font-weight: 600; padding: 10px; }

        /* --- CHAT AREA --- */
        #chat-box { flex: 1; overflow-y: auto; padding: 20px 5%; padding-bottom: 80px; display: flex; flex-direction: column; gap: 25px; }
        
        #intro-container { position: absolute; top: 140px; left: 50%; transform: translateX(-50%); width: 90%; max-width: 600px; text-align: center; z-index: 10; pointer-events: none; }
        .msg { width: 100%; line-height: 1.7; font-size: 17px; opacity: 0; animation: fadeInstant 0.3s forwards; display: flex; flex-direction: column; }
        @keyframes fadeInstant { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .user-msg { align-items: flex-end; }
        .user-content { display: inline-block; width: fit-content; max-width: 85%; background: var(--user-msg); padding: 10px 16px; border-radius: 18px 18px 4px 18px; color: #fff; }
        .ai-msg { align-items: flex-start; }
        .ai-content { width: 100%; color: #d4d4d8; }
        .ai-content strong { color: #fff; font-weight: 700; }
        
        pre { background: #1e1e1e !important; border-radius: 12px; padding: 15px; overflow-x: auto; margin: 15px 0; border: 1px solid #333; }
        code { font-family: 'JetBrains Mono', monospace; font-size: 14px; }
        .mermaid { background: #111; padding: 15px; border-radius: 10px; }
        
        .input-wrapper { background: var(--bg); padding: 15px; border-top: 1px solid var(--border); flex-shrink: 0; z-index: 60; padding-bottom: max(15px, env(safe-area-inset-bottom)); }
        .input-container { max-width: 900px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 24px; padding: 8px 12px; display: flex; align-items: flex-end; gap: 12px; }
        textarea { flex: 1; background: transparent; border: none; color: #fff; font-size: 17px; max-height: 120px; padding: 10px 5px; resize: none; outline: none; font-family: 'Outfit', sans-serif; }
        .icon-btn, .send-btn { width: 38px; height: 38px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .icon-btn { background: transparent; color: #a1a1aa; }
        .send-btn { background: #fff; color: #000; }

        /* --- 🚀 ONBOARDING OVERLAY (PREMIUM FIX) --- */
        /* --- FIXED: ANIMATED ONBOARDING OVERLAY --- */
#onboarding-overlay { 
    position: fixed; 
    top: 0;
    left: 0;
    width: 100vm;
    height: 100vmax;
    z-index: 2000; 
    display: flex; 
    align-items: center; 
    justify-content: center;
    transition: opacity 0.6s ease; 
    opacity: 1; 
    pointer-events: auto;
    
    /* Deep Black Base */
    background-color: #050505; 
    overflow: hidden; /* Idhu mukkiyam, colors veliya pona scroll bar vara kudadhu */
}

/* Common Styles for the Glowing Circles */
#onboarding-overlay::before,
#onboarding-overlay::after {
    content: "";
    position: absolute;
    width: 60vw; /* Screen la 60% alavu */
    height: 60vw;
    border-radius: 50%; /* Vattam */
    filter: blur(80px); /* Nalla soft glow kidaikum */
    z-index: -1; /* Content pinnadi irukanum */
    opacity: 0.6; /* Konjam transparent ah irundha dhaan azhagu */
}

/* 🟣 TOP LEFT: Punchy Purple Animation */
#onboarding-overlay::before {
    top: -20%;
    left: -20%;
    /* Unga pazhaya purple ah vida konjam punchy ah */
    background: radial-gradient(circle at center, #d946ef, #7e22ce); 
    animation: moveTopLeft 18s infinite alternate ease-in-out;
}

/* 🔵 BOTTOM RIGHT: Punchy Teal Animation */
#onboarding-overlay::after {
    bottom: -20%;
    right: -20%;
    /* Unga pazhaya teal ah vida konjam punchy ah */
    background: radial-gradient(circle at center, #2dd4bf, #0f766e);
    animation: moveBottomRight 15s infinite alternate ease-in-out;
}

/* --- ANIMATION KEYFRAMES (Slow Motion) --- */

@keyframes moveTopLeft {
    0% {
        transform: translate(0, 0) scale(1);
    }
    100% {
        transform: translate(20%, 20%) scale(1.2); /* Mela irundhu konjam keela varum */
    }
}

@keyframes moveBottomRight {
    0% {
        transform: translate(0, 0) scale(1);
    }
    100% {
        transform: translate(-20%, -20%) scale(1.3); /* Keela irundhu konjam mela pogum */
    }
}

        
        .wizard-container {
            width: 90%; max-width: 450px; text-align: center;
            /* CENTER FIX: Absolute Positioning */
            position: absolute; 
            top: 50%; left: 50%; 
            transform: translate(-50%, -50%);
            z-index: 2001;
        }
        
        .step-content { display: none; animation: fadeIn 0.4s ease; }
        .step-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        .intro-title { font-size: 32px; font-weight: 800; color: #fff; margin-bottom: 10px; }
        .intro-desc { color: #a1a1aa; font-size: 16px; margin-bottom: 40px; line-height: 1.5; }
        
        .btn-primary {
            background: #fff; color: #000; border: none;
            padding: 16px 40px; border-radius: 12px;
            font-size: 16px; font-weight: 700; cursor: pointer;
            width: 100%; transition: transform 0.2s;
        }
        .btn-primary:active { transform: scale(0.98); }

        .input-field {
            width: 100%; padding: 18px; border-radius: 12px; 
            border: 1px solid #333; background: #111; color: #fff;
            text-align: center; outline: none; margin-bottom: 25px;
            font-size: 18px; font-family: 'Outfit', sans-serif;
        }
        .input-field:focus { border-color: #666; }

        .toggle-group { display: flex; gap: 10px; margin-bottom: 20px; }
        .toggle-btn {
            flex: 1; padding: 12px; border: 1px solid #333; border-radius: 10px;
            background: #111; color: #71717a; cursor: pointer; font-weight: 600;
        }
        .toggle-btn.selected { background: #fff; color: #000; border-color: #fff; }
        
        .dropdown-select {
            width: 100%; padding: 15px; margin-bottom: 15px;
            background: #111; border: 1px solid #333; border-radius: 12px;
            color: #fff; font-size: 16px; outline: none; appearance: none;
            background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
            background-repeat: no-repeat; background-position: right 1rem center; background-size: 1em;
        }

        .hidden-opt { display: none; }

        /* ERROR & SHAKE STYLES */
        .input-error {
            border: 2px solid #ef4444 !important;
            background: #2a0b0b !important;
            color: #ffcccc !important;
        }
        .shake { animation: shake 0.4s cubic-bezier(.36,.07,.19,.97) both; }
        @keyframes shake {
            10%, 90% { transform: translate3d(-1px, 0, 0); }
            20%, 80% { transform: translate3d(2px, 0, 0); }
            30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
            40%, 60% { transform: translate3d(4px, 0, 0); }
        }
    </style>
</head>
<body>

    <div id="onboarding-overlay">
        <div class="wizard-container">
            
            <div id="step-1" class="step-content active">
                <div style="margin-bottom: 20px;"><i class="fas fa-graduation-cap" style="font-size: 60px; color: #fff;"></i></div>
                <h1 class="intro-title">Welcome to<br>Student's AI</h1>
                <p class="intro-desc">Your personal AI tutor designed to simplify learning, solve doubts, and help you excel in your studies.</p>
                <button class="btn-primary" onclick="nextStep(2)">Get Started</button>
            </div>

            <div id="step-2" class="step-content">
                <h2 class="intro-title" style="font-size: 26px;">What's your name?</h2>
                <p class="intro-desc">So I can address you properly.</p>
                <input type="text" id="name-input" class="input-field" placeholder="Enter your Name" 
                       autocomplete="off" autocorrect="off" spellcheck="false" inputmode="text" 
                       onkeydown="if(event.key==='Enter') nextStep(3)">
                <button class="btn-primary" onclick="nextStep(3)">Next</button>
            </div>

            <div id="step-3" class="step-content">
                <h2 class="intro-title" style="font-size: 26px;">Student Details</h2>
                
                <div class="toggle-group">
                    <div class="toggle-btn selected" id="btn-school" onclick="toggleType('school')">School</div>
                    <div class="toggle-btn" id="btn-college" onclick="toggleType('college')">College</div>
                </div>

                <div id="school-opts">
                    <select id="school-std" class="dropdown-select">
                        <option value="" disabled selected>Select Standard</option>
                        <option value="6th">6th Standard</option>
                        <option value="7th">7th Standard</option>
                        <option value="8th">8th Standard</option>
                        <option value="9th">9th Standard</option>
                        <option value="10th">10th Standard</option>
                        <option value="11th">11th Standard</option>
                        <option value="12th">12th Standard</option>
                    </select>
                </div>

                <div id="college-opts" class="hidden-opt">
                    <select id="college-dept" class="dropdown-select">
                        <option value="" disabled selected>Select Department</option>
                        <option value="AI & DS">AI & DS</option>
                        <option value="CSE">CSE</option>
                        <option value="IT">IT</option>
                        <option value="ECE">ECE</option>
                        <option value="EEE">EEE</option>
                        <option value="MECH">MECH</option>
                    </select>
                    <select id="college-year" class="dropdown-select" onchange="updateSemesters()">
                        <option value="" disabled selected>Select Year</option>
                        <option value="1st Year">1st Year</option>
                        <option value="2nd Year">2nd Year</option>
                        <option value="3rd Year">3rd Year</option>
                        <option value="4th Year">4th Year</option>
                    </select>
                    <select id="college-sem" class="dropdown-select">
                        <option value="" disabled selected>Select Semester</option>
                    </select>
                </div>

                <input type="text" id="subject-input" class="input-field" placeholder="Enter Subject (e.g. Math, Python)" 
                       style="padding: 15px; margin-bottom: 15px;" 
                       autocomplete="off" autocorrect="off" spellcheck="false" inputmode="text" 
                       onkeydown="if(event.key==='Enter') finishSetup()">
                
                <button class="btn-primary" onclick="finishSetup()">Start Learning</button>
            </div>

        </div>
    </div>

    <div id="image-modal" style="display:none;" onclick="this.style.display='none'"></div>

    <div id="sidebar">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div class="user-info"><span id="display-name">User</span></div>
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-times"></i></div>
        </div>
        <button class="new-chat-btn" onclick="newChat()">New Chat</button>
        <div class="history-label">Chat History</div>
        <div id="history-list"></div>
        <div class="brand-section">
            <div class="brand-name" style="color:#555; font-size:12px; letter-spacing:2px;">DESIGNED BY SHIRPI</div>
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
            <div id="preview-area" style="display:none;"></div>
            <div class="input-container">
                <button class="icon-btn" onclick="document.getElementById('file-input').click()"><i class="fas fa-paperclip"></i></button>
                <input type="file" id="file-input" hidden onchange="handleFileSelect(this)">
                
                <textarea id="input" placeholder="Ask your doubt..." rows="1" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
                
                <button class="send-btn" onclick="send()"><i class="fas fa-arrow-up"></i></button>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let userDetails = { type: 'school' };
        let currentChatId = null;
        let currentAttachment = { type: null, data: null };

        // --- UPDATED WIZARD LOGIC ---
        function nextStep(targetStep) {
            let valid = true;
            let errorElement = null;

            if (targetStep === 3) { 
                const nameInput = document.getElementById('name-input');
                const name = nameInput.value.trim();
                if (!name) { valid = false; errorElement = nameInput; } 
                else { currentUser = name; }
            }

            if (!valid && errorElement) {
                errorElement.classList.add('input-error', 'shake');
                setTimeout(() => errorElement.classList.remove('shake'), 500);
                errorElement.addEventListener('input', function() { this.classList.remove('input-error'); }, {once: true});
                return; 
            }

            // Push History for Back Button
            if (targetStep > 1) { history.pushState({ step: targetStep }, null, ""); }

            document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
            document.getElementById('step-' + targetStep).classList.add('active');
        }

        // --- BROWSER BACK BUTTON SUPPORT ---
        window.onpopstate = function(event) {
            if (event.state && event.state.step) {
                document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
                document.getElementById('step-' + event.state.step).classList.add('active');
            } else {
                document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
                document.getElementById('step-1').classList.add('active');
            }
        };

        function toggleType(type) {
            userDetails.type = type;
            document.getElementById('btn-school').classList.toggle('selected', type === 'school');
            document.getElementById('btn-college').classList.toggle('selected', type === 'college');
            
            if(type === 'school') {
                document.getElementById('school-opts').style.display = 'block';
                document.getElementById('college-opts').style.display = 'none';
            } else {
                document.getElementById('school-opts').style.display = 'none';
                document.getElementById('college-opts').style.display = 'block';
            }
        }

        // --- NEW: DYNAMIC SEMESTERS ---
        function updateSemesters() {
            const year = document.getElementById('college-year').value;
            const semSelect = document.getElementById('college-sem');
            semSelect.innerHTML = '<option value="" disabled selected>Select Semester</option>';
            
            let options = [];
            if(year === '1st Year') options = ['Sem 1', 'Sem 2'];
            else if(year === '2nd Year') options = ['Sem 3', 'Sem 4'];
            else if(year === '3rd Year') options = ['Sem 5', 'Sem 6'];
            else if(year === '4th Year') options = ['Sem 7', 'Sem 8'];

            options.forEach(sem => {
                const opt = document.createElement('option');
                opt.value = sem;
                opt.innerText = sem.replace('Sem', 'Semester');
                semSelect.appendChild(opt);
            });
        }

        function finishSetup() {
            document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
            let valid = true;
            userDetails.name = currentUser;
            
            // Validate Subject (Fixed)
            const subInput = document.getElementById('subject-input');
            userDetails.subject = subInput.value.trim();
            if(!userDetails.subject) { subInput.classList.add('input-error', 'shake'); valid = false; }

            if(userDetails.type === 'school') {
                const stdInput = document.getElementById('school-std');
                userDetails.standard = stdInput.value;
                if(!userDetails.standard) { stdInput.classList.add('input-error', 'shake'); valid = false; }
            } else {
                const deptInput = document.getElementById('college-dept');
                const yearInput = document.getElementById('college-year');
                const semInput = document.getElementById('college-sem');

                userDetails.dept = deptInput.value;
                userDetails.year = yearInput.value;
                userDetails.sem = semInput.value;

                if(!userDetails.dept) { deptInput.classList.add('input-error', 'shake'); valid = false; }
                if(!userDetails.year) { yearInput.classList.add('input-error', 'shake'); valid = false; }
                if(!userDetails.sem) { semInput.classList.add('input-error', 'shake'); valid = false; }
            }

            if (!valid) {
                setTimeout(() => document.querySelectorAll('.shake').forEach(el => el.classList.remove('shake')), 500);
                document.querySelectorAll('.input-error').forEach(el => {
                    el.addEventListener('input', function() { this.classList.remove('input-error'); }, {once:true});
                    el.addEventListener('change', function() { this.classList.remove('input-error'); }, {once:true});
                });
                return;
            }

            localStorage.setItem("student_ai_user", currentUser);
            localStorage.setItem("student_details", JSON.stringify(userDetails));

            const overlay = document.getElementById("onboarding-overlay");
            overlay.classList.add('hidden');
            setTimeout(() => overlay.style.display = 'none', 600);
            showApp();
        }

        // --- AUTH & CHAT LOGIC ---
        function checkLogin() {
            const stored = localStorage.getItem("student_ai_user");
            if (stored) { 
                currentUser = stored;
                try { userDetails = JSON.parse(localStorage.getItem("student_details")) || {}; } catch(e){}
                document.getElementById("onboarding-overlay").classList.add('hidden');
                document.getElementById("onboarding-overlay").style.display = 'none';
                showApp();
            }
        }

        function showApp() {
            document.getElementById("display-name").innerText = "Hi " + currentUser;
            const introDiv = document.getElementById("chat-box");
            if(introDiv.innerHTML === "") {
                const sub = userDetails.type === 'school' ? userDetails.standard : `${userDetails.dept} - ${userDetails.year}`;
                introDiv.innerHTML = `<div id="intro-container"><div class="msg ai-msg"><div class="ai-content"><h1>Hi ${currentUser},</h1><p>Ready to master <b>${userDetails.subject || 'your subjects'}</b> today?<br><small>${sub}</small></p></div></div></div>`;
            }
            loadHistory();
        }

        function handleLogout() {
            localStorage.removeItem("student_ai_user");
            localStorage.removeItem("student_details");
            location.reload();
        }

        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }
        
        async function send() {
            const input = document.getElementById('input');
            const text = input.value.trim();
            if(!text && !currentAttachment.data) return;
            const intro = document.getElementById('intro-container');
            if(intro) intro.remove();
            const box = document.getElementById('chat-box');
            box.insertAdjacentHTML('beforeend', `<div class="msg user-msg"><div class="user-content">${text}</div></div>`);
            input.value = "";
            const msgId = "ai-" + Date.now();
            box.insertAdjacentHTML('beforeend', `<div id="${msgId}" class="msg ai-msg">Thinking...</div>`);
            
            if(!currentChatId) {
                const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                const d = await r.json(); currentChatId = d.chat_id;
            }
            const res = await fetch('/chat', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: text, username: currentUser, chat_id: currentChatId })
            });
            const data = await res.json();
            document.getElementById(msgId).innerHTML = `<div class="ai-content">${marked.parse(data.response)}</div>`;
        }
        
        async function loadHistory() {
             const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
             const data = await res.json();
             const list = document.getElementById('history-list'); list.innerHTML = "";
             if(data.chats) {
                 Object.keys(data.chats).reverse().forEach(cid => {
                     list.innerHTML += `<div class="history-item" onclick="loadChat('${cid}')">${data.chats[cid].title}</div>`;
                 });
             }
        }
        
        async function loadChat(cid) {
            currentChatId = cid;
            const res = await fetch('/get_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
            const d = await res.json();
            const box = document.getElementById('chat-box'); box.innerHTML = "";
            d.messages.forEach(m => {
                const cls = m.role === 'user' ? 'user-msg' : 'ai-msg';
                const cnt = m.role === 'user' ? `<div class="user-content">${m.content}</div>` : `<div class="ai-content">${marked.parse(m.content)}</div>`;
                box.insertAdjacentHTML('beforeend', `<div class="msg ${cls}">${cnt}</div>`);
            });
            document.getElementById('sidebar').classList.remove('open');
        }

        checkLogin();
    </script>
</body>
</html>
"""
# --- BACKEND ROUTES (UNCHANGED) ---
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

 