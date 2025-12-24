# ==========================================
# 👇 PART 1: PYTHON BACKEND & RAG SETUP 👇
# ==========================================
import sys
# 1. FIX FOR CHROMA DB IN HUGGING FACE (SQLite Version Fix)
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
import shutil
from PIL import Image
from flask import Flask, request, jsonify, render_template_string, Response
import google.generativeai as genai

# --- RAG IMPORTS (THE 4 PHASES) ---
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import SentenceTransformerEmbeddings

warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
keys_string = os.environ.get("API_KEYS", "")
API_KEYS = [k.strip() for k in keys_string.replace(',', ' ').replace('\n', ' ').split() if k.strip()]
current_key_index = 0

UPLOAD_FOLDER = 'uploads'
DB_FOLDER = 'db_store'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DB_FOLDER, exist_ok=True)

# --- DATABASE (User Chat History) ---
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

# ==========================================
# 👇 RAG LOGIC (THE 4 PHASES IMPLEMENTED) 👇
# ==========================================
vectorstore = None

def process_document_rag(file_path):
    global vectorstore
    try:
        # PHASE 1: LOADING (PDF-ஐ படிக்கிறோம்)
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        
        # PHASE 2: SPLITTING (சின்ன சின்ன துண்டுகளாக பிரிக்கிறோம்)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(docs)
        
        # PHASE 3: EMBEDDING (எழுத்துக்களை நம்பர்களாக மாத்துறோம்)
        embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # PHASE 4: STORING (ChromaDB-ல சேமிக்கிறோம்)
        # பழைய டேட்டா இருந்தால் அழித்துவிட்டு புதிதாக உருவாக்குவோம் (For simple usage)
        if os.path.exists(DB_FOLDER):
            shutil.rmtree(DB_FOLDER)
            
        vectorstore = Chroma.from_documents(
            documents=splits, 
            embedding=embeddings, 
            persist_directory=DB_FOLDER
        )
        return True, "PDF Processed Successfully! I can now answer from it."
    except Exception as e:
        return False, str(e)

def query_rag(question):
    global vectorstore
    if not vectorstore:
        # Load existing DB if available
        if os.path.exists(DB_FOLDER):
            embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
            vectorstore = Chroma(persist_directory=DB_FOLDER, embedding_function=embeddings)
        else:
            return None
            
    try:
        # RETRIEVAL (கேள்விக்கு ஏற்ற பதிலை தேடுகிறோம்)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
        docs = retriever.get_relevant_documents(question)
        context_text = "\n\n".join([d.page_content for d in docs])
        return context_text
    except: return None

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

