FROM python:3.11-slim

# System deps for PyMuPDF, Tesseract, pdf2image
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure data folders exist
RUN mkdir -p data/incoming data/processed data/duplicates data/failed data/exports logs
