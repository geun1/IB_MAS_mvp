FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
COPY common/ /app/common/
COPY orchestrator/ /app/orchestrator/

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/orchestrator
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 