def generate_with_retry(prompt, image_data=None, history_messages=[], user_context="", rag_context=None):
    global current_key_index
    if not API_KEYS: return "🚨 API Keys Missing."
    
    formatted_history = []
    # Send last 10 messages for context
    for m in history_messages[-10:]:
        role = "user" if m["role"] == "user" else "model"
        formatted_history.append({"role": role, "parts": [m["content"]]})
        
    current_parts = []
    
    # SYSTEM INSTRUCTION
    system_instruction = f"You are a professional academic AI assistant. The student's profile: {user_context}. "
    
    # RAG CONTEXT INJECTION
    if rag_context:
        system_instruction += f"\n\n[REFERENCE DOCUMENT CONTENT]:\n{rag_context}\n\nUse the above reference to answer if relevant."
    
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
/* ==========================================
   👇 PART 2: CSS STYLING 👇
   ========================================== */
   HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#000000">
    <title>Student's AI</title>
    
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Outfit:wght@500;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

    <style>
    /* --- VARIABLES --- */
    :root { 
        --bg-chat: #000000; --card: #18181b; --user-msg: #27272a; --text: #e4e4e7; 
        --dim: #a1a1aa; --border: #27272a; --accent: #fff;
    }

    /* --- BODY LOCK (PREVENTS KEYBOARD JUMP) --- */
    * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; outline: none; }
    
    body { 
        margin: 0; background: var(--bg-chat); color: var(--text); 
        font-family: 'Inter', sans-serif; 
        /* 👇 This locks the screen */
        position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
        overflow: hidden; display: flex; flex-direction: column;
    }

    /* --- GLOBAL BACKGROUND (Visible only on Login) --- */
    .global-bg {
        position: fixed; inset: 0; z-index: 1; pointer-events: none;
        background: radial-gradient(circle at center, #1a0b2e 0%, #000000 100%);
    }
    .blob { position: absolute; border-radius: 50%; filter: blur(70px); opacity: 0.6; animation: float 10s infinite alternate; }
    .b1 { top: -10%; left: -10%; width: 50vw; height: 50vw; background: #9d4edd; }
    .b2 { bottom: -10%; right: -10%; width: 50vw; height: 50vw; background: #00b4d8; animation-delay: -5s; }
    @keyframes float { from { transform: translate(0,0); } to { transform: translate(30px, 30px); } }

    /* --- LOGIN OVERLAYS --- */
    .overlay {
        position: fixed; inset: 0; z-index: 6000; /* Higher than header */
        background: transparent; 
        display: flex; flex-direction: column; 
        align-items: center; justify-content: center;
        padding: 20px; transition: opacity 0.3s ease;
    }
    .overlay.hidden { opacity: 0; pointer-events: none; display: none !important; }

    .glass-box {
        width: 100%; max-width: 380px;
        background: rgba(255,255,255,0.03); backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.1); border-radius: 24px;
        padding: 30px 25px; display: flex; flex-direction: column; gap: 15px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .title-lg { font-family: 'Outfit', sans-serif; font-size: 32px; font-weight: 700; color: #fff; text-align: center; }
    .subtitle { color: var(--dim); text-align: center; font-size: 14px; margin-bottom: 20px; }

    /* --- INPUTS & BUTTONS --- */
    label { font-size: 12px; font-weight: 600; color: var(--dim); text-transform: uppercase; margin-left: 4px; margin-bottom: -8px; }
    input, select {
        width: 100%; background: rgba(0,0,0,0.3); border: 1px solid var(--border);
        color: #fff; padding: 14px; border-radius: 14px; font-size: 16px;
        font-family: 'Inter', sans-serif;
    }
    /* Stop Search Cross Icon */
    input[type="search"]::-webkit-search-cancel-button { -webkit-appearance: none; }

    .btn-primary {
        background: #fff; color: #000; border: none; padding: 14px;
        border-radius: 14px; font-weight: 700; font-size: 16px; font-family: 'Outfit', sans-serif;
        cursor: pointer; margin-top: 10px; width: 100%;
    }

    /* --- CHAT HEADER (LOCKED) --- */
    header {
        height: 65px; padding: 0 20px; background: rgba(0,0,0,0.8); backdrop-filter: blur(10px);
        border-bottom: 1px solid var(--border); display: flex; align-items: center;
        flex-shrink: 0; z-index: 100; position: relative; justify-content: space-between;
    }
    header.hidden { display: none; }
    .header-info { text-align: center; flex: 1; display: flex; flex-direction: column; }
    .student-name { font-family: 'Outfit', sans-serif; font-size: 18px; font-weight: 700; color: #fff; }
    .status-text { font-size: 11px; color: var(--dim); margin-top: 2px; }
    .icon-btn { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: transparent; border: 1px solid var(--border); color: #fff; cursor: pointer; }

    /* --- CHAT AREA (SCROLLABLE) --- */
    #chat-box {
        flex-grow: 1; overflow-y: auto; padding: 20px 15px; display: flex; flex-direction: column; gap: 20px;
        background: #000; height: 0; min-height: 0;
    }
    .msg { display: flex; flex-direction: column; max-width: 85%; }
    .user-msg { align-self: flex-end; align-items: flex-end; }
    .ai-msg { align-self: flex-start; align-items: flex-start; width: 100%; }
    
    .msg-content { padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.5; word-wrap: break-word; }
    .user-msg .msg-content { background: var(--user-msg); color: #fff; border-radius: 18px 18px 4px 18px; }
    .ai-msg .msg-content { background: transparent; color: var(--text); padding-left: 0; }
    .msg-actions { display: flex; gap: 15px; margin-top: 5px; opacity: 0.6; font-size: 12px; }

    /* --- INPUT BAR (LOCKED BOTTOM) --- */
    .input-wrapper {
        background: #000; border-top: 1px solid var(--border); padding: 10px 15px;
        padding-bottom: max(10px, env(safe-area-inset-bottom)); flex-shrink: 0; z-index: 100;
    }
    .input-wrapper.hidden { display: none; }
    .chat-bar {
        background: var(--card); border: 1px solid var(--border); border-radius: 24px;
        padding: 8px 12px; display: flex; align-items: flex-end; gap: 10px;
    }
    textarea#msg-input { 
        background: transparent; border: none; padding: 10px 0; max-height: 120px; 
        resize: none; height: 24px; width: 100%; color: #fff; font-size: 16px;
    }

    /* --- UTILS --- */
    #sidebar { position: fixed; inset: 0; background: #000; z-index: 6000; transform: translateX(-100%); transition: transform 0.3s ease; display: flex; flex-direction: column; }
    #sidebar.open { transform: translateX(0); }
    .settings-page { background: #000; position: fixed; inset: 0; z-index: 5500; display: flex; flex-direction: column; }
    
    /* Loading Bar for RAG */
    .rag-status { font-size: 12px; color: #00d2ff; margin-bottom: 5px; display: none; }
    </style>
</head>
# ==========================================
# 👇 PART 3: HTML & JAVASCRIPT 👇
# ==========================================
<body>
    <div class="global-bg" id="bg-anim">
        <div class="blob b1"></div><div class="blob b2"></div>
    </div>

    <div id="page-welcome" class="overlay">
        <div class="glass-box" style="text-align: center;">
            <div class="title-lg">Student's AI</div>
            <div class="subtitle">Your ultimate AI companion with RAG capabilities.</div>
            <button class="btn-primary" onclick="navTo('name')">Get Started</button>
        </div>
    </div>

    <div id="page-name" class="overlay hidden">
        <div class="glass-box">
            <div class="title-lg" style="font-size: 24px;">Who are you?</div>
            <div><label>Name</label><input type="search" id="inp-name" autocomplete="off"></div>
            <button class="btn-primary" onclick="saveName()">Next</button>
        </div>
    </div>

    <div id="page-details" class="overlay hidden">
        <div class="glass-box">
            <div class="title-lg" style="font-size: 24px;">Details</div>
            <label>Education Level</label>
            <select id="inp-level" onchange="toggleSem()"><option>School</option><option>College</option></select>
            <label>Class / Year</label><input type="search" id="inp-year">
            <div id="sem-box" style="display:none;"><label>Semester</label><input type="search" id="inp-sem"></div>
            <label>Subject</label><input type="search" id="inp-subj">
            <button class="btn-primary" onclick="finishSetup()">Start Learning</button>
        </div>
    </div>

    <header id="app-header" class="hidden">
        <button class="icon-btn" onclick="toggleSidebar(true)"><i class="fas fa-bars"></i></button>
        <div class="header-info">
            <span class="student-name" id="display-name">Student</span>
            <span class="status-text">Ready to master</span>
        </div>
        <div style="width: 40px;"></div>
    </header>

    <div id="chat-box"></div>

    <div class="input-wrapper hidden" id="app-input">
        <div id="rag-status" class="rag-status"><i class="fas fa-spinner fa-spin"></i> Processing Document...</div>
        <div class="chat-bar">
            <button class="icon-btn" style="border:none;" onclick="document.getElementById('file-upload').click()"><i class="fas fa-paperclip"></i></button>
            <input type="file" id="file-upload" hidden accept="image/*, application/pdf" onchange="handleFile(this)">
            
            <textarea id="msg-input" placeholder="Message..." rows="1" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
            <button class="icon-btn" style="background:#fff; color:#000; border:none;" onclick="sendMessage()"><i class="fas fa-arrow-up"></i></button>
        </div>
    </div>

    <div id="sidebar">
        <div style="padding:20px; display:flex; justify-content:space-between;">
            <span style="color:#fff; font-weight:bold;">Menu</span>
            <i class="fas fa-times" style="color:#fff; cursor:pointer;" onclick="toggleSidebar(false)"></i>
        </div>
        <div style="padding:15px;"><button class="btn-primary" onclick="newChat()">+ New Chat</button></div>
        <div id="history-container" style="flex:1; overflow-y:auto; padding:15px;"></div>
        <div style="padding:20px; border-top:1px solid #333; color:#aaa;" onclick="document.getElementById('page-settings').classList.remove('hidden')"><i class="fas fa-cog"></i> Settings</div>
    </div>

    <div id="page-settings" class="settings-page hidden">
        <div style="padding:15px; border-bottom:1px solid #333;">
            <i class="fas fa-arrow-left" style="color:#fff; cursor:pointer;" onclick="this.closest('.settings-page').classList.add('hidden')"></i>
            <span style="color:#fff; margin-left:15px; font-weight:bold;">Settings</span>
        </div>
        <div style="padding:20px;">
            <button class="btn-primary" style="background:#ef4444; color:#fff;" onclick="handleLogout()">Log Out</button>
        </div>
    </div>

    <script>
        let currentUser = null, currentChatId = null, userContext = "";
        let currentFile = null, isPDF = false;

        function checkLogin() {
            const u = localStorage.getItem("sai_user");
            if(u) {
                currentUser = u; userContext = localStorage.getItem("sai_context") || "";
                document.getElementById('display-name').innerText = u;
                showAppMode();
            } else {
                showLoginMode();
            }
        }

        function showLoginMode() {
            document.getElementById('bg-anim').style.display = 'block';
            document.getElementById('app-header').classList.add('hidden');
            document.getElementById('app-input').classList.add('hidden');
            navTo('welcome');
        }

        function showAppMode() {
            document.getElementById('bg-anim').style.display = 'none';
            document.querySelectorAll('.overlay').forEach(el => el.classList.add('hidden'));
            document.getElementById('app-header').classList.remove('hidden');
            document.getElementById('app-input').classList.remove('hidden');
            loadHistory();
            if(!currentChatId) newChat();
        }

        function navTo(id) {
            document.querySelectorAll('.overlay').forEach(el => el.classList.add('hidden'));
            document.getElementById('page-'+id).classList.remove('hidden');
        }

        function saveName() { currentUser = document.getElementById('inp-name').value; navTo('details'); }
        function toggleSem() { document.getElementById('sem-box').style.display = document.getElementById('inp-level').value === 'College' ? 'block' : 'none'; }
        
        function finishSetup() {
            userContext = `${document.getElementById('inp-level').value}, ${document.getElementById('inp-year').value}, ${document.getElementById('inp-subj').value}`;
            localStorage.setItem("sai_user", currentUser);
            localStorage.setItem("sai_context", userContext);
            showAppMode();
        }

        function handleLogout() {
            localStorage.clear();
            document.getElementById('inp-name').value = "";
            document.getElementById('chat-box').innerHTML = "";
            location.reload();
        }

        // --- RAG FILE HANDLING ---
        async function handleFile(input) {
            if(input.files[0]) {
                const file = input.files[0];
                
                // If PDF -> Upload for RAG
                if(file.type === "application/pdf") {
                    document.getElementById('rag-status').style.display = 'block';
                    const formData = new FormData();
                    formData.append('file', file);
                    
                    const res = await fetch('/upload_pdf', { method: 'POST', body: formData });
                    const data = await res.json();
                    
                    document.getElementById('rag-status').style.display = 'none';
                    if(data.status === 'success') {
                        addMsg('ai', "📄 PDF Uploaded! I have read it. Ask me anything about it.");
                    } else {
                        alert("PDF Error: " + data.message);
                    }
                } 
                // If Image -> Keep for Gemini Vision
                else {
                    const r = new FileReader();
                    r.onload = (e) => { currentFile = e.target.result; isPDF = false; alert("Image attached!"); }
                    r.readAsDataURL(file);
                }
            }
        }

        async function sendMessage() {
            const txt = document.getElementById('msg-input').value.trim();
            if(!txt && !currentFile) return;

            addMsg('user', txt, currentFile);
            document.getElementById('msg-input').value = "";
            let fileData = currentFile; currentFile = null;

            // Send to Backend
            if(!currentChatId) {
                const r = await fetch('/new_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
                const d = await r.json(); currentChatId = d.chat_id;
            }

            const res = await fetch('/chat', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                    message: txt, image: fileData, 
                    username: currentUser, chat_id: currentChatId, 
                    user_context: userContext
                })
            });
            const data = await res.json();
            addMsg('ai', data.response);
        }

        function addMsg(role, text, img=null) {
            const box = document.getElementById('chat-box');
            let content = role === 'ai' ? marked.parse(text) : text;
            let imgHtml = img ? `<img src="${img}" style="max-width:200px; border-radius:10px; display:block; margin-bottom:5px;">` : "";
            
            box.insertAdjacentHTML('beforeend', 
                `<div class="msg ${role}-msg"><div class="msg-content">${imgHtml}${content}</div></div>`
            );
            box.scrollTo(0, box.scrollHeight);
        }

        // Sidebar & History logic (Standard)
        function toggleSidebar(open) { document.getElementById('sidebar').style.transform = open ? 'translateX(0)' : 'translateX(-100%)'; }
        async function newChat() { currentChatId = null; document.getElementById('chat-box').innerHTML = ""; toggleSidebar(false); }
        async function loadHistory() {
            const res = await fetch('/get_history', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser})});
            const data = await res.json();
            const list = document.getElementById('history-container'); list.innerHTML = "";
            Object.keys(data.chats).reverse().forEach(cid => {
                list.innerHTML += `<div style="padding:10px; color:#aaa;" onclick="loadChat('${cid}')">${data.chats[cid].title || 'Chat'}</div>`;
            });
        }
        async function loadChat(cid) {
            currentChatId = cid; toggleSidebar(false);
            const res = await fetch('/get_chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:currentUser, chat_id:cid})});
            const data = await res.json();
            document.getElementById('chat-box').innerHTML = "";
            data.messages.forEach(m => addMsg(m.role==='user'?'user':'ai', m.content));
        }

        checkLogin();
    </script>
</body>
</html>
"""
# ==========================================
# 👇 PART 4: NEW ROUTES FOR PDF & CHAT 👇
# ==========================================

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"})
        
    if file:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        
        # Trigger RAG Phase 1-4
        success, msg = process_document_rag(file_path)
        
        if success:
            return jsonify({"status": "success", "message": msg})
        else:
            return jsonify({"status": "error", "message": msg})

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
    
    # Check RAG
    rag_context = query_rag(msg)
    
    user_db[u][cid]["messages"].append({"role": "user", "content": msg})
    
    # Generate Response (With RAG Context if available)
    reply = generate_with_retry(msg, img, user_db[u][cid]["messages"][:-1], ctx, rag_context)
    
    user_db[u][cid]["messages"].append({"role": "model", "content": reply})
    
    new_title = False
    if len(user_db[u][cid]["messages"]) <= 2:
        user_db[u][cid]["title"] = " ".join(msg.split()[:4])
        new_title = True
    save_db(user_db)
    return jsonify({"response": reply, "new_title": new_title})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)