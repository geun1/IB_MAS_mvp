#!/bin/bash

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # 색상 초기화

echo -e "${YELLOW}환경 변수 확인 스크립트${NC}"
echo "============================"

# .env 파일 체크
if [ -f ../.env ]; then
    echo -e "${GREEN}.env 파일이 존재합니다.${NC}"
    
    # API 키 체크
    if grep -q "OPENAI_API_KEY" ../.env; then
        echo -e "${GREEN}OPENAI_API_KEY가 설정되어 있습니다.${NC}"
    else
        echo -e "${RED}OPENAI_API_KEY가 설정되어 있지 않습니다.${NC}"
    fi
    
    if grep -q "ANTHROPIC_API_KEY" ../.env; then
        echo -e "${GREEN}ANTHROPIC_API_KEY가 설정되어 있습니다.${NC}"
    else
        echo -e "${RED}ANTHROPIC_API_KEY가 설정되어 있지 않습니다.${NC}"
    fi
else
    echo -e "${RED}.env 파일이 존재하지 않습니다. .env.example을 복사하여 설정하세요.${NC}"
fi

echo ""
echo "컨테이너 내부 환경 변수 확인"
echo "============================"

# 컨테이너에서 환경 변수 확인
echo -e "${YELLOW}web_search_agent 환경 변수:${NC}"
docker exec -it web_search_agent env | grep -E "OPENAI|ANTHROPIC|REGISTRY|LOG_LEVEL"

echo ""
echo -e "${YELLOW}writer_agent 환경 변수:${NC}"
docker exec -it writer_agent env | grep -E "OPENAI|ANTHROPIC|REGISTRY|LOG_LEVEL"

echo ""
echo "컨테이너 로그 확인"
echo "============================"
echo -e "${YELLOW}writer_agent 최근 로그:${NC}"
docker logs writer_agent --tail 20 