FROM python:3.10-slim

WORKDIR /app

COPY ./agents/web_search/requirements.txt .
COPY ./common/ /app/common/

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/agent
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 