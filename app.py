import os
import uuid
import time
import markdown
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

# ==========================================
# 👇 API KEYS (Hugging Face Secrets vazhiya edukiradhu) 👇
# ==========================================
# Secrets la 'API_KEYS' nu irukura variable ah eduthu, comma vachu pirikudhu
api_keys_str = os.getenv("API_KEYS", "") 
API_KEYS = [k.strip() for k in api_keys_str.split(",") if k.strip()]

# Backup: Oruvelai Secrets set pannalana, error varama irukka dummy list (Work aagadhu)
if not API_KEYS:
    print("⚠️ Warning: API_KEYS not found in Secrets! Please add them.")
    API_KEYS = [] 
# ==========================================

current_key_index = 0
app = Flask(__name__)
user_db = {} 

# --- 🧠 PERMANENT MEMORY ---
SYSTEM_INSTRUCTION = """
You are 'Student's AI', a smart coding assistant.
CRITICAL RULES (NEVER FORGET):
1. BLACK BOX ONLY: All code MUST be inside Markdown code blocks (```python ... ```).
2. NO TRUNCATION: Never shorten the code. Split into 'Part 1' & 'Part 2' if needed.
3. LANGUAGE: Explain simply in Tanglish (Tamil + English).
4. INDENTATION: Ensure Python code has perfect indentation.
5. EDITABLE: Always provide code that fits the Black Box UI.
"""

def generate_with_retry(prompt, history=[]):
    global current_key_index
    if not API_KEYS: return "⚠️ **Error:** No API Keys found. Please add 'API_KEYS' in Hugging Face Secrets."
    
    for attempt in range(len(API_KEYS) * 2):
        key = API_KEYS[current_key_index]
        try:
            genai.configure(api_key=key.strip())
            model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_INSTRUCTION)
            chat = model.start_chat(history=history)
            response = chat.send_message(prompt)
            return response.text
        except Exception as e:
            print(f"⚠️ Key #{current_key_index+1} Busy: {e}")
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            if "429" in str(e): time.sleep(1)
            continue
    return "⚠️ **System Busy:** All API keys are overloaded. Please wait 1 minute."

def save_db(db): pass 

# --- ROUTES ---
@app.route("/", methods=["GET"])
def home(): return render_template_string(HTML_TEMPLATE)

@app.route("/new_chat", methods=["POST"])
def new_chat():
    u = request.json.get("username")
    if u not in user_db: user_db[u] = {}
    nid = str(uuid.uuid4())
    user_db[u][nid] = {"title": "New Chat", "messages": []}
    return jsonify({"chat_id": nid})

@app.route("/rename_chat", methods=["POST"])
def rename_chat():
    d = request.json
    u, cid, t = d.get("username"), d.get("chat_id"), d.get("title")
    if u in user_db and cid in user_db[u]: user_db[u][cid]["title"] = t
    return jsonify({"status":"ok"})

