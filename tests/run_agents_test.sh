#!/bin/bash

# 에이전트 실행 및 테스트 스크립트

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # 색상 초기화

echo -e "${YELLOW}에이전트 테스트를 시작합니다...${NC}"

# 현재 디렉토리 저장
CURRENT_DIR=$(pwd)

# 프로젝트 루트 디렉토리로 이동
cd $(dirname $0)/..

# 환경 변수 확인
if [ ! -f .env ]; then
    echo -e "${RED}.env 파일이 존재하지 않습니다. .env.example을 복사하여 설정하세요.${NC}"
    echo -e "${YELLOW}.env.example에서 .env 파일을 생성합니다...${NC}"
    cp .env.example .env
    echo -e "${RED}생성된 .env 파일에 API 키를 설정하세요.${NC}"
    exit 1
fi

# API 키 체크
if ! grep -q "OPENAI_API_KEY=REMOVED" .env || grep -q "OPENAI_API_KEY=REMOVED\.\.\." .env; then
    echo -e "${RED}OPENAI_API_KEY가 올바르게 설정되어 있지 않습니다.${NC}"
    echo -e "${YELLOW}테스트를 계속하지만, API 호출이 실패할 수 있습니다.${NC}"
fi

# 에이전트 실행 확인
if [ ! "$(docker ps -q -f name=web_search_agent)" ] || [ ! "$(docker ps -q -f name=writer_agent)" ]; then
    echo -e "${YELLOW}에이전트가 실행 중이 아닙니다. 에이전트를 시작합니다...${NC}"
    cd agents && docker-compose down && docker-compose up -d
    cd ..
    echo -e "${GREEN}에이전트가 시작되었습니다. 준비 시간을 기다립니다...${NC}"
    sleep 15
else
    echo -e "${GREEN}에이전트가 이미 실행 중입니다.${NC}"
fi

# 필요한 패키지 설치
pip install requests pytest

# 테스트 실행
echo -e "${YELLOW}테스트를 실행합니다...${NC}"
python tests/test_agents.py

# 테스트 결과 확인
if [ $? -eq 0 ]; then
    echo -e "${GREEN}모든 테스트가 성공했습니다!${NC}"
else
    echo -e "${RED}테스트 중 실패가 발생했습니다.${NC}"
    
    # 문제 해결을 위한 추가 정보
    echo -e "${YELLOW}문제 해결을 위한 진단 정보 수집 중...${NC}"
    echo "============================"
    echo "컨테이너 상태:"
    docker ps | grep -E "web_search_agent|writer_agent"
    
    echo "============================"
    echo "에이전트 로그:"
    echo "web_search_agent 로그 (마지막 10줄):"
    docker logs web_search_agent --tail 10
    
    echo "writer_agent 로그 (마지막 10줄):"
    docker logs writer_agent --tail 10
fi

# 원래 디렉토리로 돌아가기
cd $CURRENT_DIR 