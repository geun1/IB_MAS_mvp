FROM python:3.10-slim

WORKDIR /app

COPY ./agents/web_search/requirements.txt .
COPY ./common/ /app/common/

# 필요한 시스템 패키지 설치 (HTML 파싱을 위한 라이브러리 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir litellm==1.67.2

# Python 모듈 경로에 현재 디렉토리 추가
ENV PYTHONPATH="${PYTHONPATH}:/app"

WORKDIR /app/agent
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 