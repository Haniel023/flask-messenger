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
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS message_reads (
                    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
                    reader_name TEXT NOT NULL,
                    read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (message_id, reader_name)
                )
            """)


init_db()


def fetch_recent_messages(limit=100):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, text, created_at
                FROM messages
                ORDER BY id DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()

    rows.reverse()
    return rows


def save_message(name, text):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO messages (name, text)
                VALUES (%s, %s)
                RETURNING id
            """, (name, text))
            return cur.fetchone()["id"]


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("join")
def on_join(data):
    name = data.get("name")
    emit("history", fetch_recent_messages())


@socketio.on("chat_message")
def on_chat_message(data):
    name = data.get("name")
    text = data.get("text")

    msg_id = save_message(name, text)

    emit("chat_message", {
        "id": msg_id,
        "name": name,
        "text": text,
        "created_at": datetime.now().isoformat()
    }, broadcast=True)


@socketio.on("read")
def on_read(data):
    message_id = data.get("message_id")
    reader = data.get("reader")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO message_reads (message_id, reader_name)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (message_id, reader))

    emit("read_update", {
        "message_id": message_id,
        "reader": reader
    }, broadcast=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4021"))
    socketio.run(app, host="0.0.0.0", port=port)
