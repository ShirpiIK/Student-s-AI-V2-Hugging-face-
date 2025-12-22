# ===============================
# Student's AI — FINAL VERSION
# ===============================

import os, uuid, time, json, base64, io, warnings
from PIL import Image
from flask import Flask, request, jsonify, render_template_string, Response
import google.generativeai as genai

warnings.filterwarnings("ignore")

# ---------- API KEYS ----------
keys_string = os.environ.get("API_KEYS", "")
API_KEYS = [k.strip() for k in keys_string.replace(",", " ").split() if k.strip()]

# ---------- DATABASE ----------
DB_FILE = "chat_db.json"

def load_db():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_db(db):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(db, f, indent=2)
    except:
        pass

user_db = load_db()

app = Flask(__name__)
current_key_index = 0

# ---------- MODEL ----------
def get_working_model(key):
    try:
        genai.configure(api_key=key)
        models = list(genai.list_models())
        valid = [m for m in models if "generateContent" in m.supported_generation_methods]
        for m in valid:
            if "flash" in m.name.lower():
                return m.name
        return valid[0].name if valid else None
    except:
        return None

def process_image(image_data):
    try:
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]
        return Image.open(io.BytesIO(base64.b64decode(image_data)))
    except:
        return None

def generate_with_retry(prompt, image_data=None, history_messages=[], user_context=""):
    global current_key_index
    if not API_KEYS:
        return "🚨 API Keys Missing."

    formatted_history = []
    for m in history_messages[-6:]:
        role = "user" if m["role"] == "user" else "model"
        formatted_history.append({"role": role, "parts": [m["content"]]})

    final_prompt = f"[User Context: {user_context}]\n{prompt}" if user_context else prompt
    parts = [final_prompt]

    if image_data:
        img = process_image(image_data)
        if img:
            parts.append(img)

    for _ in range(len(API_KEYS)):
        key = API_KEYS[current_key_index]
        model_name = get_working_model(key)
        if not model_name:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            continue
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            if image_data:
                res = model.generate_content(parts)
            else:
                chat = model.start_chat(history=formatted_history)
                res = chat.send_message(final_prompt)
            return res.text
        except:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            time.sleep(1)

    return "⚠️ System Busy. Try again."

# ---------- HTML ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Student's AI</title>
<link rel="manifest" href="/manifest.json">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
:root{
 --bg:#09090b;--card:#18181b;--text:#e4e4e7;--dim:#71717a;
 --border:#27272a;--input-bg:#131315;
}
[data-theme="light"]{
 --bg:#f4f4f5;--card:#fff;--text:#18181b;--border:#d4d4d8;
}
*{box-sizing:border-box}
body{
 margin:0;background:var(--bg);color:var(--text);
 height:100dvh;display:flex;flex-direction:column;overflow:hidden;
 font-family:Inter,sans-serif;
}
header{
 position:fixed;top:0;left:0;right:0;height:70px;
 background:var(--bg);border-bottom:1px solid var(--border);
 display:flex;align-items:center;justify-content:center;z-index:3000;
}
#chat-box{flex:1;padding:90px 5% 20px;overflow-y:auto}
.input-wrapper{
 position:sticky;bottom:0;background:var(--bg);
 border-top:1px solid var(--border);
 padding:15px;padding-bottom:env(safe-area-inset-bottom);
}
.input-container{
 max-width:900px;margin:auto;background:var(--card);
 border:1px solid var(--border);border-radius:24px;
 display:flex;gap:10px;padding:10px 15px;
}
textarea{flex:1;background:none;border:none;color:var(--text);resize:none;outline:none}
.data-box{
 max-width:350px;width:90%;background:var(--card);
 border:1px solid var(--border);border-radius:20px;
 padding:20px;margin-top:12vh;max-height:75vh;overflow-y:auto;
}
.input-error{
 border:1px solid #ef4444!important;
 box-shadow:0 0 0 2px rgba(239,68,68,.25);
}
.welcome-title{font-size:36px;font-weight:800}
.welcome-desc{font-size:15px;color:var(--dim);max-width:280px;margin:auto}
</style>
</head>
<body>

