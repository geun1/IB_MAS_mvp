#!/bin/bash

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # 색상 초기화

echo -e "${YELLOW}에이전트 시작 스크립트${NC}"
echo "============================"

# Python 버전 확인
python --version
echo "============================"

# Python 경로 확인
echo "Python 경로:"
python -c "import sys; print(sys.path)"
echo "============================"

# 환경 변수 확인
echo "환경 변수:"
env | grep -E "OPENAI|ANTHROPIC|REGISTRY|LOG_LEVEL|PYTHONPATH"
echo "============================"

# 애플리케이션 시작
echo -e "${GREEN}애플리케이션을 시작합니다...${NC}"
exec uvicorn main:app --host 0.0.0.0 --port 8000
