from flask import Flask, render_template 
from flask_socketio import SocketIO, emit 
from datetime import datetime 
import sqlite3 
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "chat.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            text TEXT NOT NULL,
            ts TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def now_ts():
    return datetime.now().strftime("%H:%M")


def fetch_recent_messages(limit=50):
    conn = get_db()
    rows = conn.execute("""
        SELECT name, text, ts
        FROM messages
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    # reverse so oldest -> newest
    return list(reversed([{"name": r["name"], "text": r["text"], "ts": r["ts"]} for r in rows]))


def save_message(name, text, ts):
    conn = get_db()
    conn.execute("""
        INSERT INTO messages (name, text, ts)
        VALUES (?, ?, ?)
    """, (name, text, ts))
    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("join")
def on_join(data):
    name = (data.get("name") or "Anon").strip()

    # Send history only to the joining client
    emit("history", fetch_recent_messages(50))

    # Broadcast join message to everyone
    emit("system", {"text": f"{name} joined", "ts": now_ts()}, broadcast=True)


@socketio.on("chat_message")
def on_chat_message(data):
    name = (data.get("name") or "Anon").strip()
    text = (data.get("text") or "").strip()
    if not text:
        return

    ts = now_ts()
    save_message(name, text, ts)

    # broadcast message to all clients
    emit("chat_message", {"name": name, "text": text, "ts": ts}, broadcast=True)


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
    port = int(os.environ.get("PORT", 4021))
    socketio.run(app, host="0.0.0.0", port=port)

