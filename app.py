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


def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in environment variables.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            # Messages
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Read receipts (simple: who read which message)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS message_reads (
                    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    reader_name TEXT NOT NULL,
                    read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (message_id, reader_name)
                )
            """)


# IMPORTANT for gunicorn: run on import
init_db()


def save_message(name: str, text: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (name, text)
                VALUES (%s, %s)
                RETURNING id, name, text, created_at
                """,
                (name, text),
            )
            row = cur.fetchone()
            # created_at is datetime
            return {
                "id": row["id"],
                "name": row["name"],
                "text": row["text"],
                "created_at": row["created_at"].isoformat(),
            }


def fetch_recent_messages(limit: int = 200) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, text, created_at
                FROM messages
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    rows.reverse()  # oldest -> newest
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "text": r["text"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("join")
def on_join(data):
    # Send history only to the joining client
    emit("history", fetch_recent_messages(200))


@socketio.on("chat_message")
def on_chat_message(data):
    name = (data.get("name") or "Anon").strip()
    text = (data.get("text") or "").strip()
    if not text:
        return

    msg = save_message(name, text)
    emit("chat_message", msg, broadcast=True)


@socketio.on("read")
def on_read(data):
    """
    data: { message_id: int, reader: string }
    """
    try:
        message_id = int(data.get("message_id"))
    except Exception:
        return

    reader = (data.get("reader") or "").strip()
    if not reader:
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO message_reads (message_id, reader_name)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (message_id, reader),
            )

    emit("read_update", {"message_id": message_id, "reader": reader}, broadcast=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4021"))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
