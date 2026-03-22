import logging
import os
import re
import tempfile
import uuid

import redis
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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

# ---------------------------------------------------------------------------
# Security config
# ---------------------------------------------------------------------------

# 10 MB upload limit – prevents huge PDFs that generate hundreds of embed calls
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Restrict CORS to the configured frontend origin (default: localhost dev)
_allowed_origins = os.environ.get("CORS_ORIGINS", "http://localhost:8080").split(",")
CORS(app, origins=[o.strip() for o in _allowed_origins])

# Per-IP rate limiter backed by the same Redis instance
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=(
        f"redis://:{os.environ.get('REDIS_PASSWORD', '')}@"
        f"{os.environ.get('REDIS_HOST', 'localhost')}:"
        f"{os.environ.get('REDIS_PORT', 6379)}/"
        f"{os.environ.get('REDIS_DB', 0)}"
    ),
    default_limits=[],  # No global default – limits are per-route
)

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

@app.errorhandler(413)
def request_entity_too_large(e):
    """Friendly JSON response when the uploaded file exceeds MAX_CONTENT_LENGTH."""
    return jsonify({"error": "File too large. Maximum allowed size is 10 MB."}), 413


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

# Maximum allowed lengths for user-supplied text fields
_MAX_TOPIC_LEN = 300
_MAX_QUESTION_LEN = 500
# Maximum questions a single session may ask (Gemini LLM call each)
_MAX_QUESTIONS_PER_SESSION = 20
# Maximum characters of extracted PDF text to embed.
# A 10 MB text-dense PDF can produce 500 K+ chars → 500+ embedding API calls.
# Capping at 50 000 chars keeps embedding calls to ≈50 per upload.
_MAX_EXTRACTED_TEXT_LEN = 50_000


# UUID pattern used to validate session-id URL parameters.
_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def _validate_session_id(session_id: str) -> bool:
    """Return True only when session_id is a well-formed UUID v4 string."""
    return bool(_UUID_RE.match(session_id))


def _get_client_ip() -> str:
    """
    Return the real client IP.

    X-Forwarded-For is only trusted when the TRUST_PROXY environment variable
    is set to '1', i.e. when the app is deployed behind a known reverse proxy.
    Trusting it unconditionally allows trivial IP-spoofing attacks.
    """
    if os.environ.get("TRUST_PROXY") == "1":
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _ip_already_used(ip: str) -> bool:
    """Non-atomic fast check: return True if this IP has already consumed its slot."""
    return redis_client.exists(f"rate_limit:ip:{ip}") == 1


def _claim_ip_slot(ip: str) -> bool:
    """
    Atomically claim the one-time upload slot for this IP.

    Uses Redis SET NX so that two concurrent requests from the same IP cannot
    both pass the rate-limit check before either records the usage — the
    classic TOCTOU race that the old check-then-set pattern suffered from.

    This must be called AFTER input validation but BEFORE any Gemini API call
    so that:
      - A user with an invalid file can correct and retry without losing their slot.
      - A transient Gemini error does not leave the slot open for unlimited retries.

    Returns:
        True  – slot was just claimed (request is allowed to proceed).
        False – key already existed (request must be rejected).
    """
    # SET NX returns True when the key is newly written, None otherwise.
    return redis_client.set(f"rate_limit:ip:{ip}", "1", nx=True) is True


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

    # Fast non-atomic check: reject immediately if IP is already permanently blocked.
    # (The key is never deleted once set, so reading without a lock is safe here.)
    if _ip_already_used(client_ip):
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
        if len(topic) > _MAX_TOPIC_LEN:
            return jsonify({"error": f"topicToLearn must be {_MAX_TOPIC_LEN} characters or fewer"}), 400

        logger.info("upload: topic='%s', file='%s'.", topic, file.filename)

        # Save to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        # Extract text
        extracted_text = extract_text_from_pdf(temp_path)
        if not extracted_text:
            return jsonify({"error": "No text extracted from PDF"}), 400

        # Cap text length to limit embedding API calls.
        # A 10 MB all-text PDF can produce 500 K+ chars → 500+ Gemini embedding
        # calls. Truncating to _MAX_EXTRACTED_TEXT_LEN keeps costs predictable.
        if len(extracted_text) > _MAX_EXTRACTED_TEXT_LEN:
            logger.warning(
                "upload: extracted text truncated from %d to %d chars for session cost control.",
                len(extracted_text),
                _MAX_EXTRACTED_TEXT_LEN,
            )
            extracted_text = extracted_text[:_MAX_EXTRACTED_TEXT_LEN]

        # Atomically claim the IP slot just before the first Gemini call.
        # This prevents both the TOCTOU race (two concurrent requests from the
        # same IP bypassing the check above) and retry loops caused by
        # transient Gemini errors (the slot is consumed regardless of whether
        # the API call succeeds).
        if not _claim_ip_slot(client_ip):
            logger.info("upload: concurrent rate-limit collision for IP %s.", client_ip)
            return jsonify({"error": "rate_limited"}), 429

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

        return jsonify({"session_id": session_id, "sentence_count": len(sentences)}), 200

    except Exception as exc:
        logger.exception("upload: unhandled error – %s", exc)
        return jsonify({"error": "An internal error occurred. Please try again."}), 500
    finally:
        _cleanup_temp_file(temp_path)


