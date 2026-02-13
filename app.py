# app.py  (PostgreSQL version for Render) # Requires: Flask, Flask-SocketIO, eventlet, psycopg[binary]

from flask import Flask, render_template 
from flask_socketio import SocketIO, emit 
from datetime import datetime 
import os 
import psycopg 
from psycopg.rows import dict_row

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

socketio = SocketIO(app, cors_allowed_origins="*")
DATABASE_URL = os.environ.get("DATABASE_URL")

def now_ts():
    return datetime.now().strftime("%H:%M")


def get_db():
    """
    Returns a psycopg connection with dict rows.
    DATABASE_URL must be set in Render environment variables.
    """
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it in Render (Environment -> Add Variable)."
        )
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    """
    Creates required tables if they don't exist.
    Runs at import time so it works with gunicorn (not only __main__).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )


def fetch_recent_messages(limit: int = 50):
    """
    Fetch last N messages (oldest -> newest) for history.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, text, ts
                FROM messages
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()  # list[dict]
    rows.reverse()
    return rows


def save_message(name: str, text: str, ts: str):
    """
    Save message to database.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (name, text, ts)
                VALUES (%s, %s, %s)
                """,
                (name, text, ts),
            )


# ✅ IMPORTANT: run init_db on import so gunicorn deployments create the table
init_db()


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("join")
def on_join(data):
    name = (data.get("name") or "Anon").strip()

    # Send history only to this client
    emit("history", fetch_recent_messages(50))

    # Broadcast join event
    emit("system", {"text": f"{name} joined", "ts": now_ts()}, broadcast=True)


@socketio.on("chat_message")
def on_chat_message(data):
    name = (data.get("name") or "Anon").strip()
    text = (data.get("text") or "").strip()
    if not text:
        return

    ts = now_ts()
    save_message(name, text, ts)

    emit(
        "chat_message",
        {"name": name, "text": text, "ts": ts},
        broadcast=True,
    )


@socketio.on("typing")
def on_typing(data):
    name = (data.get("name") or "Anon").strip()
    is_typing = bool(data.get("is_typing"))
    emit(
        "typing",
        {"name": name, "is_typing": is_typing},
        broadcast=True,
        include_self=False,
    )


@socketio.on("leave")
def on_leave(data):
    name = (data.get("name") or "Anon").strip()
    emit("system", {"text": f"{name} left", "ts": now_ts()}, broadcast=True)


if __name__ == "__main__":
    # Local run (Render uses gunicorn start command instead)
    port = int(os.environ.get("PORT", "4021"))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
