import os
from flask import Flask, jsonify, request
import redis
from dotenv import load_dotenv
from gemini_service import get_gemini_service
from pdf_extractor import extract_text_from_pdf, extract_pdf_metadata
from vector_store import VectorStore
from werkzeug.utils import secure_filename
import tempfile

load_dotenv()

app = Flask(__name__)

# Initialize Gemini service
try:
    gemini = get_gemini_service()
except Exception as e:
    print(f"Warning: Could not initialize Gemini service: {e}")

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


@app.route("/learn", methods=["POST"])
def learn():
    """
    Extract text from uploaded PDF, create embeddings with OpenAI,
    build FAISS index, and find similar chunks to the topic
    
    Form parameters:
    - uploadedPDF: The PDF file to extract text from
    - topicToLearn: The topic/subject to focus on
    """
    temp_path = None
    
    try:
        # Check if file is in the request
        if "uploadedPDF" not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400
        
        file = request.files["uploadedPDF"]
        topic = request.form.get("topicToLearn", "")
        
        if file.filename == "":
            return jsonify({"error": "No PDF file selected"}), 400
        
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "File must be a PDF"}), 400
        
        if not topic:
            return jsonify({"error": "topicToLearn is required"}), 400
        
        # Save file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            file.save(tmp_file.name)
            temp_path = tmp_file.name
        
        try:
            # Extract text from PDF
            extracted_text = extract_text_from_pdf(temp_path)
            metadata = extract_pdf_metadata(temp_path)
            
            if not extracted_text:
                return jsonify({"error": "No text extracted from PDF"}), 400
            
            # Initialize vector store with Google Gemini
            vector_store = VectorStore(
                google_api_key=os.environ.get("GOOGLE_API_KEY"),
                pickle_file="faiss_store.pkl"
            )
            
            # Create vector store from extracted text
            success = vector_store.create_vector_store_from_text(extracted_text)
            
            if not success:
                return jsonify({"error": "Failed to create vector store"}), 400
            
            # Find similar chunks to the topic
            similar_chunks = vector_store.search_similar(topic, k=5)
            
            # Query with sources using LLM
            enhanced_query = f"make something interesting and insightful and exciting for humans and in 60 words from: {topic}"
            qa_result = vector_store.query_with_sources(enhanced_query)
            
            response = {
                "status": "success",
                "topic": topic,
                "metadata": metadata,
                "extracted_text_length": len(extracted_text),
                "vector_store_info": vector_store.get_index_info(),
                "similar_chunks": [
                    {
                        "chunk": chunk,
                        "similarity_score": float(score)
                    }
                    for chunk, score in similar_chunks
                ],
                "qa_result": qa_result
            }
            
            return jsonify(response), 200
            
        finally:
            # Clean up temporary file
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
    
    except Exception as e:
        # Clean up on error
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7700))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host="0.0.0.0", port=port, debug=debug)
