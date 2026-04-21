FROM python:3.11-slim

WORKDIR /app

COPY nlp_layer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY nlp_layer/ /app/nlp_layer/

ENV PYTHONPATH=/app/nlp_layer

CMD ["uvicorn", "nlp_layer.main:app", "--host", "0.0.0.0", "--port", "8002"]
