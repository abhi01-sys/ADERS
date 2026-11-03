# ── Stage 1: Build React Frontend ─────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /app/dashboard_react
COPY dashboard_react/package*.json ./
RUN npm install
COPY dashboard_react/ ./
RUN npm run build

# ── Stage 2: Python Backend & Runtime ─────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by OpenCV and media handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-first (lightweight, fits easily in Render free tier memory)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Copy compiled frontend from Stage 1 into dashboard_react/dist
COPY --from=frontend-builder /app/dashboard_react/dist ./dashboard_react/dist

# Expose default port
ENV PORT=8000
EXPOSE 8000

# Start FastAPI server binding to $PORT (Render injects $PORT automatically)
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