<header>Student's AI</header>

<div id="chat-box"></div>

<div class="input-wrapper">
  <div class="input-container">
    <textarea id="input" placeholder="Type a message..."
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send();}">
    </textarea>
    <button onclick="send()">➤</button>
  </div>
</div>

<script>
let currentUser="User",currentChatId=null,userContext="",currentAttachment=null;

/* SEARCH X + ENTER */
function toggleSearchClear(el){
 document.getElementById("search-clear-btn")?.style.display=
  el.value?"flex":"none";
}
function clearSearch(){
 const el=document.getElementById("setting-search");
 if(!el) return;
 el.value="";toggleSearchClear(el);
}

/* PROFILE ENTER SAVE */
function handleSubjectKey(e){
 if(e.key==="Enter"){e.preventDefault();saveProfileChanges();e.target.blur();}
}

/* LOGOUT FULL REFRESH */
function handleLogout(){localStorage.clear();location.reload(true);}

/* INSTANT RENAME */
async function renameChat(cid){
 const val=prompt("Rename chat");
 if(!val) return;
 const t=document.querySelector("#chat-"+cid+" .h-title");
 if(t) t.innerText=val;
 await fetch("/rename_chat",{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify({username:currentUser,chat_id:cid,title:val})});
}

/* SAVE PROFILE – NO POPUP */
function saveProfileChanges(){
 const inp=document.getElementById("p-subj-edit");
 if(!inp) return;
 const parts=userContext.split(",");
 if(parts[0]==="college") parts[3]=inp.value;
 else parts[2]=inp.value;
 userContext=parts.join(",");
 localStorage.setItem("student_ai_context",userContext);
}

async function send(){
 const txt=document.getElementById("input").value.trim();
 if(!txt) return;
 document.getElementById("input").value="";
 const box=document.getElementById("chat-box");
 box.innerHTML+=`<div><b>You:</b> ${txt}</div>`;
 const r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify({username:currentUser,chat_id:currentChatId,message:txt,user_context:userContext})});
 const d=await r.json();
 box.innerHTML+=`<div><b>AI:</b> ${d.response}</div>`;
 box.scrollTop=box.scrollHeight;
}
</script>

</body>
</html>
"""

# ---------- ROUTES ----------
@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route("/new_chat", methods=["POST"])
def new_chat():
    u = request.json["username"]
    user_db.setdefault(u, {})
    cid = str(uuid.uuid4())
    user_db[u][cid] = {"title": "New Chat", "messages": []}
    save_db(user_db)
    return jsonify({"chat_id": cid})

@app.route("/rename_chat", methods=["POST"])
def rename_chat():
    d = request.json
    if d["username"] in user_db and d["chat_id"] in user_db[d["username"]]:
        user_db[d["username"]][d["chat_id"]]["title"] = d["title"]
        save_db(user_db)
    return jsonify({"status": "ok"})

@app.route("/chat", methods=["POST"])
def chat():
    d = request.json
    u, cid, msg = d["username"], d.get("chat_id"), d["message"]
    ctx = d.get("user_context", "")
    user_db.setdefault(u, {})
    user_db[u].setdefault(cid, {"title": "Chat", "messages": []})
    user_db[u][cid]["messages"].append({"role": "user", "content": msg})
    reply = generate_with_retry(msg, None, user_db[u][cid]["messages"][:-1], ctx)
    user_db[u][cid]["messages"].append({"role": "model", "content": reply})
    save_db(user_db)
    return jsonify({"response": reply})

@app.route("/manifest.json")
def manifest():
    return Response(json.dumps({
        "name": "Student's AI",
        "short_name": "StudentAI",
        "start_url": "/",
        "display": "standalone",
        "theme_color": "#09090b"
    }), mimetype="application/json")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)