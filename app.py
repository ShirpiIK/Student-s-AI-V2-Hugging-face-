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
BASE_INSTRUCTION = """
ROLE: You are "Student's AI", a professional academic tutor.
RULES:
1. **MATH:** Use LaTeX for formulas ($$ ... $$).
2. **DIAGRAMS:** Use Mermaid.js (```mermaid ... ```).
3. **LANGUAGE:** English by default. Use Tamil/Tanglish ONLY if requested.
4. **FORMAT:** Markdown. Bold key terms.
"""

# --- 🧬 MODEL FUNCTIONS ---
def get_working_model(key):
    try:
        genai.configure(api_key=key)
        return 'gemini-1.5-flash'
    except: return None

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
    
    # --- PHASE 1: CONTEXT INTEGRATION ---
    full_prompt = prompt
    if user_context:
        full_prompt = f"[Student Context: {user_context}]\nQuestion: {prompt}"

    if file_text: current_parts.append(f"analyzing file:\n{file_text}\n\n")
    current_parts.append(full_prompt)
    if image_data:
        img = process_image(image_data)
        if img: current_parts.append(img)

    for i in range(len(API_KEYS)):
        key = API_KEYS[current_key_index]
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=BASE_INSTRUCTION)
            if image_data or file_text: response = model.generate_content(current_parts)
            else:
                chat = model.start_chat(history=formatted_history)
                response = chat.send_message(full_prompt)
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
        body { margin: 0; background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; height: 100dvh; overflow: hidden; }
        
        /* HEADER */
        header { height: 70px; padding: 0 20px; background: rgba(9,9,11, 0.98); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; position: absolute; top: 0; width: 100%; z-index: 50; }
        .app-title { font-size: 24px; font-weight: 800; color: #fff; }
        .menu-btn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #333; display: flex; align-items: center; justify-content: center; cursor: pointer; color:#fff; }
        .settings-icon { font-size: 18px; color: #aaa; cursor: pointer; }

        /* MAIN CONTAINER */
        #app-container { display: flex; flex-direction: column; height: 100dvh; padding-top: 70px; }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px 5%; padding-bottom: 80px; display: flex; flex-direction: column; gap: 20px; }
        
        /* OVERLAYS (LOGIN & SELECTION) */
        .overlay { position: fixed; inset: 0; background: #000; z-index: 2000; display: flex; align-items: flex-start; justify-content: center; padding-top: 150px; transition: opacity 0.3s; }
        
        /* IMPORTANT: 'hidden' class with !important to force hide */
        .overlay.hidden { display: none !important; opacity: 0; pointer-events: none; }
        
        .login-box { width: 90%; max-width: 350px; text-align: center; padding: 30px; border: 1px solid var(--border); border-radius: 20px; background: #0a0a0a; }
        
        /* FORM ELEMENTS */
        .form-label { display: block; text-align: left; font-size: 12px; color: #aaa; margin-bottom: 5px; margin-top: 15px; }
        input, select { width: 100%; padding: 12px; margin-bottom: 5px; background: #18181b; border: 1px solid #333; color: #fff; border-radius: 8px; outline: none; font-size: 16px; font-family: 'Outfit', sans-serif; }
        .start-btn { width: 100%; padding: 15px; border-radius: 12px; border: none; background: #fff; font-weight: 800; cursor: pointer; font-size: 16px; margin-top: 25px; }

        /* MESSAGES */
        .msg { display: flex; flex-direction: column; opacity: 0; animation: fadeInstant 0.3s forwards; }
        @keyframes fadeInstant { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .user-msg { align-items: flex-end; }
        .user-content { background: var(--user-msg); padding: 10px 16px; border-radius: 18px 18px 4px 18px; max-width: 85%; color: #fff; }
        .ai-msg { align-items: flex-start; }
        .ai-content { width: 100%; color: #d4d4d8; }
        .ai-content strong { color: #fff; }

        /* INPUT AREA */
        .input-wrapper { background: var(--bg); padding: 15px; border-top: 1px solid var(--border); }
        .input-container { max-width: 900px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 24px; padding: 8px 12px; display: flex; align-items: flex-end; gap: 12px; }
        textarea { flex: 1; background: transparent; border: none; color: #fff; font-size: 17px; max-height: 120px; padding: 10px 5px; resize: none; outline: none; font-family: 'Outfit', sans-serif; }
        .icon-btn, .send-btn { width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: none; cursor: pointer; font-size: 18px; }
        .icon-btn { background: transparent; color: #a1a1aa; }
        .send-btn { background: #fff; color: #000; }

        /* SIDEBAR */
        #sidebar { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: var(--bg); z-index: 100; padding: 25px; padding-top: 80px; transform: translateY(-100%); transition: transform 0.4s; }
        #sidebar.open { transform: translateY(0); }
        
        /* INTRO */
        #intro-container { position: absolute; top: 140px; left: 50%; transform: translateX(-50%); width: 90%; max-width: 600px; text-align: center; pointer-events: none; z-index: 10; }
        
        #preview-area { display:none; position:absolute; bottom:85px; left:20px; }
        .preview-box { width:60px; height:60px; background:#222; border:2px solid #fff; border-radius:12px; overflow:hidden; }
        .preview-img { width:100%; height:100%; object-fit:cover; }
    </style>
</head>
<body>

    <div id="login-overlay" class="overlay">
        <div class="login-box">
            <h1 class="app-title" style="margin-bottom:10px;">Student's AI</h1>
            <input type="text" id="username-input" placeholder="Your Name">
            <button class="start-btn" onclick="handleLogin()">Next</button>
        </div>
    </div>

    <div id="selection-overlay" class="overlay hidden">
        <div class="login-box">
            <h2 style="color:#fff; margin-top:0;">Customize Profile</h2>
            
            <span class="form-label">Education Level</span>
            <select id="edu-level" onchange="updateEduOptions()">
                <option value="school">School (6th - 12th)</option>
                <option value="college">College (Arts/Engg)</option>
            </select>

            <span class="form-label">Class / Year</span>
            <select id="edu-year"></select>

            <span class="form-label">Subject (Optional)</span>
            <input type="text" id="edu-subject" placeholder="Ex: Maths, Physics...">

            <button class="start-btn" onclick="handleSelection()">Start Learning</button>
        </div>
    </div>

    <div id="sidebar">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div style="font-size:20px; font-weight:700; color:#fff;">Hi <span id="display-name">User</span></div>
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-times"></i></div>
        </div>
        <button class="start-btn" style="margin:0 0 20px 0; padding:12px;" onclick="newChat()">New Chat</button>
        <div style="color:#71717a; font-size:13px; font-weight:600; text-transform:uppercase;">Chat History</div>
        <div id="history-list" style="margin-top:10px;"></div>
        <div style="position:absolute; bottom:30px; width:100%; left:0; text-align:center;">
             <div style="color:#ef4444; cursor:pointer; font-weight:600;" onclick="handleLogout()">Log Out</div>
        </div>
    </div>

    <div id="app-container">
        <header>
            <div class="menu-btn" onclick="toggleSidebar()"><i class="fas fa-bars"></i></div>
            <span class="app-title">Student's AI</span>
            <div class="settings-icon" onclick="openSettings()"><i class="fas fa-cog"></i></div>
        </header>

        <div id="chat-box"></div>

        <div class="input-wrapper">
             <div id="preview-area">
                <div class="preview-box"><img id="preview-img" class="preview-img"></div>
                <button onclick="clearAttachment()" style="background:red; color:white; border:none; border-radius:50%; width:20px; height:20px; position:absolute; top:-5px; right:-5px;">×</button>
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
        let currentUser = null;
        let currentChatId = null;
        let userContext = "";
        let currentAttachment = null;

        function getIntroHtml(name) {
            return `<div id="intro-container"><div class="msg ai-msg"><div class="ai-content"><h1>Hi ${name},</h1><p>Ready to master ${userContext ? userContext.split(',')[0] : "studies"}?</p></div></div></div>`;
        }

        // --- AUTH & PHASE 1 LOGIC (FIXED) ---
        function checkLogin() {
            const u = localStorage.getItem("student_ai_user");
            const c = localStorage.getItem("student_ai_context");
            
            if(u) {
                currentUser = u;
                // Previously logged in? Hide Login
                document.getElementById('login-overlay').style.display = 'none';
                
                if(c) {
                    // Context exists? Go to App
                    userContext = c;
                    document.getElementById('selection-overlay').style.display = 'none';
                    showApp();
                } else {
                    // Context missing? Show Selection
                    const sel = document.getElementById('selection-overlay');
                    sel.classList.remove('hidden'); 
                    sel.style.display = 'flex'; // FORCE SHOW
                    updateEduOptions();
                }
            }
        }

        function handleLogin() {
            const name = document.getElementById("username-input").value.trim();
            if(!name) { alert("Please enter a name"); return; }
            
            localStorage.setItem("student_ai_user", name);
            currentUser = name;

            // --- FORCE TRANSITION TO SELECTION ---
            document.getElementById("login-overlay").style.display = 'none'; // Hide Login
            
            const sel = document.getElementById("selection-overlay");
            sel.classList.remove('hidden'); 
            sel.style.display = 'flex'; // FORCE SHOW
            
            updateEduOptions();
        }

        function updateEduOptions() {
            const level = document.getElementById('edu-level').value;
            const yearSelect = document.getElementById('edu-year');
            yearSelect.innerHTML = "";
            let opts = level === 'school' ? ["6th", "7th", "8th", "9th", "10th", "11th", "12th"] : ["1st Year", "2nd Year", "3rd Year", "4th Year"];
            opts.forEach(o => {
                let op = document.createElement('option');
                op.value = o; op.innerText = o;
                yearSelect.appendChild(op);
            });
        }

        function handleSelection() {
            const l = document.getElementById('edu-level').value;
            const y = document.getElementById('edu-year').value;
            const s = document.getElementById('edu-subject').value;
            
            userContext = `${l}, ${y}, ${s}`;
            localStorage.setItem("student_ai_context", userContext);
            
            // Hide Selection -> Show App
            document.getElementById('selection-overlay').style.display = 'none';
            showApp();
        }

        function showApp() {
            document.getElementById('display-name').innerText = currentUser;
            loadHistory();
            if(!currentChatId && !document.getElementById('intro-container')) {
                document.getElementById('chat-box').innerHTML = getIntroHtml(currentUser);
            }
        }

        function handleLogout() {
            localStorage.clear();
            location.reload();
        }

        function openSettings() {
            const sel = document.getElementById("selection-overlay");
            sel.classList.remove('hidden');
            sel.style.display = 'flex';
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

        async function send() {
            const txt = document.getElementById('input').value.trim();
            if(!txt && !currentAttachment) return;

            const intro = document.getElementById('intro-container');
            if(intro) intro.remove();

            const box = document.getElementById('chat-box');
            let imgHtml = currentAttachment ? `<br><img src="${currentAttachment}" style="max-height:100px;border-radius:8px;">` : "";
            box.insertAdjacentHTML('beforeend', `<div class="msg user-msg"><div class="user-content">${txt}${imgHtml}</div></div>`);
            
            document.getElementById('input').value = "";
            let imgData = currentAttachment;
            clearAttachment();
            box.scrollTo(0, box.scrollHeight);

            const msgId = "ai-" + Date.now();
            box.insertAdjacentHTML('beforeend', `<div id="${msgId}" class="msg ai-msg">...</div>`);
            
            try {
                if(!currentChatId) {
                    const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                    const d = await r.json(); currentChatId = d.chat_id;
                }
                const res = await fetch('/chat', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({message:txt, image:imgData, username:currentUser, chat_id:currentChatId, user_context:userContext})
                });
                const data = await res.json();
                document.getElementById(msgId).innerHTML = `<div class="ai-content">${marked.parse(data.response)}</div>`;
                hljs.highlightAll();
                box.scrollTo(0, box.scrollHeight);
                if(data.new_title) loadHistory();
            } catch(e) { document.getElementById(msgId).innerText = "Error."; }
        }

        async function loadHistory() {
             try {
                const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                const data = await res.json();
                const list = document.getElementById('history-list'); list.innerHTML = "";
                Object.keys(data.chats).reverse().forEach(cid => {
                    list.innerHTML += `<div style="padding:10px; margin-bottom:5px; background:#18181b; border-radius:8px; cursor:pointer;" onclick="loadChat('${cid}')">${data.chats[cid].title || "Chat"}</div>`;
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

        // Init
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