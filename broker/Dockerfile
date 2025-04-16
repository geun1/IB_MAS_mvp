FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
COPY common/ /app/common/
COPY broker/ /app/broker/

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/broker
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 