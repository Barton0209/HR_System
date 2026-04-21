FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-rus \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ocr_core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ocr_core/ /app/ocr_core/
COPY config/ /app/config/

ENV OCR_CONFIG=/app/config/ocr_selector.yaml
ENV TESSERACT_PATH=/usr/bin/tesseract
ENV PYTHONPATH=/app/ocr_core

CMD ["uvicorn", "ocr_core.main:app", "--host", "0.0.0.0", "--port", "8001"]
