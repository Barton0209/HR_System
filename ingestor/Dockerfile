FROM python:3.11-slim

WORKDIR /app

COPY ingestor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestor/ /app/ingestor/

ENV PYTHONPATH=/app/ingestor

CMD ["uvicorn", "ingestor.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
