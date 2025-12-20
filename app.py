import os
import uuid
import time
import json
import warnings
from flask import Flask, request, jsonify, render_template_string, Response
import google.generativeai as genai

# --- DISABLE WARNINGS ---
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

# --- 🧠 SYSTEM INSTRUCTION (Dynamic based on Selection) ---
BASE_SYSTEM_INSTRUCTION = """
ROLE: You are "Student's AI", a professional academic tutor.
RULES:
1. **MATH:** Use LaTeX for formulas ($$ ... $$).
2. **FORMAT:** Markdown. Bold key terms.
3. **TONE:** Helpful, encouraging, and clear.
"""

# --- 🧬 MODEL HANDLING ---
def get_working_model(key):
    try:
        genai.configure(api_key=key)
        return 'gemini-1.5-flash'
    except: return None

def generate_with_retry(prompt, user_context="", history_messages=[]):
    global current_key_index
    if not API_KEYS: return "🚨 API Keys Missing."

    formatted_history = []
    for m in history_messages[-6:]:
        role = "user" if m["role"] == "user" else "model"
        formatted_history.append({"role": role, "parts": [m["content"]]})

    # Combine User Context (Class/Subject) with System Instruction
    full_system_instruction = f"{BASE_SYSTEM_INSTRUCTION}\nCONTEXT: {user_context}"

    for i in range(len(API_KEYS)):
        key = API_KEYS[current_key_index]
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=full_system_instruction)
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Student's AI</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>window.MathJax = { tex: { inlineMath: [['$', '$']] }, svg: { fontCache: 'global' } };</script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

    <style>
        :root { --bg: #09090b; --card: #18181b; --text: #e4e4e7; --accent: #fff; --border: #27272a; }
        body { margin: 0; background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; height: 100dvh; overflow: hidden; display: flex; flex-direction: column; }
        
        /* HEADER LOCKED */
        header { height: 70px; padding: 0 20px; background: rgba(9,9,11, 0.98); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; position: absolute; top: 0; left: 0; right: 0; z-index: 50; }
        .app-title { font-size: 24px; font-weight: 800; color: #fff; }
        .settings-btn { color: #aaa; cursor: pointer; font-size: 18px; }

        /* ADS PLACEHOLDER */
        #ad-strip { position: absolute; top: 70px; left: 0; width: 100%; height: 50px; background: #111; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 12px; color: #555; z-index: 40; }

        /* MAIN CONTENT */
        #app-container { margin-top: 120px; flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; padding-bottom: 80px; display: flex; flex-direction: column; gap: 20px; }

        /* MESSAGES */
        .msg { display: flex; flex-direction: column; max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 16px; line-height: 1.6; }
        .user-msg { align-self: flex-end; background: #27272a; color: #fff; border-bottom-right-radius: 4px; }
        .ai-msg { align-self: flex-start; color: #d4d4d8; }
        
        /* INPUT AREA */
        .input-wrapper { padding: 15px; background: var(--bg); border-top: 1px solid var(--border); }
        .input-container { display: flex; gap: 10px; background: var(--card); padding: 8px 15px; border-radius: 24px; border: 1px solid var(--border); align-items: center; }
        textarea { flex: 1; background: transparent; border: none; color: #fff; font-size: 16px; outline: none; resize: none; max-height: 100px; font-family: 'Outfit', sans-serif; }
        .send-btn { background: #fff; color: #000; border: none; width: 35px; height: 35px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; }

        /* OVERLAYS (Login & Selection) */
        .overlay { position: fixed; inset: 0; background: #000; z-index: 2000; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 150px; transition: opacity 0.4s; }
        .overlay.hidden { opacity: 0; pointer-events: none; }
        
        .box { width: 90%; max-width: 350px; background: #0a0a0a; border: 1px solid var(--border); border-radius: 20px; padding: 30px; text-align: center; }
        .box h2 { margin-top: 0; margin-bottom: 20px; }
        
        input, select { width: 100%; padding: 12px; margin-bottom: 15px; background: #18181b; border: 1px solid #333; color: #fff; border-radius: 8px; outline: none; font-family: 'Outfit', sans-serif; }
        button.primary-btn { width: 100%; padding: 12px; background: #fff; color: #000; border: none; border-radius: 8px; font-weight: 700; cursor: pointer; font-size: 16px; }
        
        /* INTRO TEXT */
        #intro-text { position: absolute; top: 50px; width: 100%; text-align: center; color: #777; pointer-events: none; }
    </style>
</head>
<body>

    <div id="login-overlay" class="overlay">
        <div class="box">
            <h2>Student's AI</h2>
            <input type="text" id="username" placeholder="Enter your name">
            <button class="primary-btn" onclick="handleLogin()">Get Started</button>
        </div>
    </div>

    <div id="selection-overlay" class="overlay hidden">
        <div class="box">
            <h2>Customize Learning</h2>
            
            <label style="display:block; text-align:left; font-size:12px; color:#aaa; margin-bottom:5px;">Education Level</label>
            <select id="edu-level" onchange="updateOptions()">
                <option value="school">School (6th - 12th)</option>
                <option value="college">College (Engineering/Arts)</option>
            </select>

            <label style="display:block; text-align:left; font-size:12px; color:#aaa; margin-bottom:5px;">Class / Year</label>
            <select id="edu-year">
                </select>

            <label style="display:block; text-align:left; font-size:12px; color:#aaa; margin-bottom:5px;">Subject</label>
            <input type="text" id="edu-subject" placeholder="Ex: Maths, Physics, Python">

            <button class="primary-btn" onclick="handleSelection()">Start Chatting</button>
        </div>
    </div>

    <header>
        <span class="app-title">Student's AI</span>
        <div class="settings-btn" onclick="openSelection()"><i class="fas fa-cog"></i></div>
    </header>

    <div id="ad-strip">📢 Ad Space (Supports this App) 📢</div>

    <div id="app-container">
        <div id="chat-box">
            <div id="intro-text">
                <h2 id="intro-msg">Hi!</h2>
                <p>Ask me anything about your subject.</p>
            </div>
        </div>
        
        <div class="input-wrapper">
            <div class="input-container">
                <textarea id="input" rows="1" placeholder="Type your doubt..." oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
                <button class="send-btn" onclick="send()"><i class="fas fa-arrow-up"></i></button>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let userContext = "";
        let currentChatId = null;

        // --- ONBOARDING LOGIC ---
        function checkAuth() {
            const user = localStorage.getItem("student_user");
            const context = localStorage.getItem("student_context");
            
            if (user) {
                currentUser = user;
                document.getElementById('login-overlay').classList.add('hidden');
                
                if (context) {
                    userContext = context;
                    document.getElementById('selection-overlay').classList.add('hidden');
                    updateIntro();
                    loadHistory();
                } else {
                    document.getElementById('selection-overlay').classList.remove('hidden');
                    updateOptions();
                }
            }
        }

        function handleLogin() {
            const name = document.getElementById('username').value.trim();
            if (name) {
                localStorage.setItem("student_user", name);
                currentUser = name;
                document.getElementById('login-overlay').classList.add('hidden');
                document.getElementById('selection-overlay').classList.remove('hidden');
                updateOptions();
            }
        }

        function updateOptions() {
            const level = document.getElementById('edu-level').value;
            const yearSelect = document.getElementById('edu-year');
            yearSelect.innerHTML = "";
            
            let options = [];
            if (level === 'school') {
                options = ["6th Std", "7th Std", "8th Std", "9th Std", "10th Std", "11th Std", "12th Std"];
            } else {
                options = ["1st Year", "2nd Year", "3rd Year", "4th Year"];
            }
            
            options.forEach(opt => {
                const el = document.createElement("option");
                el.value = opt; el.innerText = opt;
                yearSelect.appendChild(el);
            });
        }

        function handleSelection() {
            const level = document.getElementById('edu-level').value;
            const year = document.getElementById('edu-year').value;
            const subject = document.getElementById('edu-subject').value;

            if (subject) {
                userContext = `Level: ${level}, Class: ${year}, Subject: ${subject}`;
                localStorage.setItem("student_context", userContext);
                
                document.getElementById('selection-overlay').classList.add('hidden');
                updateIntro();
                loadHistory(); // Load history or start new
                newChat();     // Ensure backend knows context
            } else {
                alert("Please enter a subject!");
            }
        }

        function openSelection() {
            document.getElementById('selection-overlay').classList.remove('hidden');
        }

        function updateIntro() {
            document.getElementById('intro-msg').innerText = `Hi ${currentUser},`;
            document.querySelector('#intro-text p').innerText = `Ready to master ${JSON.parse(JSON.stringify(userContext.split(',')[2] || "studies"))}?`;
        }

        // --- CHAT LOGIC ---
        async function send() {
            const input = document.getElementById('input');
            const text = input.value.trim();
            if (!text) return;

            // Remove Intro
            const intro = document.getElementById('intro-text');
            if(intro) intro.style.display = 'none';

            const box = document.getElementById('chat-box');
            box.insertAdjacentHTML('beforeend', `<div class="msg user-msg">${text}</div>`);
            
            input.value = '';
            box.scrollTop = box.scrollHeight;

            // Loading
            const msgId = "ai-" + Date.now();
            box.insertAdjacentHTML('beforeend', `<div id="${msgId}" class="msg ai-msg">...</div>`);
            box.scrollTop = box.scrollHeight;

            try {
                // Initial Chat Setup if needed
                if (!currentChatId) {
                    const r = await fetch('/new_chat', {
                        method:'POST', headers:{'Content-Type':'application/json'}, 
                        body:JSON.stringify({username:currentUser})
                    });
                    const d = await r.json(); currentChatId = d.chat_id;
                }

                const res = await fetch('/chat', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                        message: text, 
                        username: currentUser, 
                        chat_id: currentChatId,
                        user_context: userContext // Sending Context to Backend
                    })
                });
                const data = await res.json();
                
                document.getElementById(msgId).innerHTML = marked.parse(data.response);
                if(window.MathJax) MathJax.typesetPromise();
                box.scrollTop = box.scrollHeight;

            } catch (e) { document.getElementById(msgId).innerText = "Error: " + e.message; }
        }

        async function newChat() {
            try {
                const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                const d = await r.json(); currentChatId = d.chat_id;
            } catch(e) {}
        }
        
        async function loadHistory() {
             // Future: Implementation for history loading
        }

        // Init
        checkAuth();

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
    user_db[u][nid] = {"messages": []}
    save_db(user_db)
    return jsonify({"chat_id": nid})

@app.route("/chat", methods=["POST"])
def chat():
    d = request.json
    u = d.get("username")
    cid = d.get("chat_id")
    msg = d.get("message")
    context = d.get("user_context", "")

    if u not in user_db: user_db[u] = {}
    if cid not in user_db[u]: user_db[u][cid] = {"messages": []}

    user_db[u][cid]["messages"].append({"role": "user", "content": msg})
    
    # Generate Answer with RAG Context + User Context
    reply = generate_with_retry(msg, context, user_db[u][cid]["messages"][:-1])
    
    user_db[u][cid]["messages"].append({"role": "model", "content": reply})
    save_db(user_db)
    return jsonify({"response": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)
    