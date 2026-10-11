FROM python:3.11-slim
# Tesseract enables OCR for scanned PDFs / handwritten-note images
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 FLASK_ENV=production
# 1 worker + threads: document processing runs in an in-process thread pool
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 8 --timeout 180
