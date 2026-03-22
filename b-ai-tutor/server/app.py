import logging
import os
import re
import tempfile
import uuid

import redis
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from pdf_extractor import extract_text_from_pdf
from vector_store import VectorStore

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------
load_dotenv()

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from the frontend

# ---------------------------------------------------------------------------
# Redis client
# ---------------------------------------------------------------------------
redis_client = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    db=int(os.environ.get("REDIS_DB", 0)),
    password=os.environ.get("REDIS_PASSWORD") or None,
    decode_responses=True,
)
logger.info(
    "Redis client configured at %s:%s (db=%s).",
    os.environ.get("REDIS_HOST", "localhost"),
    os.environ.get("REDIS_PORT", 6379),
    os.environ.get("REDIS_DB", 0),
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Return a simple health-check payload including the configured port."""
    port = int(os.environ.get("PORT", 7700))
    logger.debug("Health check requested.")
    return jsonify({"status": "ok", "port": port})


# ---------------------------------------------------------------------------
# PDF learning pipeline (upload endpoint only)
# ---------------------------------------------------------------------------

def _cleanup_temp_file(path: str) -> None:
    """Remove a temporary file if it still exists, logging any failure."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.debug("Temporary file removed: %s", path)
        except OSError as exc:
            logger.warning("Could not remove temporary file %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Sentence splitter utility
# ---------------------------------------------------------------------------

def _split_into_sentences(text: str) -> list[str]:
    """Split a block of text into individual, non-trivial sentences."""
    # Split on sentence-ending punctuation followed by whitespace
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in parts if s.strip() and len(s.strip()) > 10]


# ---------------------------------------------------------------------------
# PDF upload → session creation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# IP-based one-time rate limiter helper
# ---------------------------------------------------------------------------

def _get_client_ip() -> str:
    """Return the real client IP, respecting X-Forwarded-For if present."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _is_ip_rate_limited(ip: str) -> bool:
    """Return True if this IP has already consumed its one free upload."""
    return redis_client.exists(f"rate_limit:ip:{ip}") == 1


def _mark_ip_used(ip: str) -> None:
    """Permanently flag this IP as having used its one free upload."""
    redis_client.set(f"rate_limit:ip:{ip}", "1")


@app.route("/upload", methods=["POST"])
def upload():
    """
    Upload a PDF + topic, extract text, build a FAISS vector store,
    generate an initial teaching monologue, and populate a per-session
    Redis sentence queue.

    Each IP address is allowed exactly one successful upload (rate-limited
    permanently in Redis).

    Form fields:
        uploadedPDF  (file) – PDF document.
        topicToLearn (str)  – Topic the student wants to learn.

    Returns:
        200 – {"session_id": "<uuid>", "sentence_count": <int>}
        400 – Validation error.
        429 – IP already used its free session.
        500 – Processing error.
    """
    client_ip = _get_client_ip()

    if _is_ip_rate_limited(client_ip):
        logger.info("upload: rate-limited request from IP %s.", client_ip)
        return jsonify({"error": "rate_limited"}), 429

    temp_path = None
    try:
        if "uploadedPDF" not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400

        file = request.files["uploadedPDF"]
        topic = request.form.get("topicToLearn", "").strip()

        if not file.filename:
            return jsonify({"error": "No PDF file selected"}), 400
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "File must be a PDF"}), 400
        if not topic:
            return jsonify({"error": "topicToLearn is required"}), 400

        logger.info("upload: topic='%s', file='%s'.", topic, file.filename)

        # Save to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        # Extract text
        extracted_text = extract_text_from_pdf(temp_path)
        if not extracted_text:
            return jsonify({"error": "No text extracted from PDF"}), 400

        # Create session
        session_id = str(uuid.uuid4())
        store_path = os.path.join("faiss_store", session_id)
        api_key = os.environ.get("GOOGLE_API_KEY")

        # Build FAISS vector store
        vector_store = VectorStore(google_api_key=api_key, pickle_file=store_path)
        vector_store.create_vector_store_from_text(extracted_text)
        logger.info("upload: vector store created at '%s'.", store_path)

        # Generate an initial teaching script via RAG
        teaching_query = (
            f"You are an enthusiastic and clear AI tutor. "
            f"Explain '{topic}' in 8 to 10 engaging, complete sentences "
            f"that a student would enjoy listening to."
        )
        qa_result = vector_store.query_with_sources(teaching_query)
        answer_text = qa_result.get("answer", "")

        sentences = _split_into_sentences(answer_text)
        if not sentences:
            sentences = [answer_text.strip()]

        # Push sentences into the session queue
        queue_key = f"session:{session_id}:queue"
        for sentence in sentences:
            redis_client.rpush(queue_key, sentence)
        redis_client.expire(queue_key, 3600)

        # Store session metadata
        meta_key = f"session:{session_id}:meta"
        redis_client.hset(meta_key, mapping={
            "topic": topic,
            "store_path": store_path,
            "filename": file.filename,
        })
        redis_client.expire(meta_key, 3600)

        logger.info(
            "upload: session '%s' created with %d sentences.", session_id, len(sentences)
        )

        # Permanently record this IP so it cannot upload again
        _mark_ip_used(client_ip)

        return jsonify({"session_id": session_id, "sentence_count": len(sentences)}), 200

    except Exception as exc:
        logger.exception("upload: unhandled error – %s", exc)
        return jsonify({"error": str(exc)}), 500
    finally:
        _cleanup_temp_file(temp_path)


# ---------------------------------------------------------------------------
# Per-session sentence polling
# ---------------------------------------------------------------------------

@app.route("/session/<session_id>/next", methods=["GET"])
def session_next(session_id: str):
    """
    Pop and return the next sentence from the session's Redis queue.

    Returns:
        200 – {"text": "<sentence>", "done": false, "remaining": <int>}
              or {"text": null, "done": true, "remaining": 0} when empty.
        500 – Redis error.
    """
    try:
        queue_key = f"session:{session_id}:queue"
        sentence = redis_client.lpop(queue_key)
        if sentence:
            remaining = redis_client.llen(queue_key)
            logger.debug("session_next: '%s' → sentence (%d remaining).", session_id, remaining)
            return jsonify({"text": sentence, "done": False, "remaining": remaining}), 200

        logger.debug("session_next: '%s' → queue empty.", session_id)
        return jsonify({"text": None, "done": True, "remaining": 0}), 200

    except Exception as exc:
        logger.exception("session_next: error – %s", exc)
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Per-session question answering
# ---------------------------------------------------------------------------

@app.route("/session/<session_id>/question", methods=["POST"])
def session_question(session_id: str):
    """
    Answer a student's question using the session's FAISS vector store and
    push the response sentences back into the session queue.

    Request body (JSON):
        {"question": "<text>"}

    Returns:
        200 – {"status": "queued", "sentence_count": <int>}
        400 – Missing question.
        404 – Session not found / expired.
        500 – Processing error.
    """
    try:
        data = request.get_json(silent=True) or {}
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "question is required"}), 400

        meta_key = f"session:{session_id}:meta"
        meta = redis_client.hgetall(meta_key)
        if not meta:
            return jsonify({"error": "Session not found or expired"}), 404

        store_path = meta.get("store_path", "")
        api_key = os.environ.get("GOOGLE_API_KEY")

        # Load session vector store and answer the question
        vector_store = VectorStore(google_api_key=api_key, pickle_file=store_path)
        loaded = vector_store.load_index()
        if not loaded:
            return jsonify({"error": "Could not load session vector store"}), 500

        qa_result = vector_store.query_with_sources(question)
        answer_text = qa_result.get("answer", "")

        sentences = _split_into_sentences(answer_text)
        if not sentences:
            sentences = [answer_text.strip()]

        queue_key = f"session:{session_id}:queue"
        for sentence in sentences:
            redis_client.rpush(queue_key, sentence)
        redis_client.expire(queue_key, 3600)

        logger.info(
            "session_question: '%s' → %d sentences queued.", session_id, len(sentences)
        )
        return jsonify({"status": "queued", "sentence_count": len(sentences)}), 200

    except Exception as exc:
        logger.exception("session_question: error – %s", exc)
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7700))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    logger.info("Starting Flask server on port %d (debug=%s).", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