@app.route("/delete_chat", methods=["POST"])
def delete_chat():
    d = request.json
    u, cid = d.get("username"), d.get("chat_id")
    if u in user_db and cid in user_db[u]: del user_db[u][cid]
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
    if u not in user_db: user_db[u] = {}
    if cid not in user_db[u]: user_db[u][cid] = {"messages": []}
    user_db[u][cid]["messages"].append({"role": "user", "content": msg})
    
    history = [{'role': 'user' if m['role'] == 'user' else 'model', 'parts': [m['content']]} for m in user_db[u][cid]['messages'][:-1]]
    final_prompt = f"User Context: {ctx}\nQuestion: {msg}" if ctx else msg
    reply = generate_with_retry(final_prompt, history)
    
    user_db[u][cid]["messages"].append({"role": "model", "content": reply})
    new_title = False
    if len(user_db[u][cid]["messages"]) <= 2:
        user_db[u][cid]["title"] = " ".join(msg.split()[:4])
        new_title = True
    return jsonify({"response": reply, "new_title": new_title})
    # --- UI TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Student's AI</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root { --bg: #000; --sidebar: #0a0a0a; --header: rgba(0,0,0,0.95); --user-bg: #222; --text: #ececec; --accent: #fff; --dim: #888; --border: #333; --card: #111; }
        [data-theme="light"] { --bg: #f5f5f5; --sidebar: #fff; --header: rgba(255,255,255,0.95); --user-bg: #e0e0e0; --text: #000; --accent: #000; --dim: #666; --border: #ddd; --card: #fff; }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body, html { margin: 0; padding: 0; height: 100%; width: 100%; background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; overflow: hidden; }

        .overlay { position: fixed; inset: 0; z-index: 2000; background: var(--bg); display: flex; flex-direction: column; align-items: center; overflow-y: auto; }
        .hidden { display: none !important; }
        .data-box { width: 90%; max-width: 350px; background: var(--card); border: 1px solid var(--border); border-radius: 20px; padding: 25px; display: flex; flex-direction: column; gap: 15px; margin-bottom: 50px; flex-shrink: 0; }
        
        .top-bar-full { width: 100%; background: var(--bg); padding: 15px 20px; display: flex; align-items: center; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
        .search-container { position: relative; width: 100%; }
        .search-input { width: 100%; padding: 12px 40px 12px 15px; background: var(--card); border: 1px solid var(--border); border-radius: 10px; color: var(--text); outline: none; font-size: 16px; }
        .search-clear { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: var(--dim); cursor: pointer; display: none; padding: 5px; }

        .profile-avatar { width: 90px; height: 90px; background: #222; border-radius: 50%; margin: 0 auto 10px auto; position: relative; display: flex; justify-content: center; align-items: center; border: 2px solid var(--border); }
        .form-label { font-size: 13px; color: var(--dim); margin-bottom: -10px; font-weight: 600; margin-left: 5px; }
        .welcome-container { padding: 40px; text-align: left; margin-top: auto; margin-bottom: auto; width: 100%; max-width: 500px; padding-left: 50px; } /* Added Padding */
        
        header { position: fixed; top: 0; left: 0; width: 100%; height: 60px; padding: 0 20px; background: var(--header); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; z-index: 100; backdrop-filter: blur(10px); }
        #chat-box { flex: 1; overflow-y: auto; padding: 80px 20px 80px 20px; display: flex; flex-direction: column; gap: 20px; width: 100%; max-width: 800px; margin: 0 auto; }
        
        .msg { display: flex; flex-direction: column; width: 100%; position: relative; }
        .user-msg { align-items: flex-end; }
        .user-msg .user-content { background: var(--user-bg); padding: 12px 18px; border-radius: 18px 18px 4px 18px; max-width: 85%; color: var(--text); font-size: 16px; }
        .ai-msg { align-items: flex-start; }
        .ai-content { width: 100%; font-size: 16px; line-height: 1.6; color: var(--text); }
        
        pre { background: #101010; border: 1px solid #333; border-radius: 8px; padding: 15px; overflow-x: auto; margin: 10px 0; font-family: 'JetBrains Mono', monospace; }
        code { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #a5d6ff; }
        
        .input-wrapper { position: fixed; bottom: 0; left: 0; width: 100%; background: var(--bg); border-top: 1px solid var(--border); padding: 10px 15px; z-index: 101; }
        .input-bar { width: 100%; max-width: 800px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 25px; padding: 8px 8px 8px 20px; display: flex; align-items: center; gap: 10px; }
        textarea { flex: 1; background: transparent; border: none; color: var(--text); font-size: 16px; max-height: 120px; padding: 0; resize: none; outline: none; font-family: 'Outfit', sans-serif; }
        
        .submit-btn { width: 100%; padding: 15px; background: var(--accent); color: var(--bg); border: none; border-radius: 12px; font-weight: 700; cursor: pointer; font-size: 16px; margin-top: 10px; }
        .icon-btn { background: none; border: none; color: var(--text); font-size: 18px; cursor: pointer; padding: 5px; }
        .action-icon { font-size: 12px; color: var(--dim); margin-left: 10px; cursor: pointer; opacity: 0.7; }
        .msg-actions { display: flex; justify-content: flex-end; margin-top: 5px; padding-right: 5px; }

        #sidebar { position: fixed; inset: 0; width: 280px; background: var(--sidebar); border-right: 1px solid var(--border); transform: translateX(-100%); transition: 0.3s; z-index: 2001; padding: 20px; display: flex; flex-direction: column; }
        #sidebar.open { transform: translateX(0); }
        .overlay-bg { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 2000; display: none; }
        .overlay-bg.active { display: block; }
        select, input { background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 12px; border-radius: 8px; width: 100%; outline: none; margin-top: 5px; }
        #custom-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 3000; display: none; align-items: center; justify-content: center; }
        .modal-box { background: var(--card); padding: 25px; border-radius: 15px; width: 90%; max-width: 320px; border: 1px solid var(--border); text-align: center; }
    </style>
</head>
<body>
    <div id="custom-modal"><div class="modal-box"><h3 id="modal-title" style="margin-bottom:15px;">Alert</h3><input type="text" id="modal-input" style="display:none; margin-bottom:15px;" placeholder="Type here..."><div style="display:flex; gap:10px;"><button class="submit-btn" style="background:var(--dim); flex:1;" onclick="closeModal()">Cancel</button><button class="submit-btn" style="flex:1;" id="modal-confirm-btn">OK</button></div></div></div>
    <div id="welcome-overlay" class="overlay"><div class="welcome-container"><h1 class="welcome-title" style="font-size:48px; margin-bottom:20px;">Student's AI</h1><p style="color:var(--dim); font-size:18px; line-height:1.6; margin-bottom:30px;">Your smart academic companion.</p><button class="submit-btn" style="width:auto; padding:15px 40px;" onclick="showNameBox()">Get Started <i class="fas fa-arrow-right"></i></button></div></div>
    <div id="name-overlay" class="overlay hidden" style="justify-content:center;"><div class="data-box"><h2>Who are you?</h2><input type="text" id="username-input" placeholder="Enter Name"><button class="submit-btn" onclick="handleNameSubmit()">Next</button></div></div>
    <div id="details-overlay" class="overlay hidden" style="justify-content:center;"><div class="data-box" style="margin-top:auto; margin-bottom:auto;"><h2>Student Details</h2><span class="form-label">Name</span><div id="disp-user-name" style="padding:10px; color:var(--accent);"></div><span class="form-label">Level</span><select id="edu-level" onchange="updateEduOptions()"><option value="" disabled selected>Select</option><option value="school">School</option><option value="college">College</option></select><span class="form-label" id="lbl-year">Year/Class</span><select id="edu-year" onchange="updateSem()"><option value="" disabled selected>Select</option></select><div id="sem-box" style="display:none; flex-direction:column;"><span class="form-label">Semester</span><select id="edu-sem"><option value="" disabled selected>Select</option></select></div><span class="form-label">Subject</span><input type="text" id="edu-subj" placeholder="Ex: Maths"><button class="submit-btn" onclick="handleDetailsSubmit()">Start</button></div></div>

    <div id="settings-overlay" class="overlay hidden">
        <div class="top-bar-full" style="padding:10px 15px;">
            <div class="search-container">
                <input type="text" id="setting-search" class="search-input" placeholder="Search settings..." oninput="toggleSearchClear(this)">
                <i class="fas fa-times search-clear" id="search-clear-btn" onclick="clearSearch()"></i>
            </div>
            <div onclick="closeSettings()" style="font-size:24px; padding-left:15px; cursor:pointer;">&times;</div>
        </div>
        <div style="width:100%; max-width:400px; padding:20px;">
            <div onclick="openProfile()" style="display:flex; justify-content:space-between; padding:15px; background:var(--card); border-radius:12px; cursor:pointer; align-items:center;"><span>Student Profile</span><i class="fas fa-chevron-right" style="font-size:12px;"></i></div>
            <hr style="border:0; border-top:1px solid var(--border); margin:20px 0;">
            <span class="form-label" style="margin-left:0;">THEME</span>
            <div style="display:flex; gap:10px; margin-top:10px;">
                <button class="icon-btn" onclick="setTheme('light')" style="border:1px solid var(--border); flex:1; border-radius:8px;"><i class="fas fa-sun"></i></button>
                <button class="icon-btn" onclick="setTheme('dark')" style="border:1px solid var(--border); flex:1; border-radius:8px;"><i class="fas fa-moon"></i></button>
                <button class="icon-btn" onclick="setTheme('system')" style="border:1px solid var(--border); flex:1; border-radius:8px;"><i class="fas fa-desktop"></i></button>
            </div>
        </div>
    </div>

    <div id="profile-overlay" class="overlay hidden">
        <div class="top-bar-full"><div onclick="backToSettings()" style="cursor:pointer; display:flex; align-items:center; gap:10px;"><i class="fas fa-arrow-left"></i> Back</div></div>
        <div class="data-box" style="margin-top:20px; border:none; background:transparent;">
            <div class="profile-avatar"><img id="p-pic-disp" style="width:100%; height:100%; object-fit:cover; display:none; border-radius:50%;"><i class="fas fa-user" id="p-icon-disp" style="font-size:30px; color:#fff; position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);"></i><label for="p-upload" style="position:absolute; bottom:0; right:-5px; background:var(--text); width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; cursor:pointer;"><i class="fas fa-camera" style="font-size:12px; color:var(--bg);"></i></label></div><input type="file" id="p-upload" hidden onchange="handlePic(this)">
            <span class="form-label">Name</span><div id="p-name" style="padding:10px; background:var(--bg); border-radius:8px;">--</div>
            <span class="form-label">Level</span><div id="p-level" style="padding:10px; background:var(--bg); border-radius:8px;">--</div>
            <span class="form-label">Year/Class</span><div id="p-year" style="padding:10px; background:var(--bg); border-radius:8px;">--</div>
            <div id="p-sem-row" style="display:none; flex-direction:column;"><span class="form-label">Semester</span><div id="p-sem" style="padding:10px; background:var(--bg); border-radius:8px;">--</div></div>
            <button class="submit-btn" style="background:#ef4444; color:#fff; margin-top:20px;" onclick="handleLogout()">Log Out</button>
            <div style="height:50px;"></div>
        </div>
    </div>
"""
# --- JAVASCRIPT ---
    HTML_TEMPLATE += """
    <div class="overlay-bg" id="overlay-bg" onclick="toggleSidebar()"></div>
    <div id="sidebar">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div style="display:flex; align-items:center; gap:10px; font-weight:700;"><img id="sb-pic" style="width:30px; height:30px; border-radius:50%; display:none; object-fit:cover;"><span>Hi <span id="disp-name">User</span></span></div>
            <div onclick="toggleSidebar()" style="cursor:pointer; font-size:20px;">&times;</div>
        </div>
        <button class="submit-btn" style="margin:0 0 20px 0; padding:10px;" onclick="newChat()">+ New Chat</button>
        <div style="font-size:12px; font-weight:700; color:var(--dim); margin-bottom:10px;">HISTORY</div>
        <div id="history-list" style="flex:1; overflow-y:auto;"></div>
        <div style="padding-top:20px; border-top:1px solid var(--border); cursor:pointer;" onclick="openSettings()"><i class="fas fa-cog"></i> Settings</div>
    </div>

    <header><div onclick="toggleSidebar()" style="cursor:pointer; padding:10px;"><i class="fas fa-bars"></i></div><span style="font-weight:700; font-size:18px;">Student's AI</span><div style="width:40px;"></div></header>
    <div id="chat-box"></div>
    <div class="input-wrapper"><div class="input-bar"><textarea id="input" placeholder="Type..." rows="1" oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea><button class="icon-btn" onclick="send()" style="background:var(--accent); color:var(--bg); border-radius:50%; width:35px; height:35px; display:flex; align-items:center; justify-content:center;"><i class="fas fa-arrow-up"></i></button></div></div>

    <script>
        let currUser=null, currChat=null, context="";
        function checkLogin(){
            const t=localStorage.getItem("theme"); if(t) setTheme(t);
            const u=localStorage.getItem("user"); const c=localStorage.getItem("context");
            if(u){ currUser=u; document.getElementById('welcome-overlay').style.display='none'; 
                if(c){ context=c; showApp(); } else { document.getElementById('details-overlay').classList.remove('hidden'); document.getElementById('disp-user-name').innerText=u; }
            }
        }
        function showNameBox(){document.getElementById('welcome-overlay').style.display='none'; document.getElementById('name-overlay').classList.remove('hidden');}
        function handleNameSubmit(){const n=document.getElementById('username-input').value.trim(); if(n){localStorage.setItem("user",n); currUser=n; document.getElementById('name-overlay').style.display='none'; document.getElementById('details-overlay').classList.remove('hidden'); document.getElementById('disp-user-name').innerText=n;}}
        function updateEduOptions(){const l=document.getElementById('edu-level').value; const y=document.getElementById('edu-year'); const s=document.getElementById('sem-box'); const lbl=document.getElementById('lbl-year'); y.innerHTML='<option value="" disabled selected>Select</option>'; if(l==='college'){ lbl.innerText="Year"; s.style.display='flex'; ["1st Year","2nd Year","3rd Year","4th Year"].forEach(o=>y.innerHTML+=`<option value="${o}">${o}</option>`); } else { lbl.innerText="Standard"; s.style.display='none'; ["6th","7th","8th","9th","10th","11th","12th"].forEach(o=>y.innerHTML+=`<option value="${o}">${o}</option>`); }}
        function updateSem(){const l=document.getElementById('edu-level').value; const y=document.getElementById('edu-year').value; const sm=document.getElementById('edu-sem'); if(l!=='college')return; sm.innerHTML='<option value="" disabled selected>Select</option>'; let sems=[]; if(y==="1st Year")sems=["Sem 1","Sem 2"]; else if(y==="2nd Year")sems=["Sem 3","Sem 4"]; else if(y==="3rd Year")sems=["Sem 5","Sem 6"]; else sems=["Sem 7","Sem 8"]; sems.forEach(s=>sm.innerHTML+=`<option value="${s}">${s}</option>`);}
        function handleDetailsSubmit(){const l=document.getElementById('edu-level').value, y=document.getElementById('edu-year').value, sub=document.getElementById('edu-subj').value; let sem=""; if(l==='college') sem=document.getElementById('edu-sem').value; if(!l||!y||!sub||(l==='college'&&!sem)) return alert("Fill all fields"); context = l==='college' ? `${l}, ${y}, ${sem}, ${sub}` : `${l}, ${y}, ${sub}`; localStorage.setItem("context", context); document.getElementById('details-overlay').style.display='none'; showApp();}
        function showApp(){document.getElementById('disp-name').innerText=currUser; loadHistory(); updatePic(); if(!currChat) document.getElementById('chat-box').innerHTML=`<div class="msg ai-msg"><div class="ai-content">Hi ${currUser}! Ready to help.</div></div>`;}
        
        function openSettings(){document.getElementById('settings-overlay').classList.remove('hidden'); document.getElementById('sidebar').classList.remove('open'); document.getElementById('overlay-bg').classList.remove('active'); clearSearch();}
        function closeSettings(){document.getElementById('settings-overlay').classList.add('hidden');}
        function openProfile(){closeSettings(); const p=document.getElementById('profile-overlay'); p.classList.remove('hidden'); document.getElementById('p-name').innerText=currUser; const c=context.split(','); document.getElementById('p-level').innerText=c[0]; document.getElementById('p-year').innerText=c[1]; if(c[0]==='college'){document.getElementById('p-sem-row').style.display='flex'; document.getElementById('p-sem').innerText=c[2];} updatePic();}
        function backToSettings(){document.getElementById('profile-overlay').classList.add('hidden'); openSettings();}
        function toggleSearchClear(el){document.getElementById('search-clear-btn').style.display=el.value?'block':'none';}
        function clearSearch(){document.getElementById('setting-search').value=''; document.getElementById('search-clear-btn').style.display='none';}
        function handlePic(inp){if(inp.files[0]){const r=new FileReader(); r.onload=(e)=>{localStorage.setItem("pic",e.target.result); updatePic();}; r.readAsDataURL(inp.files[0]);}}
        function updatePic(){const p=localStorage.getItem("pic"); if(p){['p-pic-disp','sb-pic'].forEach(id=>{const el=document.getElementById(id); el.src=p; el.style.display='block';}); document.getElementById('p-icon-disp').style.display='none';}}
        function setTheme(t){localStorage.setItem("theme",t); if(t==='light')document.documentElement.setAttribute('data-theme','light'); else document.documentElement.removeAttribute('data-theme');}
        function handleLogout(){localStorage.clear(); location.reload();}

        function toggleSidebar(){document.getElementById('sidebar').classList.toggle('open'); document.getElementById('overlay-bg').classList.toggle('active');}
        async function send(){
            const inp=document.getElementById('input'); const txt=inp.value.trim(); if(!txt)return;
            if(!currChat) await newChat(true);
            const box=document.getElementById('chat-box');
            box.insertAdjacentHTML('beforeend',`<div class="msg user-msg"><div class="user-content">${txt}</div><div class="msg-actions"><i class="fas fa-pen action-icon" onclick="document.getElementById('input').value='${txt}';document.getElementById('input').focus()"></i><i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText('${txt}')"></i></div></div>`);
            inp.value=''; box.scrollTo(0,box.scrollHeight);
            const tid="ai-"+Date.now(); box.insertAdjacentHTML('beforeend',`<div id="${tid}" class="msg ai-msg"><div class="ai-content">...</div></div>`);
            try{
                const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt,username:currUser,chat_id:currChat,user_context:context})});
                const d=await r.json(); const div=document.getElementById(tid); div.innerHTML=`<div class="ai-content">${marked.parse(d.response)}</div><div class="msg-actions"><i class="fas fa-copy action-icon" onclick="navigator.clipboard.writeText(this.closest('.ai-msg').innerText)"></i></div>`;
                if(d.new_title) loadHistory();
            }catch(e){document.getElementById(tid).innerHTML="Error";}
        }

        async function loadHistory(){
            const r=await fetch('/get_history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currUser})});
            const d=await r.json(); const l=document.getElementById('history-list'); l.innerHTML="";
            Object.keys(d.chats).reverse().forEach(cid=>{
                l.innerHTML+=`<div id="h-${cid}" style="padding:10px; display:flex; justify-content:space-between; cursor:pointer;" onclick="loadChat('${cid}')"><span>${d.chats[cid].title}</span><div><i class="fas fa-pen action-icon" onclick="event.stopPropagation(); renameChat('${cid}')"></i><i class="fas fa-trash action-icon" onclick="event.stopPropagation(); deleteChat('${cid}')"></i></div></div>`;
            });
        }
        async function loadChat(cid){
            currChat=cid; const r=await fetch('/get_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currUser,chat_id:cid})});
            const d=await r.json(); const box=document.getElementById('chat-box'); box.innerHTML="";
            d.messages.forEach(m=>{
                const cls=m.role==='user'?'user':'ai'; const c=m.role==='user'?m.content:marked.parse(m.content);
                const act=cls==='user'?`<div class="msg-actions"><i class="fas fa-pen action-icon" onclick="document.getElementById('input').value='${m.content}';document.getElementById('input').focus()"></i></div>`:'';
                box.insertAdjacentHTML('beforeend',`<div class="msg ${cls}-msg"><div class="${cls}-content">${c}</div>${act}</div>`);
            });
            toggleSidebar(); box.scrollTo(0,box.scrollHeight);
        }
        async function newChat(s=false){const r=await fetch('/new_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currUser})}); const d=await r.json(); currChat=d.chat_id; if(!s){document.getElementById('chat-box').innerHTML=''; loadHistory(); toggleSidebar();}}
        
        function showModal(t,cb){document.getElementById('custom-modal').style.display='flex';document.getElementById('modal-title').innerText=t;document.getElementById('modal-confirm-btn').onclick=()=>{cb();closeModal()};}
        function closeModal(){document.getElementById('custom-modal').style.display='none';}
        async function deleteChat(cid){document.getElementById('h-'+cid).remove(); await fetch('/delete_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currUser,chat_id:cid})}); if(currChat===cid) newChat();}
        async function renameChat(cid){const t=prompt("New Name:"); if(!t)return; document.querySelector(`#h-${cid} span`).innerText=t; await fetch('/rename_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currUser,chat_id:cid,title:t})});}
        
        checkLogin();
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)