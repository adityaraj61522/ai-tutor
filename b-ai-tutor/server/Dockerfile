# ---------------------------------------------------------------------------
# Stage 1 – build / install dependencies
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# System libraries required by faiss-cpu (OpenMP) and pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 – lean runtime image
# ---------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# libgomp1 is needed at runtime by faiss-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

EXPOSE 7700

CMD ["python", "app.py"]
