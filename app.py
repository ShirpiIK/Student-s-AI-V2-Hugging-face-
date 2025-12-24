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
        /* --- CORE VARIABLES --- */
        :root {
            --bg: #000000; --card: #141414; --user-msg: #27272a; 
            --text: #ececec; --text-muted: #a1a1aa; 
            --accent: #fff; --border: #27272a;
            --input-bg: #1a1a1a;
        }

        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; outline: none; }
        body { 
            margin: 0; background: var(--bg); color: var(--text); 
            font-family: 'Outfit', sans-serif; 
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            overflow: hidden; display: flex; flex-direction: column;
        }

        /* --- HEADER --- */
        header {
            height: 60px; padding: 0 15px; 
            background: rgba(0,0,0,0.8); backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            display: flex; align-items: center; justify-content: space-between; 
            z-index: 50; flex-shrink: 0;
        }
        .app-title { font-weight: 700; font-size: 18px; }
        .menu-btn { font-size: 20px; padding: 10px; cursor: pointer; }

        /* --- CHAT BOX --- */
        #chat-box { 
            flex: 1; overflow-y: auto; padding: 20px 15px; 
            /* 👇 FIX: Reduced empty space */
            padding-bottom: 20px; 
            display: flex; flex-direction: column; gap: 25px; scroll-behavior: smooth;
        }

        .msg { display: flex; flex-direction: column; width: 100%; }
        .user-msg { align-items: flex-end; }
        .ai-msg { align-items: flex-start; }

        .msg-content { 
            padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.6; 
            max-width: 85%; word-wrap: break-word;
        }
        .user-msg .msg-content { 
            background: var(--user-msg); color: #fff; 
            border-bottom-right-radius: 4px;
        }
        .ai-msg .msg-content { 
            background: transparent; padding-left: 0; color: var(--text); 
        }

        /* 👇 FIX: ACTIONS VISIBLE ALWAYS (Not just on click/hover) */
        .msg-actions { 
            display: flex; gap: 15px; margin-top: 8px; opacity: 0.7; 
            font-size: 12px; padding: 0 5px;
        }
        .action-icon { cursor: pointer; display: flex; align-items: center; gap: 5px; color: var(--text-muted); }
        .action-icon:hover { color: #fff; }

        /* --- PREVIEW AREA (NEW) --- */
        #preview-container {
            display: none; padding: 10px 15px; background: var(--bg);
            border-top: 1px solid var(--border);
        }
        .preview-box {
            position: relative; display: inline-block;
            width: 60px; height: 60px; border-radius: 10px;
            overflow: hidden; border: 1px solid var(--border);
        }
        .preview-img { width: 100%; height: 100%; object-fit: cover; cursor: pointer; }
        .close-preview {
            position: absolute; top: 2px; right: 2px;
            background: rgba(0,0,0,0.7); color: #fff; border-radius: 50%;
            width: 18px; height: 18px; display: flex; align-items: center; 
            justify-content: center; font-size: 10px; cursor: pointer;
        }

        /* --- INPUT AREA (PROFESSIONAL DESIGN) --- */
        .input-wrapper { 
            background: var(--bg); padding: 10px 15px; 
            padding-bottom: max(15px, env(safe-area-inset-bottom));
            flex-shrink: 0; z-index: 60;
        }
        .input-container { 
            background: var(--input-bg); border: 1px solid var(--border); 
            border-radius: 30px; padding: 5px 8px; 
            display: flex; align-items: flex-end; gap: 8px;
            transition: border 0.3s;
        }
        .input-container:focus-within { border-color: #444; }

        /* Icon Styling */
        .attach-btn {
            width: 40px; height: 40px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            color: var(--text-muted); cursor: pointer; font-size: 18px;
            transition: color 0.2s;
        }
        .attach-btn:hover { color: #fff; background: rgba(255,255,255,0.05); }

        textarea { 
            flex: 1; background: transparent; border: none; color: #fff; 
            font-size: 16px; max-height: 120px; padding: 10px 5px; 
            resize: none; font-family: 'Outfit', sans-serif;
        }

        .send-btn { 
            width: 40px; height: 40px; border-radius: 50%;
            background: #fff; color: #000; display: flex; 
            align-items: center; justify-content: center; 
            cursor: pointer; font-size: 16px; transition: transform 0.2s;
            margin-bottom: 2px;
        }
        .send-btn:active { transform: scale(0.9); }

        /* --- SIDEBAR & OVERLAY --- */
        #sidebar-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.6); 
            backdrop-filter: blur(3px); z-index: 99; opacity: 0; 
            pointer-events: none; transition: opacity 0.3s;
        }
        #sidebar-overlay.active { opacity: 1; pointer-events: auto; }

        #sidebar {
            position: fixed; top: 0; left: 0; width: 280px; height: 100%; 
            background: #09090b; z-index: 100; border-right: 1px solid var(--border);
            transform: translateX(-100%); transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
            display: flex; flex-direction: column;
        }
        #sidebar.open { transform: translateX(0); }

        /* History Styling */
        .history-item { 
            padding: 15px; margin: 5px 10px; border-radius: 10px; 
            color: var(--text-muted); font-size: 14px; 
            display: flex; justify-content: space-between; align-items: center;
            cursor: pointer; transition: 0.2s;
        }
        .history-item:active { background: var(--card); color: #fff; }

        /* --- PROFESSIONAL CUSTOM MODAL --- */
        #custom-modal {
            position: fixed; inset: 0; background: rgba(0,0,0,0.8); 
            z-index: 2000; display: none; align-items: center; justify-content: center;
            backdrop-filter: blur(5px);
        }
        .modal-box {
            background: #18181b; width: 90%; max-width: 320px;
            padding: 25px; border-radius: 20px; border: 1px solid #333;
            text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            transform: scale(0.9); animation: popIn 0.2s forwards;
        }
        @keyframes popIn { to { transform: scale(1); } }
        
        .modal-title { font-size: 18px; font-weight: 700; color: #fff; margin-bottom: 10px; }
        .modal-input {
            width: 100%; padding: 12px; border-radius: 10px; 
            background: #000; border: 1px solid #333; color: #fff;
            margin: 15px 0; font-size: 16px; outline: none;
        }
        .modal-input:focus { border-color: #fff; }
        
        .modal-btns { display: flex; gap: 10px; margin-top: 10px; }
        .m-btn { flex: 1; padding: 12px; border-radius: 12px; border: none; font-weight: 600; cursor: pointer; }
        .m-cancel { background: #27272a; color: #fff; }
        .m-confirm { background: #fff; color: #000; }

        /* Image View Modal */
        #img-viewer {
            position: fixed; inset: 0; z-index: 3000; background: rgba(0,0,0,0.95);
            display: none; align-items: center; justify-content: center;
        }
        #img-viewer img { max-width: 95%; max-height: 90%; border-radius: 5px; }
        .close-viewer { position: absolute; top: 20px; right: 20px; color: #fff; font-size: 24px; cursor: pointer; }

        /* Misc */
        .typing-cursor::after { content: 'l'; animation: blink 1s infinite; }
        @keyframes blink { 50% { opacity: 0; } }
    </style>
    <body>
    <div id="img-viewer">
        <div class="close-viewer" onclick="document.getElementById('img-viewer').style.display='none'">&times;</div>
        <img id="full-image" src="">
    </div>

    <div id="custom-modal">
        <div class="modal-box">
            <div class="modal-title" id="m-title">Title</div>
            <input type="text" id="m-input" class="modal-input" autocomplete="off" placeholder="Type here...">
            <div class="modal-btns">
                <button class="m-btn m-cancel" onclick="closeModal()">Cancel</button>
                <button class="m-btn m-confirm" id="m-confirm-btn">Confirm</button>
            </div>
        </div>
    </div>

    <div id="sidebar-overlay" onclick="toggleSidebar(false)"></div>

    <div id="sidebar">
        <div style="padding: 20px; border-bottom: 1px solid var(--border); display:flex; justify-content:space-between; align-items:center;">
            <span style="color:#fff; font-weight:700; font-size:18px;">Menu</span>
            <i class="fas fa-times" style="color:#aaa; font-size:20px; cursor:pointer;" onclick="toggleSidebar(false)"></i>
        </div>
        <div style="padding:15px;">
            <div style="background:#fff; color:#000; padding:12px; border-radius:10px; text-align:center; font-weight:600; cursor:pointer;" onclick="newChat()">+ New Chat</div>
        </div>
        <div style="padding: 0 15px; color:#666; font-size:12px; font-weight:600; text-transform:uppercase;">History</div>
        <div id="history-list" style="flex:1; overflow-y:auto; padding:10px 0;"></div>
        <div style="padding:15px; border-top:1px solid var(--border); color:#ccc; cursor:pointer;" onclick="alert('Settings Page')">
            <i class="fas fa-cog"></i> Settings
        </div>
    </div>

    <header>
        <div class="menu-btn" onclick="toggleSidebar(true)"><i class="fas fa-bars"></i></div>
        <span class="app-title">Student's AI</span>
        <div style="width:40px;"></div>
    </header>

    <div id="chat-box">
        </div>

    <div id="preview-container">
        <div class="preview-box">
            <img id="preview-img" class="preview-img" onclick="viewImage(this.src)">
            <div class="close-preview" onclick="clearFile()">×</div>
        </div>
    </div>

    <div class="input-wrapper">
        <div class="input-container">
            <div class="attach-btn" onclick="document.getElementById('file-upload').click()">
                <i class="fas fa-paperclip"></i>
            </div>
            <input type="file" id="file-upload" hidden accept="image/*" onchange="handleFile(this)">
            
            <textarea id="input" placeholder="Type a message..." rows="1" oninput="autoResize(this)"></textarea>
            
            <div class="send-btn" onclick="send()">
                <i class="fas fa-arrow-up"></i>
            </div>
        </div>
    </div>
    <script>
        let currentUser = "Shirpi"; // Default for now
        let currentChatId = null;
        let currentFile = null;
        let isGenerating = false;

        // --- 1. SIDEBAR LOGIC ---
        function toggleSidebar(open) {
            const sb = document.getElementById('sidebar');
            const ov = document.getElementById('sidebar-overlay');
            if(open) {
                sb.classList.add('open');
                ov.classList.add('active');
            } else {
                sb.classList.remove('open');
                ov.classList.remove('active');
            }
        }

        // --- 2. FILE HANDLING & PREVIEW ---
        function handleFile(input) {
            if(input.files && input.files[0]) {
                const r = new FileReader();
                r.onload = function(e) {
                    currentFile = e.target.result;
                    document.getElementById('preview-container').style.display = 'block';
                    document.getElementById('preview-img').src = currentFile;
                }
                r.readAsDataURL(input.files[0]);
            }
        }

        function clearFile() {
            currentFile = null;
            document.getElementById('file-upload').value = "";
            document.getElementById('preview-container').style.display = 'none';
        }

        function viewImage(src) {
            document.getElementById('full-image').src = src;
            document.getElementById('img-viewer').style.display = 'flex';
        }

        function autoResize(el) {
            el.style.height = 'auto';
            el.style.height = el.scrollHeight + 'px';
        }

        // --- 3. CHAT & TYPEWRITER LOGIC ---
        async function send() {
            if(isGenerating) return;
            const inp = document.getElementById('input');
            const txt = inp.value.trim();
            if(!txt && !currentFile) return;

            // UI Cleanup
            inp.value = ""; inp.style.height = 'auto';
            document.getElementById('preview-container').style.display = 'none';
            
            // Add User Msg
            addMsg('user', txt, currentFile);
            let fileData = currentFile; currentFile = null; // Reset after sending

            // AI Placeholder
            const msgId = "ai-" + Date.now();
            const box = document.getElementById('chat-box');
            box.insertAdjacentHTML('beforeend', 
                `<div id="${msgId}" class="msg ai-msg">
                    <div class="msg-content typing-cursor">Thinking...</div>
                </div>`
            );
            box.scrollTo(0, box.scrollHeight);
            isGenerating = true;

            // Fetch Logic (Keep existing backend logic)
            if(!currentChatId) {
                // Creates new chat logic here...
                currentChatId = "chat-" + Date.now(); // Simulation
            }

            try {
                const res = await fetch('/chat', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: txt, image: fileData, username: currentUser, chat_id: currentChatId })
                });
                const data = await res.json();
                
                // Start Typewriter
                const aiContentDiv = document.getElementById(msgId).querySelector('.msg-content');
                aiContentDiv.classList.remove('typing-cursor');
                aiContentDiv.innerHTML = ""; // Clear "Thinking..."
                
                typeWriter(aiContentDiv, data.response, msgId);

            } catch(e) {
                document.getElementById(msgId).innerHTML = "Error.";
                isGenerating = false;
            }
        }

        function addMsg(role, text, img) {
            const box = document.getElementById('chat-box');
            let imgHtml = img ? `<img src="${img}" onclick="viewImage(this.src)" style="max-width:200px; border-radius:10px; margin-bottom:5px; cursor:pointer;">` : "";
            let content = text; // User text is raw
            
            let actions = "";
            if(role === 'user') {
                actions = `
                <div class="msg-actions" style="justify-content:flex-end;">
                    <div class="action-icon" onclick="document.getElementById('input').value='${text}'"><i class="fas fa-pen"></i></div>
                    <div class="action-icon" onclick="navigator.clipboard.writeText('${text}')"><i class="fas fa-copy"></i></div>
                </div>`;
            }

            box.insertAdjacentHTML('beforeend', 
                `<div class="msg ${role}-msg">
                    <div class="msg-content">${imgHtml}${content}</div>
                    ${actions}
                </div>`
            );
            box.scrollTo(0, box.scrollHeight);
        }

        // --- TYPEWRITER EFFECT (ChatGPT Style) ---
        function typeWriter(element, text, msgId) {
            // For simple line-by-line effect without backend stream:
            // We parse markdown first, then reveal standard elements or just type raw text then render.
            // Best visual: Type raw words, then render markdown at end.
            
            let words = text.split(" ");
            let i = 0;
            element.innerText = "";
            
            function type() {
                if (i < words.length) {
                    element.innerText += words[i] + " ";
                    i++;
                    document.getElementById('chat-box').scrollTo(0, document.getElementById('chat-box').scrollHeight);
                    setTimeout(type, 30); // Speed of typing
                } else {
                    // Finished typing, render Markdown & Add Actions
                    element.innerHTML = marked.parse(text);
                    addAiActions(msgId, text);
                    isGenerating = false;
                }
            }
            type();
        }

        function addAiActions(msgId, text) {
            const div = document.getElementById(msgId);
            const actions = `
            <div class="msg-actions">
                <div class="action-icon" onclick="navigator.clipboard.writeText(\`${text.replace(/`/g, '\\`')}\`)"><i class="fas fa-copy"></i> Copy</div>
                <div class="action-icon" onclick="alert('Regenerate')"><i class="fas fa-sync"></i> Regen</div>
                <div class="action-icon"><i class="fas fa-share"></i> Share</div>
            </div>`;
            div.insertAdjacentHTML('beforeend', actions);
        }

        // --- 4. CUSTOM MODALS (Unique & Professional) ---
        let modalCallback = null;

        function showModal(title, isInput, placeholder, cb) {
            const m = document.getElementById('custom-modal');
            document.getElementById('m-title').innerText = title;
            const inp = document.getElementById('m-input');
            
            if(isInput) {
                inp.style.display = 'block';
                inp.value = "";
                inp.placeholder = placeholder;
                inp.focus();
            } else {
                inp.style.display = 'none';
            }
            
            modalCallback = cb;
            m.style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('custom-modal').style.display = 'none';
            modalCallback = null;
        }

        document.getElementById('m-confirm-btn').onclick = function() {
            const val = document.getElementById('m-input').value;
            if(modalCallback) modalCallback(val);
            closeModal();
        };

        // Long Press Simulation for History
        // (Call this from your existing loadHistory function logic)
        function showHistoryOptions(chatId) {
            // This replaces the old ugly popup logic
            // Example usage: Right click or Long press context
            showModal("Manage Chat", false, "", () => {
                // This is a placeholder for action selection
                // Ideally, show buttons for Rename / Delete inside modal
                // For simplicity as requested:
                showRename(chatId);
            });
        }

        function showRename(cid) {
            showModal("Rename Chat", true, "New name...", (val) => {
                if(val) fetch('/rename_chat', { /*...*/ });
            });
        }
        
        function showDelete(cid) {
            showModal("Delete Chat?", false, "", () => {
                fetch('/delete_chat', { /*...*/ });
            });
        }

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