# ---------------------------------------------------------------------------
# Per-session sentence polling
# ---------------------------------------------------------------------------

@app.route("/session/<session_id>/next", methods=["GET"])
@limiter.limit("120 per minute")
def session_next(session_id: str):
    """
    Pop and return the next sentence from the session's Redis queue.

    Returns:
        200 – {"text": "<sentence>", "done": false, "remaining": <int>}
              or {"text": null, "done": true, "remaining": 0} when empty.
        400 – Invalid session_id format.
        500 – Redis error.
    """
    if not _validate_session_id(session_id):
        return jsonify({"error": "Invalid session ID"}), 400
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
        return jsonify({"error": "An internal error occurred."}), 500


# ---------------------------------------------------------------------------
# Per-session question answering
# ---------------------------------------------------------------------------

@app.route("/session/<session_id>/question", methods=["POST"])
@limiter.limit("1 per 30 seconds")
def session_question(session_id: str):
    """
    Answer a student's question using the session's FAISS vector store and
    push the response sentences back into the session queue.

    Request body (JSON):
        {"question": "<text>"}

    Returns:
        200 – {"status": "queued", "sentence_count": <int>}
        400 – Missing question or invalid session_id format.
        404 – Session not found / expired.
        500 – Processing error.
    """
    if not _validate_session_id(session_id):
        return jsonify({"error": "Invalid session ID"}), 400
    try:
        data = request.get_json(silent=True) or {}
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "question is required"}), 400
        # Truncate oversized questions to cap token costs
        question = question[:_MAX_QUESTION_LEN]

        meta_key = f"session:{session_id}:meta"
        meta = redis_client.hgetall(meta_key)
        if not meta:
            return jsonify({"error": "Session not found or expired"}), 404

        # Enforce per-session question cap
        q_count_key = f"session:{session_id}:question_count"
        question_count = int(redis_client.get(q_count_key) or 0)
        if question_count >= _MAX_QUESTIONS_PER_SESSION:
            logger.info(
                "session_question: session '%s' hit the %d-question cap.",
                session_id, _MAX_QUESTIONS_PER_SESSION,
            )
            return jsonify({"error": "question_limit_reached"}), 429
        # Use a pipeline so INCR and EXPIRE are sent atomically.
        # If the server crashes between two separate commands the key would
        # persist forever with no TTL, permanently consuming a question slot.
        pipe = redis_client.pipeline()
        pipe.incr(q_count_key)
        pipe.expire(q_count_key, 3600)
        pipe.execute()

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
        return jsonify({"error": "An internal error occurred. Please try again."}), 500


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7700))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    logger.info("Starting Flask server on port %d (debug=%s).", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
