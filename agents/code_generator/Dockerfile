FROM python:3.10-slim

WORKDIR /app

COPY ./agents/code_generator/requirements.txt .
COPY ./common/ /app/common/
COPY ./agents/code_generator/*.py /app/agent/

RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir litellm==1.67.2

# Python 모듈 경로에 현재 디렉토리 추가
ENV PYTHONPATH="${PYTHONPATH}:/app"

WORKDIR /app/agent
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 