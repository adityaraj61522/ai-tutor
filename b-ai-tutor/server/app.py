import os
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    port = int(os.environ.get("PORT", 7700))
    return jsonify({"status": "ok", "port": port})


@app.route("/echo", methods=["POST"])
def echo():
    data = request.get_json(silent=True)
    return jsonify({"echo": data}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7700))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host="0.0.0.0", port=port, debug=debug)
