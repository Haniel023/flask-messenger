from flask import Flask, render_template, request
from flask_socketio import SocketIO, send

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret"
socketio = SocketIO(app, cors_allowed_origins="*")
print("App started..")

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("message")
def handle_message(msg):
    name = (msg.get("name") or "Anon").strip()
    text = (msg.get("text") or "").strip()
    if not text:
        return
    send({"name": name, "text": text}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=4021, debug=True)