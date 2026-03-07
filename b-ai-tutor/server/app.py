"""
Flask application entry point for the AI Tutor backend.

Exposes REST endpoints for:
  - Health check (GET /)
  - Echo utility (POST /echo)
  - Redis task queue management (POST /queue/push, /queue/pop, GET /queue/length)
  - PDF learning pipeline (POST /learn)

Environment variables (see .env):
  PORT, FLASK_DEBUG, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, GOOGLE_API_KEY
"""

import logging
import os
import tempfile

import redis
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from gemini_service import get_gemini_service
from pdf_extractor import extract_pdf_metadata, extract_text_from_pdf
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
# Gemini service (non-fatal if unavailable at startup)
# ---------------------------------------------------------------------------
try:
    gemini = get_gemini_service()
    logger.info("Gemini service initialised successfully.")
except Exception as exc:
    gemini = None
    logger.warning("Could not initialise Gemini service at startup: %s", exc)

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
# Echo utility (useful for integration testing)
# ---------------------------------------------------------------------------

@app.route("/echo", methods=["POST"])
def echo():
    """Echo the received JSON body back to the caller."""
    data = request.get_json(silent=True)
    logger.debug("Echo endpoint called with data: %s", data)
    return jsonify({"echo": data}), 200


# ---------------------------------------------------------------------------
# Redis task-queue endpoints
# ---------------------------------------------------------------------------

@app.route("/queue/push", methods=["POST"])
def queue_push():
    """
    Push a message onto the Redis task queue (right-push).

    Request body (JSON):
        Any JSON-serialisable object.

    Returns:
        200 – item queued
        400 – no data provided
        500 – Redis error
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            logger.warning("queue/push called with empty body.")
            return jsonify({"error": "No data provided"}), 400

        redis_client.rpush("task_queue", str(data))
        logger.info("Task pushed to queue: %s", data)
        return jsonify({"status": "queued", "message": "Task added to queue"}), 200

    except Exception as exc:
        logger.exception("Error pushing to task queue: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/queue/pop", methods=["POST"])
def queue_pop():
    """
    Pop the oldest message from the Redis task queue (left-pop).

    Returns:
        200 – item returned, or empty-queue indicator
        500 – Redis error
    """
    try:
        item = redis_client.lpop("task_queue")
        if item:
            logger.info("Task popped from queue: %s", item)
            return jsonify({"status": "success", "item": item}), 200

        logger.debug("queue/pop called but queue is empty.")
        return jsonify({"status": "empty", "message": "Queue is empty"}), 200

    except Exception as exc:
        logger.exception("Error popping from task queue: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/queue/length", methods=["GET"])
def queue_length():
    """
    Return the current number of items in the Redis task queue.

    Returns:
        200 – {"length": <int>}
        500 – Redis error
    """
    try:
        length = redis_client.llen("task_queue")
        logger.debug("Queue length queried: %d", length)
        return jsonify({"length": length}), 200

    except Exception as exc:
        logger.exception("Error fetching queue length: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# PDF learning pipeline
# ---------------------------------------------------------------------------

def _cleanup_temp_file(path: str) -> None:
    """Remove a temporary file if it still exists, logging any failure."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.debug("Temporary file removed: %s", path)
        except OSError as exc:
            logger.warning("Could not remove temporary file %s: %s", path, exc)


@app.route("/learn", methods=["POST"])
def learn():
    """
    Full PDF-to-insight pipeline powered by Google Gemini and FAISS.

    Accepts a multipart/form-data request, extracts text from the uploaded
    PDF, builds a FAISS vector store with Gemini embeddings, and returns
    semantically similar chunks plus an LLM-generated insight for the
    requested topic.

    Form fields:
        uploadedPDF  (file)  – The PDF document to process.
        topicToLearn (str)   – The topic/subject to focus on.

    Returns:
        200 – Success payload with metadata, similar chunks, and QA result.
        400 – Validation error (missing file, bad extension, no topic, etc.).
        500 – Internal processing error.
    """
    temp_path = None

    try:
        # ---- Input validation ------------------------------------------------
        if "uploadedPDF" not in request.files:
            logger.warning("learn: no PDF file in request.")
            return jsonify({"error": "No PDF file provided"}), 400

        file = request.files["uploadedPDF"]
        topic = request.form.get("topicToLearn", "").strip()

        if not file.filename:
            logger.warning("learn: empty filename received.")
            return jsonify({"error": "No PDF file selected"}), 400

        if not file.filename.lower().endswith(".pdf"):
            logger.warning("learn: non-PDF file submitted (%s).", file.filename)
            return jsonify({"error": "File must be a PDF"}), 400

        if not topic:
            logger.warning("learn: topicToLearn is missing.")
            return jsonify({"error": "topicToLearn is required"}), 400

        logger.info("learn: processing topic='%s', file='%s'.", topic, file.filename)

        # ---- Save upload to a temp file --------------------------------------
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            file.save(tmp.name)
            temp_path = tmp.name
        logger.debug("learn: PDF saved to temp path %s.", temp_path)

        # ---- PDF text extraction ---------------------------------------------
        extracted_text = extract_text_from_pdf(temp_path)
        metadata = extract_pdf_metadata(temp_path)
        logger.info(
            "learn: extracted %d characters from PDF (%d pages).",
            len(extracted_text),
            metadata.get("total_pages", "?"),
        )

        if not extracted_text:
            return jsonify({"error": "No text extracted from PDF"}), 400

        # ---- Build FAISS vector store ----------------------------------------
        vector_store = VectorStore(
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            pickle_file="faiss_store.pkl",
        )

        success = vector_store.create_vector_store_from_text(extracted_text)
        if not success:
            logger.error("learn: vector store creation returned False.")
            return jsonify({"error": "Failed to create vector store"}), 400

        logger.info("learn: vector store created successfully.")

        # ---- Similarity search for topic chunks ------------------------------
        similar_chunks = vector_store.search_similar(topic, k=5)
        logger.debug("learn: found %d similar chunks for topic '%s'.", len(similar_chunks), topic)

        # ---- LLM insight generation ------------------------------------------
        enhanced_query = (
            f"make something interesting and insightful and exciting "
            f"for humans and in 60 words from: {topic}"
        )
        qa_result = vector_store.query_with_sources(enhanced_query)
        logger.info("learn: LLM insight generated.")

        # ---- Build and return response ---------------------------------------
        response = {
            "status": "success",
            "topic": topic,
            "metadata": metadata,
            "extracted_text_length": len(extracted_text),
            "vector_store_info": vector_store.get_index_info(),
            "similar_chunks": [
                {"chunk": chunk, "similarity_score": float(score)}
                for chunk, score in similar_chunks
            ],
            "qa_result": qa_result,
        }
        return jsonify(response), 200

    except Exception as exc:
        logger.exception("learn: unhandled error – %s", exc)
        return jsonify({"error": str(exc)}), 500

    finally:
        # Always clean up the temporary PDF, regardless of success or failure.
        _cleanup_temp_file(temp_path)


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7700))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    logger.info("Starting Flask server on port %d (debug=%s).", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
