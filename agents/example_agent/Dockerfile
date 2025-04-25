# 다른 에이전트와 동일한 Python 버전 사용
FROM python:3.10-slim

WORKDIR /app

# 공통 모듈과 에이전트별 요구사항 복사
COPY ./common/ /app/common/
COPY ./agents/example_agent/requirements.txt .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 에이전트 코드 복사
COPY ./agents/example_agent/main.py /app/agent/

# Python 모듈 경로 설정 (common 디렉토리 포함)
ENV PYTHONPATH="${PYTHONPATH}:/app"

# 작업 디렉토리 변경
WORKDIR /app/agent

# 서버 실행 (start_agents.sh 사용 권장)
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# docker-compose.yml 에서 start_agents.sh 를 사용하므로 CMD는 주석 처리하거나 제거 가능 