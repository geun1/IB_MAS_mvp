#!/bin/bash

# 이 스크립트는 stock_analysis_agent 서비스를 시작합니다

# 환경 변수 설정
export PYTHONPATH=$PYTHONPATH:$(pwd)
export REGISTRY_URL="${REGISTRY_URL:-http://registry:8000}"
export CONTAINER_NAME="${CONTAINER_NAME:-stock_analysis_agent}"
export PORT="${PORT:-8000}"

# 필요한 디렉토리로 이동
cd "$(dirname "$0")"

# 서비스 시작
uvicorn main:app --host 0.0.0.0 --port $PORT --reload 