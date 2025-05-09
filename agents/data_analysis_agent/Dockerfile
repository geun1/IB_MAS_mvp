FROM python:3.10-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpng-dev \
    libfreetype6-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 필요한 디렉토리 생성
RUN mkdir -p /app/agent /app/common

# 공통 모듈 복사
COPY ./common/ /app/common/

# 의존성 파일 복사 및 설치
COPY ./agents/data_analysis_agent/requirements.txt /app/agent/
RUN pip install --no-cache-dir -r /app/agent/requirements.txt && pip install --no-cache-dir litellm==1.67.2

# 에이전트 파일 복사
COPY ./agents/data_analysis_agent/ /app/agent/

# 시작 스크립트 복사
COPY ./agents/start_agents.sh /app/

# 작업 디렉토리 설정
WORKDIR /app/agent

# 환경 변수 설정
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV PORT=8040
ENV CONTAINER_NAME="data_analysis_agent"

# 시작 명령
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8040"] 