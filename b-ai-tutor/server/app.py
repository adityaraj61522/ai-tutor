import os
from flask import Flask, jsonify, request
import redis
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Initialize Redis connection
redis_client = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    db=int(os.environ.get("REDIS_DB", 0)),
    password=os.environ.get("REDIS_PASSWORD", None),
    decode_responses=True
)


@app.route("/", methods=["GET"])
def index():
    port = int(os.environ.get("PORT", 7700))
    return jsonify({"status": "ok", "port": port})


@app.route("/echo", methods=["POST"])
def echo():
    data = request.get_json(silent=True)
    return jsonify({"echo": data}), 200


@app.route("/queue/push", methods=["POST"])
def queue_push():
    """Push a message to the task queue"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        redis_client.rpush("task_queue", str(data))
        return jsonify({"status": "queued", "message": "Task added to queue"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/queue/pop", methods=["POST"])
def queue_pop():
    """Pop a message from the task queue"""
    try:
        item = redis_client.lpop("task_queue")
        if item:
            return jsonify({"status": "success", "item": item}), 200
        return jsonify({"status": "empty", "message": "Queue is empty"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/queue/length", methods=["GET"])
def queue_length():
    """Get the length of the task queue"""
    try:
        length = redis_client.llen("task_queue")
        return jsonify({"length": length}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7700))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host="0.0.0.0", port=port, debug=debug)
