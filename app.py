from flask import Flask, render_template 
from flask_socketio import SocketIO, emit 
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    return render_template("index.html")

def now_ts():
    return datetime.now().strftime("%H:%M")

@socketio.on("join")
def on_join(data):
    name = (data.get("name") or "Anon").strip()
    emit("system", {"text": f"{name} joined", "ts": now_ts()}, broadcast=True)

@socketio.on("chat_message")
def on_chat_message(data):
    name = (data.get("name") or "Anon").strip()
    text = (data.get("text") or "").strip()
    if not text:
        return
    emit("chat_message", {"name": name, "text": text, "ts": now_ts()}, broadcast=True)

@socketio.on("typing")
def on_typing(data):
    name = (data.get("name") or "Anon").strip()
    is_typing = bool(data.get("is_typing"))
    emit("typing", {"name": name, "is_typing": is_typing}, broadcast=True, include_self=False)

@socketio.on("leave")
def on_leave(data):
    name = (data.get("name") or "Anon").strip()
    emit("system", {"text": f"{name} left", "ts": now_ts()}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=4021, debug=True)
