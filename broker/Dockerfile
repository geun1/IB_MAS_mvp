FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
COPY common/ /app/common/
COPY broker/ /app/broker/

RUN pip install --no-cache-dir -r requirements.txt

# Python 모듈 경로에 현재 디렉토리 추가
ENV PYTHONPATH="${PYTHONPATH}:/app"

# 작업 디렉토리 유지
WORKDIR /app

# 프로젝트를 모듈로 인식하도록 수정
CMD ["uvicorn", "broker.main:app", "--host", "0.0.0.0", "--port", "8001"] 