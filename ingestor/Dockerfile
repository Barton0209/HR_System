FROM python:3.11-slim
WORKDIR /app
COPY ingestor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ingestor/ /app/
COPY web_ui/ /app/web_ui/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
