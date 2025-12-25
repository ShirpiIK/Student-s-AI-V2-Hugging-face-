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

# --- UI TEMPLATE (UPDATED: PROFESSIONAL UI V2) ---

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
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
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
        /* --- VARIABLES & THEMES --- */
        :root {
            --bg: #09090b; 
            --card: #18181b; 
            --user-msg: #27272a; 
            --text: #e4e4e7;
            --text-muted: #a1a1aa;
            --accent: #fff; 
            --border: #27272a; 
            --hover: #27272a;
        }
        
        /* LIGHT MODE OVERRIDES */
        body.light-mode {
            --bg: #ffffff; 
            --card: #f4f4f5; 
            --user-msg: #e4e4e7; 
            --text: #09090b;
            --text-muted: #52525b;
            --accent: #000; 
            --border: #e4e4e7; 
            --hover: #f4f4f5;
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        
        body, html { 
            margin: 0; padding: 0; height: 100dvh; width: 100%; max-width: 100%;
            background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; 
            overflow: hidden; font-size: 16px;
            transition: background 0.3s ease, color 0.3s ease;
        }

        /* --- APP STRUCTURE --- */
        #app-container { 
            display: flex; flex-direction: column; height: 100dvh; width: 100%; 
            position: relative; overflow-x: hidden; padding-top: 60px;
        }

        /* --- HEADER --- */
        header {
            height: 60px; padding: 0 15px; 
            background: var(--bg);
            border-bottom: 1px solid var(--border);
            display: flex; align-items: center; justify-content: space-between; 
            z-index: 50; padding-top: env(safe-area-inset-top);
            position: absolute; top: 0; left: 0; right: 0;
            transition: background 0.3s ease;
        }
        .menu-btn { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text); transition: background 0.2s; }
        .menu-btn:active { background: var(--hover); }
        .app-title { font-size: 20px; font-weight: 700; color: var(--text); letter-spacing: -0.5px; }

        body, html, * { 
             font-family: 'Outfit', sans-serif !important; /* ஆப் முழுவதும் ஒரே சீரான ஃபான்ட் */
        }
        /* --- SIDEBAR --- */
        #sidebar {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: rgba(0,0,0,0); /* ஆரம்பத்தில் வெளிப்படையாக இருக்கும் */
            z-index: 100; transform: translateX(-100%); 
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
        }

         #sidebar.open { transform: translateX(0); background: rgba(0,0,0,0.5); }

        /* உண்மையான மெனு பகுதி */
        .sidebar-content {
            width: 280px; height: 100%; background: var(--bg);
            display: flex; flex-direction: column; padding: 20px;
            border-right: 1px solid var(--border);
        }

        /* வலது பக்கம் இருக்கும் காலி இடம் (Gap) */
        .sidebar-overlay-gap { flex: 1; cursor: pointer; }
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .user-info-text { font-size: 18px; font-weight: 700; color: var(--text); }
        
        .new-chat-btn { 
            width: 100%; padding: 12px; background: var(--text); color: var(--bg); 
            border: none; border-radius: 10px; font-weight: 600; cursor: pointer; 
            margin-bottom: 20px; display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        
        .history-label { color: var(--text-muted); font-size: 12px; font-weight: 600; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }
        #history-list { flex: 1; overflow-y: auto; padding-right: 5px; }
        
        .history-item { 
            padding: 12px; margin-bottom: 8px; background: transparent; 
            border-radius: 8px; cursor: pointer; color: var(--text); 
            display: flex; justify-content: space-between; align-items: center;
            font-size: 14px; transition: background 0.2s;
        }
        .history-item:hover { background: var(--card); }
        .history-actions { display: flex; gap: 10px; opacity: 0; transition: opacity 0.2s; }
        .history-item:hover .history-actions { opacity: 1; }
        .hist-icon { color: var(--text-muted); font-size: 12px; padding: 4px; }
        .hist-icon:hover { color: var(--text); }

        .sidebar-footer { margin-top: auto; border-top: 1px solid var(--border); padding-top: 15px; }
        .footer-link { display: flex; align-items: center; gap: 10px; padding: 12px; color: var(--text); cursor: pointer; border-radius: 8px; font-weight: 500; }
        .footer-link:hover { background: var(--card); }

        /* --- CHAT AREA --- */
        #chat-box { 
        flex: 1; overflow-y: auto; 
        padding: 20px 15px; 
        padding-bottom: 40px; /* Reduced from 100px to 40px */
        display: flex; flex-direction: column; gap: 20px; 
        scroll-behavior: smooth;
    }
        
        .msg { width: 100%; display: flex; flex-direction: column; opacity: 0; animation: fadeIn 0.4s forwards; }
        @keyframes fadeIn { to { opacity: 1; } }
        
        .user-msg { align-items: flex-end; }
        /* --- FIXED: USER BUBBLE PROFESSIONAL STYLE --- */
    

        /* AI Message Formatting */
      .ai-content {
        width: 100%;
        max-width: 100%;
        font-size: 17px;
        line-height: 1.8;
    }
       .ai-content strong { color: var(--text); font-weight: 700; }
        /* Chat Actions (Icons below message) */
        .msg-actions { 
        display: flex; gap: 15px; margin-top: 8px; 
        opacity: 1; /* 👇 FIX: Always visible (removed hover) */
        font-size: 13px; padding: 0 5px; color: var(--text-muted);
        transition: color 0.2s;
    }
        .msg:hover .msg-actions { opacity: 1; }
        .action-icon { 
        cursor: pointer; display: flex; align-items: center; gap: 5px; 
    }
    .action-icon:hover { color: var(--text); }
        /* Code Blocks */
        pre { background: #1e1e1e !important; border-radius: 12px; padding: 15px; overflow-x: auto; margin: 15px 0; border: 1px solid #333; }
        code { font-family: 'JetBrains Mono', monospace; font-size: 14px; }
        
        /* Input Area */
        .input-wrapper { 
            background: var(--bg); padding: 10px 15px; border-top: 1px solid var(--border); 
            flex-shrink: 0; z-index: 60; padding-bottom: max(15px, env(safe-area-inset-bottom)); 
        }
        textarea { 
            flex: 1; background: transparent; border: none; color: var(--text); 
            font-size: 16px; max-height: 120px; padding: 12px 0; resize: none; outline: none; 
            font-family: 'Outfit', sans-serif; 
        }
        /* --- SETTINGS PAGE (OVERLAY) --- */
        #settings-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: var(--bg); z-index: 2000; display: flex; flex-direction: column;
            transform: translateX(100%); transition: transform 0.3s ease;
            overflow-y: auto;
        }
        #settings-overlay.active { transform: translateX(0); }

        .settings-header {
            padding: 20px; padding-top: calc(20px + env(safe-area-inset-top));
            display: flex; align-items: center; gap: 15px;
        }
        .back-btn { font-size: 20px; color: var(--text); cursor: pointer; padding: 5px; }
        
        .settings-search {
            width: 90%; max-width: 600px; margin: 0 auto 20px auto;
            background: var(--card); border: 1px solid var(--border);
            padding: 12px 20px; border-radius: 12px; color: var(--text);
            display: flex; align-items: center; gap: 10px;
        }
        .settings-search input { background: transparent; border: none; color: var(--text); width: 100%; outline: none; font-size: 16px; }

        .settings-content {
            width: 100%; max-width: 600px; margin: 0 auto; padding: 0 20px 40px 20px;
        }

        .section-title { color: var(--text-muted); font-size: 13px; font-weight: 600; margin: 20px 0 10px 0; text-transform: uppercase; }
        
        /* Profile Section */
        .profile-card {
            background: var(--card); border-radius: 16px; padding: 20px;
            display: flex; flex-direction: column; align-items: center; margin-bottom: 30px;
            border: 1px solid var(--border);
        }
        .profile-pic-wrapper {
            position: relative; width: 100px; height: 100px; margin-bottom: 20px;
        }
        .profile-pic {
            width: 100%; height: 100%; border-radius: 50%; object-fit: cover;
            border: 2px solid var(--border); background: #111;
        }
        .edit-pic-btn {
            position: absolute; bottom: 0; right: 0; background: var(--text); color: var(--bg);
            width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
            cursor: pointer; font-size: 14px;
        }
        
        .profile-details { width: 100%; }
        .detail-row {
            display: flex; justify-content: space-between; align-items: center;
            padding: 15px 0; border-bottom: 1px solid var(--border);
            font-size: 15px;
        }
        .detail-row:last-child { border-bottom: none; }
        .detail-label { color: var(--text-muted); }
        .detail-value { color: var(--text); font-weight: 600; text-align: right; max-width: 60%; }
        
        /* Editable Subject */
        .editable-subject { border-bottom: 1px dashed var(--text-muted); cursor: pointer; }
        .subject-edit-input { 
            background: var(--bg); color: var(--text); border: 1px solid var(--text); 
            padding: 5px; border-radius: 5px; width: 100%; text-align: right; 
        }

        /* Themes */
        .theme-list { background: var(--card); border-radius: 16px; border: 1px solid var(--border); overflow: hidden; }
        .theme-option {
            padding: 15px 20px; display: flex; align-items: center; gap: 15px;
            cursor: pointer; border-bottom: 1px solid var(--border); color: var(--text);
        }
        .theme-option:last-child { border-bottom: none; }
        .theme-icon { width: 24px; text-align: center; }

        .logout-row { 
            margin-top: 10px; color: #ef4444; font-weight: 600; cursor: pointer; 
            padding: 15px 0; text-align: center;
        }

        /* --- ONBOARDING OVERLAY (UNCHANGED LOGIC - FIXED CSS) --- */
        #onboarding-overlay { 
            position: fixed; top: 0; left: 0; width: 100vw; 
            height: 100vh; height: 100lvh;
            z-index: 3000; 
            display: flex; align-items: center; justify-content: center;
            transition: opacity 0.6s ease; opacity: 1; pointer-events: auto;
            background-color: #050505; overflow: hidden; 
        }
        #onboarding-overlay.hidden { opacity: 0; pointer-events: none; }

        #onboarding-overlay::before, #onboarding-overlay::after {
            content: ""; position: absolute; width: 60vw; height: 60vw;
            border-radius: 50%; filter: blur(80px); z-index: -1; opacity: 0.6;
        }
        #onboarding-overlay::before {
            top: -20%; left: -20%;
            background: radial-gradient(circle at center, #d946ef, #7e22ce); 
            animation: moveTopLeft 18s infinite alternate ease-in-out;
        }
        #onboarding-overlay::after {
            bottom: -20%; right: -20%;
            background: radial-gradient(circle at center, #2dd4bf, #0f766e);
            animation: moveBottomRight 15s infinite alternate ease-in-out;
        }
        @keyframes moveTopLeft { 0% { transform: translate(0, 0) scale(1); } 100% { transform: translate(20%, 20%) scale(1.2); } }
        @keyframes moveBottomRight { 0% { transform: translate(0, 0) scale(1); } 100% { transform: translate(-20%, -20%) scale(1.3); } }

        /* Wizard Styles */
        .wizard-container { width: 90%; max-width: 450px; text-align: center; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 3001; }
        .step-content { display: none; animation: fadeIn 0.4s ease; }
        .step-content.active { display: block; }
        .intro-title { font-size: 32px; font-weight: 800; color: #fff; margin-bottom: 10px; }
        .intro-desc { color: #a1a1aa; font-size: 16px; margin-bottom: 40px; line-height: 1.5; }
        .btn-primary { background: #fff; color: #000; border: none; padding: 16px 40px; border-radius: 12px; font-size: 16px; font-weight: 700; cursor: pointer; width: 100%; transition: transform 0.2s; }
        .btn-primary:active { transform: scale(0.98); }
        .input-field { width: 100%; padding: 18px; border-radius: 12px; border: 1px solid #333; background: #111; color: #fff; text-align: center; outline: none; margin-bottom: 25px; font-size: 18px; font-family: 'Outfit', sans-serif; }
        .toggle-group { display: flex; gap: 10px; margin-bottom: 20px; }
        .toggle-btn { flex: 1; padding: 12px; border: 1px solid #333; border-radius: 10px; background: #111; color: #71717a; cursor: pointer; font-weight: 600; }
        .toggle-btn.selected { background: #fff; color: #000; border-color: #fff; }
        .dropdown-select { width: 100%; padding: 15px; margin-bottom: 15px; background: #111; border: 1px solid #333; border-radius: 12px; color: #fff; font-size: 16px; outline: none; appearance: none; }
        .hidden-opt { display: none; }
        .input-error { border: 2px solid #ef4444 !important; background: #2a0b0b !important; }
        .shake { animation: shake 0.4s cubic-bezier(.36,.07,.19,.97) both; }
        @keyframes shake { 10%, 90% { transform: translate3d(-1px, 0, 0); } 30%, 70% { transform: translate3d(-4px, 0, 0); } 50% { transform: translate3d(4px, 0, 0); } }

        /* --- FIX: FONT SIZE & FULL WIDTH --- */
    
    /* 1. மெசேஜ் பாக்ஸ் செட்டிங்ஸ் */
    .msg-bubble { 
        padding: 12px 16px; 
        
        /* 👇 எழுத்து அளவு பெரிதாக்கப்பட்டது */
        font-size: 18px !important; 
        line-height: 1.8 !important; 
        
        /* 👇 வலது பக்கம் இடம் வீணாவதை தடுக்க (Full Width) */
        max-width: 100% !important; 
        width: fit-content;
    }

    /* 2. AI Text செட்டிங்ஸ் */
    .ai-content { 
        font-size: 18px !important; 
        line-height: 1.8 !important;
    }
    /* --- PROFESSIONAL CHAT STYLES --- */

    /* 1. Automatic Curve User Bubble */
    /* --- USER MESSAGE BOX: CURVED SQUARE DESIGN --- */
    .user-content {
        /* Square Shape with Curved Edges */
        border-radius: 12px; /* சதுர வடிவம் மற்றும் வளைந்த விளிம்புகள் */
        background: var(--user-msg); 
        color: var(--text);
        padding: 12px 16px; 
        
        /* Font Settings */
        font-size: 17px; 
        line-height: 1.6;
        
        /* 👇 Positioning & Auto-Sizing */
        position: relative;
        width: fit-content;      /* டெக்ஸ்ட் அளவிற்கு ஏற்ப மாறும் */
        max-width: 85%;          /* 85% மேல் போகாது */
        min-width: 50px;         /* மிகச் சிறிய வார்த்தைக்கும் வடிவம் மாறாது */
        word-wrap: break-word;   /* நீண்ட வார்த்தைகளை உடைக்கும் */
        margin-left: auto;       /* வலது பக்கம் ஒட்டி நிற்கும் */
        box-shadow: 0 4px 10px rgba(0,0,0,0.2); /* அழகான நிழல் */
        border: 1px solid rgba(255,255,255,0.05); /* மெல்லிய பார்டர் */
    }

    /* 2. Stylish Input Bar (Glassmorphism) */
    .input-container { 
        background: rgba(20, 20, 20, 0.95);
        backdrop-filter: blur(10px);
        border: 1px solid #333; 
        border-radius: 40px; 
        padding: 8px 10px; 
        display: flex; align-items: flex-end; gap: 12px;
        transition: all 0.3s ease;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    .input-container:focus-within { border-color: #666; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }

    /* 3. Stylish + Button (Rotating) */
    .plus-btn {
        width: 44px; height: 44px; border-radius: 50%;
        background: #27272a; color: #aaa; 
        display: flex; align-items: center; justify-content: center;
        cursor: pointer; flex-shrink: 0; font-size: 20px;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid #333;
    }
    .plus-btn:hover { background: #fff; color: #000; transform: rotate(90deg); }

    /* 4. Stylish Send Button (Bouncing) */
    .send-btn { 
        width: 44px; height: 44px; border-radius: 50%;
        background: #fff; color: #000; 
        display: flex; align-items: center; justify-content: center; 
        cursor: pointer; flex-shrink: 0; font-size: 18px;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        margin-bottom: 0px;
    }
    .send-btn:hover { transform: scale(1.1); box-shadow: 0 0 15px rgba(255,255,255,0.4); }
    .send-btn:active { transform: scale(0.9); }
    /* ... ஏற்கனவே இருக்கும் டிசைன் கோடுகள் ... */

    /* 👇 புதிய கோடை இங்கே மட்டும் பேஸ்ட் பண்ணுங்க */
    * {
        -webkit-user-select: none;
        -ms-user-select: none;
        user-select: none;
        -webkit-touch-callout: none;
    }
    input, textarea, .msg-bubble, .ai-content, .user-content {
        -webkit-user-select: text;
        user-select: text;
    }

    #custom-modal {
        position: fixed; inset: 0; background: rgba(0,0,0,0.85);
        display: none; align-items: center; justify-content: center; z-index: 9999;
    }
    .modal-content {
        background: var(--card); border: 1px solid var(--border);
        padding: 25px; border-radius: 20px; width: 90%; max-width: 350px; text-align: center;
    }
    .modal-input {
        width: 100%; padding: 12px; border-radius: 10px; border: 1px solid var(--border);
        background: var(--bg); color: var(--text); margin: 15px 0; outline: none;
    }
    .modal-btns { display: flex; gap: 10px; margin-top: 10px; }
    .m-btn { flex: 1; padding: 12px; border-radius: 10px; border: none; font-weight: 600; cursor: pointer; }
</style>
</head>
<body>

    <div id="settings-overlay">
        <div class="settings-header">
            <div class="back-btn" onclick="closeSettings()"><i class="fas fa-arrow-left"></i></div>
            <h2 style="margin:0; font-size:20px; color:var(--text);">Settings</h2>
        </div>

        <div class="settings-search">
            <i class="fas fa-search" style="color:var(--text-muted);"></i>
            <input type="text" placeholder="Search settings...">
        </div>

        <div class="settings-content">
            <div class="section-title">Student Profile</div>
            <div class="profile-card">
                <div class="profile-pic-wrapper">
                    <img id="settings-pic" src="https://ui-avatars.com/api/?name=User&background=random" class="profile-pic">
                    <label for="pic-upload" class="edit-pic-btn"><i class="fas fa-camera"></i></label>
                    <input type="file" id="pic-upload" hidden accept="image/*" onchange="uploadProfilePic(this)">
                </div>
                <div class="profile-details">
                    <div class="detail-row">
                        <span class="detail-label">Name</span>
                        <span class="detail-value" id="profile-name">User</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Education</span>
                        <span class="detail-value" id="profile-edu">College</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Standard/Dept</span>
                        <span class="detail-value" id="profile-std">AI & DS</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Subject</span>
                        <span class="detail-value editable-subject" id="profile-sub" onclick="editSubject(this)">Maths</span>
                    </div>
                    <div class="logout-row" onclick="handleLogout()">Log Out</div>
                </div>
            </div>

            <div style="border-bottom: 1px solid var(--border); margin-bottom: 20px;"></div>

            <div class="section-title">Themes</div>
            <div class="theme-list">
                <div class="theme-option" onclick="setTheme('light')">
                    <div class="theme-icon"><i class="fas fa-sun"></i></div>
                    <span>Light Mode</span>
                </div>
                <div class="theme-option" onclick="setTheme('dark')">
                    <div class="theme-icon"><i class="fas fa-moon"></i></div>
                    <span>Dark Mode</span>
                </div>
                <div class="theme-option" onclick="setTheme('system')">
                    <div class="theme-icon"><i class="fas fa-desktop"></i></div>
                    <span>System Default</span>
                </div>
            </div>
        </div>
    </div>

    <div id="onboarding-overlay">
        <div class="wizard-container">
            <div id="step-1" class="step-content active">
                <div style="margin-bottom: 20px;"><i class="fas fa-graduation-cap" style="font-size: 60px; color: #fff;"></i></div>
                <h1 class="intro-title">Welcome to<br>Student's AI</h1>
                <p class="intro-desc">Your personal AI tutor designed to simplify learning, solve doubts, and help you excel.</p>
                <button class="btn-primary" onclick="nextStep(2)">Get Started</button>
            </div>
            <div id="step-2" class="step-content">
                <h2 class="intro-title" style="font-size: 26px;">What's your name?</h2>
                <input type="text" id="name-input" class="input-field" placeholder="Enter your Name" autocomplete="off" onkeydown="if(event.key==='Enter') nextStep(3)">
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
                        <option value="6th">6th</option><option value="7th">7th</option><option value="8th">8th</option>
                        <option value="9th">9th</option><option value="10th">10th</option><option value="11th">11th</option><option value="12th">12th</option>
                    </select>
                    <input type="text" id="school-subject" class="input-field" placeholder="Enter Subject (e.g. Maths)" autocomplete="off" onkeydown="if(event.key==='Enter') finishSetup()">
                </div>
                <div id="college-opts" class="hidden-opt">
                    <select id="college-dept" class="dropdown-select">
                        <option value="" disabled selected>Select Department</option>
                        <option value="CSE">CSE</option><option value="AI & DS">AI & DS</option><option value="IT">IT</option>
                    </select>
                    <select id="college-year" class="dropdown-select" onchange="updateSemesters()">
                        <option value="" disabled selected>Select Year</option>
                        <option value="1st Year">1st Year</option><option value="2nd Year">2nd Year</option>
                    </select>
                    <select id="college-sem" class="dropdown-select"><option value="" disabled selected>Select Semester</option></select>
                    <input type="text" id="college-subject" class="input-field" placeholder="Enter Subject" autocomplete="off" onkeydown="if(event.key==='Enter') finishSetup()">
                </div>
                <button class="btn-primary" onclick="finishSetup()">Start Learning</button>
            </div>
        </div>
    </div>

    <div id="sidebar">
        <div class="sidebar-content">
            <div style="position:relative; margin-bottom:15px;">
                <input type="text" id="hist-search" placeholder="Search history..." 
                       style="width:100%; padding:10px 35px 10px 12px; border-radius:10px; border:1px solid var(--border); background:var(--card); color:var(--text); outline:none;"
                       oninput="filterHistory(this.value)">
                <i class="fas fa-times" id="clear-search" 
                   style="position:absolute; right:12px; top:50%; transform:translateY(-50%); cursor:pointer; display:none; color:var(--text-muted);"
                   onclick="clearSearch()"></i>
            </div>
            
            <div class="sidebar-header">
                <span class="user-info-text" id="display-name">User</span>
                <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-times"></i></div>
            </div>

            <button class="new-chat-btn" onclick="newChat()"><i class="fas fa-plus"></i> New Chat</button>
            <div class="history-label">Chat History</div>
            <div id="history-list"></div>
            
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
                <div onclick="clearFile()" style="position:absolute; top:-8px; right:-8px; background:red; color:fff; border-radius:50%; width:20px; height:20px; display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:12px;">×</div>
            </div>
        </div>

        <div id="attach-menu" style="display:none; position:absolute; bottom:75px; left:15px; background:#1a1a1a; border:1px solid #333; border-radius:16px; padding:8px; flex-direction:column; width:160px; z-index:100; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
            
            <label style="padding:12px; display:flex; align-items:center; gap:12px; color:#fff; cursor:pointer; font-size:14px;">
                <i class="fas fa-camera" style="color:#00d2ff;"></i> Camera 
                <input type="file" hidden accept="image/*" capture="environment" onchange="handleFile(this)">
            </label>
            
            <label style="padding:12px; display:flex; align-items:center; gap:12px; color:#fff; cursor:pointer; font-size:14px;">
                <i class="fas fa-image" style="color:#bf5af2;"></i> Gallery 
                <input type="file" hidden accept="image/*" onchange="handleFile(this)">
            </label>
            
            <label style="padding:12px; display:flex; align-items:center; gap:12px; color:#fff; cursor:pointer; font-size:14px;">
                <i class="fas fa-file-pdf" style="color:#ff3b30;"></i> File 
                <input type="file" hidden accept="application/pdf" onchange="handleFile(this)">
            </label>
        </div>
            <div class="input-container">
            <div class="plus-btn" onclick="toggleAttachMenu()">
                <i class="fas fa-plus"></i> 
            </div>
            
            <textarea id="msg-input" placeholder="Message..." rows="1" 
                oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
            
            <div class="send-btn" onclick="send()">
                <i class="fas fa-arrow-up"></i>
            </div>
        </div>
    </div>
    <script>
        // 1. GLOBAL VARIABLES
        let currentUser = null;
        let userDetails = { type: 'school' };
        let currentChatId = null;
        let isGenerating = false;

        // 2. ONBOARDING & LOGIN LOGIC
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

        window.onpopstate = function(e) {
            document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
            const s = e.state && e.state.step ? e.state.step : 1;
            document.getElementById('step-' + s).classList.add('active');
        };

        function toggleType(type) {
            userDetails.type = type;
            document.getElementById('btn-school').classList.toggle('selected', type === 'school');
            document.getElementById('btn-college').classList.toggle('selected', type === 'college');
            document.getElementById('school-opts').style.display = type === 'school' ? 'block' : 'none';
            document.getElementById('college-opts').style.display = type === 'college' ? 'block' : 'none';
        }

        function updateSemesters() {
             const year = document.getElementById('college-year').value;
             const semSelect = document.getElementById('college-sem');
             semSelect.innerHTML = '<option value="" disabled selected>Select Semester</option>';
             let options = year === '1st Year' ? ['Sem 1', 'Sem 2'] : ['Sem 3', 'Sem 4'];
             options.forEach(s => {
                 let opt = document.createElement('option'); opt.value = s; opt.innerText = s; semSelect.appendChild(opt);
             });
        }

        function finishSetup() {
            userDetails.name = currentUser;
            let valid = true;
            if(userDetails.type === 'school') {
                userDetails.standard = document.getElementById('school-std').value;
                userDetails.subject = document.getElementById('school-subject').value.trim();
                if(!userDetails.standard || !userDetails.subject) valid = false;
            } else {
                userDetails.dept = document.getElementById('college-dept').value;
                userDetails.year = document.getElementById('college-year').value;
                userDetails.sem = document.getElementById('college-sem').value;
                userDetails.subject = document.getElementById('college-subject').value.trim();
                if(!userDetails.dept || !userDetails.subject) valid = false;
            }
            if(!valid) { alert("Please fill all details"); return; }

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

        // 3. APP CORE & SETTINGS LOGIC
        function checkLogin() {
            const stored = localStorage.getItem("student_ai_user");
            if (stored) { 
                currentUser = stored;
                userDetails = JSON.parse(localStorage.getItem("student_details") || "{}");
                document.getElementById("onboarding-overlay").style.display = 'none';
                showApp();
            }
            const theme = localStorage.getItem('app_theme') || 'system';
            setTheme(theme);
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

        function openSettings() {
            document.getElementById('settings-overlay').classList.add('active');
            if(document.getElementById('sidebar').classList.contains('open')) toggleSidebar();
            updateProfileUI();
        }

        function closeSettings() { document.getElementById('settings-overlay').classList.remove('active'); }

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

        function uploadProfilePic(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    localStorage.setItem('profile_pic', e.target.result);
                    updateProfileUI();
                }
                reader.readAsDataURL(input.files[0]);
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

        // 4. ATTACHMENT & UTILITY LOGIC
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

        /* --- 1. SMOOTH TYPEWRITER LOGIC --- */
        /* --- PROFESSIONAL MARKDOWN-AWARE TYPEWRITER --- */
        
        /* --- CHATGPT STYLE ANIMATION (NO SHAKE & PERFECT SCROLL) --- */
        function typeWriter(element, text, callback) {
            const chatBox = document.getElementById('chat-box');
            let i = 0;
            
            // 1. பதிலை முதலிலேயே Markdown ஆக மாற்றி ஒரு மறைமுக இடத்தில் (Hidden Div) வைக்கிறோம்
            // இது பெட்டி அதிருவதை (Shake) தடுக்கும்.
            element.innerHTML = marked.parse(text);
            const finalHTML = element.innerHTML;
            element.innerHTML = ""; // அனிமேஷனுக்காக மீண்டும் காலியாக்குகிறோம்

            // 2. டயக்ராம் இருந்தால் அது தெரியாமல் இருக்க பெட்டியின் உயரத்தை லாக் செய்கிறோம்
            element.style.minHeight = "20px";

            function type() {
                if (i < finalHTML.length) {
                    // HTML Tags-ஐ கண்டறிந்தால் அதை முழுமையாக ஒரே நேரத்தில் சேர்க்க வேண்டும்
                    if (finalHTML.charAt(i) === '<') {
                        let tagEnd = finalHTML.indexOf('>', i);
                        i = tagEnd + 1;
                    } else {
                        i += 3; // வேகத்திற்காக 3 எழுத்துகளாக பிரிக்கிறோம்
                    }
                    
                    element.innerHTML = finalHTML.substring(0, i);
                    
                    // 👇 இதுதான் வார்த்தை மேலே வருவதை (Auto-scroll) உறுதி செய்யும்
                    chatBox.scrollTop = chatBox.scrollHeight;
                    
                    requestAnimationFrame(type); // சீரான அனிமேஷனுக்கு setTimeout-க்கு பதில் இது சிறந்தது
                } else {
                    element.innerHTML = finalHTML; // இறுதியில் முழுமையாக உறுதி செய்
                    
                    // Mermaid டயக்ராம் இருந்தால் மட்டும் லோடு செய்
                    if (window.mermaid && text.includes("```mermaid")) {
                        mermaid.run({ nodes: [element] });
                    }
                    
                    chatBox.scrollTop = chatBox.scrollHeight;
                    if (callback) callback();
                }
            }
            type();
        }

        
        function copyText(btn, text) {
            navigator.clipboard.writeText(text).then(() => {
                const originalIcon = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check" style="color:#4ade80;"></i> Copied';
                setTimeout(() => { btn.innerHTML = originalIcon; }, 2000);
            });
        }

        function shareContent(text) {
            if (navigator.share) {
                navigator.share({ title: 'Student AI', text: text }).catch(console.error);
            } else {
                alert("Sharing not supported. Text copied.");
            }
        }

        // 5. CHAT HANDLING LOGIC
        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }

        function editMessage(text) {
            const inputEl = document.getElementById('msg-input');
            inputEl.value = text;
            inputEl.focus();
            inputEl.style.height = 'auto';
            inputEl.style.height = inputEl.scrollHeight + 'px';
        }

        async function regenerateLast() {
            const userMsgs = document.querySelectorAll('.user-content');
            if (userMsgs.length === 0) return;
            const lastMsgText = userMsgs[userMsgs.length - 1].innerText;
            const aiMsgs = document.querySelectorAll('.ai-msg');
            if (aiMsgs.length > 0) aiMsgs[aiMsgs.length - 1].remove();
            document.getElementById('msg-input').value = lastMsgText;
            send(); 
        }

        function addMsg(role, text, img) {
            const box = document.getElementById('chat-box');
            let contentHtml = "";
            if (img) contentHtml += `<img src="${img}" class="chat-img">`;
            if (role === 'ai') {
                contentHtml += `<div class="ai-content">${marked.parse(text)}</div>`;
            } else {
                contentHtml += `<div class="user-content">${text}</div>`;
            }
            const safeText = text.replace(/`/g, '\\`').replace(/"/g, '&quot;');
            let actionsHtml = "";
            if (role === 'user') {
                actionsHtml = `
                <div class="msg-actions" style="justify-content: flex-end;">
                    <div class="action-icon" onclick="copyText(this, \`${safeText}\`)"><i class="fas fa-copy"></i> Copy</div>
                    <div class="action-icon" onclick="editMessage(\`${safeText}\`)"><i class="fas fa-pen"></i> Edit</div>
                </div>`;
            } else {
                actionsHtml = `
                <div class="msg-actions">
                    <div class="action-icon" onclick="copyText(this, \`${safeText}\`)"><i class="fas fa-copy"></i> Copy</div>
                    <div class="action-icon" onclick="regenerateLast()"><i class="fas fa-sync-alt"></i> Regen</div>
                    <div class="action-icon" onclick="shareContent(\`${safeText}\`)"><i class="fas fa-share-alt"></i> Share</div>
                </div>`;
            }
            const msgDiv = document.createElement('div');
            msgDiv.className = `msg ${role === 'user' ? 'user-msg' : 'ai-msg'}`;
            msgDiv.innerHTML = `<div class="msg-bubble" style="${role==='ai'?'background:transparent;padding:0;':''}">${contentHtml}</div>${actionsHtml}`;
            box.appendChild(msgDiv);
            box.scrollTo(0, box.scrollHeight);
        }

        /* --- 2. UPDATED SEND FUNCTION --- */
        /* --- UPDATED SEND FUNCTION --- */
        
        /* --- UPDATED SEND FUNCTION --- */
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
            chatBox.insertAdjacentHTML('beforeend', 
                `<div id="${msgId}" class="msg ai-msg"><div class="msg-bubble" style="color:var(--text-muted);">Thinking...</div></div>`
            );
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
                    const actionsHtml = `
                        <div class="msg-actions">
                            <div class="action-icon" onclick="copyText(this, \`${safeText}\`)"><i class="fas fa-copy"></i> Copy</div>
                            <div class="action-icon" onclick="regenerateLast()"><i class="fas fa-sync-alt"></i> Regen</div>
                            <div class="action-icon" onclick="shareContent(\`${safeText}\`)"><i class="fas fa-share-alt"></i> Share</div>
                        </div>`;
                    aiDiv.insertAdjacentHTML('beforeend', actionsHtml);
                    
                    isGenerating = false; 
                    chatBox.scrollTop = chatBox.scrollHeight;
                });
            } catch (e) {
                document.getElementById(msgId).innerHTML = "Error.";
                isGenerating = false;
            }
        }       
            
        // 6. HISTORY & CHAT MANAGEMENT
        async function loadHistory() {
             const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
             const data = await res.json();
             const list = document.getElementById('history-list'); list.innerHTML = "";
             if(data.chats) {
                 Object.keys(data.chats).reverse().forEach(cid => {
                     list.innerHTML += `
                        <div class="history-item">
                            <span onclick="loadChat('${cid}')" style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${data.chats[cid].title}</span>
                            <div class="history-actions">
                                <i class="fas fa-pen hist-icon" onclick="renameChat('${cid}')"></i>
                                <i class="fas fa-trash hist-icon" onclick="deleteChat('${cid}')"></i>
                            </div>
                        </div>`;
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
        function showModal(title, isInput, callback) {
            const modal = document.getElementById('custom-modal') || createModalElement();
            document.getElementById('m-title').innerText = title;
            const inp = document.getElementById('m-inp');
            inp.style.display = isInput ? 'block' : 'none';
            inp.value = "";
     
        modal.style.display = 'flex';
        window.modalCallback = (confirm) => {
        modal.style.display = 'none';
        if(confirm) callback(isInput ? inp.value : true);
        };
        }

        function createModalElement() {
        const div = document.createElement('div');
        div.id = 'custom-modal';
        div.innerHTML = `<div class="modal-content"><h3 id="m-title"></h3><input id="m-inp" class="modal-input"><div class="modal-btns"><button class="m-btn" style="background:#333;color:#fff" onclick="modalCallback(false)">Cancel</button><button class="m-btn" style="background:#fff;color:#000" onclick="modalCallback(true)">Confirm</button></div></div>`;
        document.body.appendChild(div);
        return div;
        }

        async function renameChat(cid) {
             showModal("Rename Chat", true, async (newTitle) => {
        if(newTitle) {
            await fetch('/rename_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid, title:newTitle})});
            loadHistory();
        }
        });
         }

        async function deleteChat(cid) {
        showModal("Delete this chat?", false, async () => {
        await fetch('/delete_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
        loadHistory();
        if(currentChatId === cid) document.getElementById('chat-box').innerHTML = "";
        });
        }
        
        function newChat() {
            currentChatId = null;
            document.getElementById('chat-box').innerHTML = `<div class="msg ai-msg"><div class="ai-content"><h1>Hi ${currentUser},</h1><p>Start a new topic!</p></div></div>`;
            toggleSidebar();
        }

        // FIXED SEARCH & CLEAR LOGIC
        function filterHistory(query) {
            const items = document.querySelectorAll('.history-item');
            const clearBtn = document.getElementById('clear-search');
            clearBtn.style.display = query.length > 0 ? 'block' : 'none';
    
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
        
        // 7. INITIALIZE APP
        checkLogin();
    </script>
    
</body>       
</html>
"""
"""Part 3: Backend Routes & Main Execution
(இதை Part 2 முடிஞ்ச இடத்துல இருந்து அப்படியே தொடர்ந்து பேஸ்ட் பண்ணுங்க. முக்கியம்: இதை மிஸ் பண்ணிடாதீங்க)"""
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
        
    # chat() function-ன் இறுதியில் இதைச் சேர்க்கவும்
    save_db(user_db) # <--- இதுதான் ஹிஸ்டரியைச் சேமிக்கும்
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