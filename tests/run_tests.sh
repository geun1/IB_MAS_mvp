#!/bin/bash
# 프로젝트 테스트 실행 스크립트

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}테스트 환경 준비 중...${NC}"
echo -e "Docker 서비스가 실행 중인지 확인하세요."

# Redis 테스트 실행
echo -e "\n${YELLOW}Redis 테스트 실행 중...${NC}"
pytest -xvs test_redis.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Redis 테스트 성공!${NC}"
else
    echo -e "${RED}Redis 테스트 실패${NC}"
fi

# 간소화된 RabbitMQ 테스트 실행
echo -e "\n${YELLOW}간소화된 RabbitMQ 테스트 실행 중...${NC}"
python test_rabbitmq_simple.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}간소화된 RabbitMQ 테스트 성공!${NC}"
else
    echo -e "${RED}간소화된 RabbitMQ 테스트 실패${NC}"
fi

# 수정된 RabbitMQ 테스트 실행
echo -e "\n${YELLOW}수정된 RabbitMQ 테스트 실행 중...${NC}"
pytest -xvs test_rabbitmq.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}수정된 RabbitMQ 테스트 성공!${NC}"
else
    echo -e "${RED}수정된 RabbitMQ 테스트 실패${NC}"
fi

# 통합 테스트 실행
echo -e "\n${YELLOW}통합 테스트 실행 중...${NC}"
pytest -xvs test_integration.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}통합 테스트 성공!${NC}"
else
    echo -e "${RED}통합 테스트 실패${NC}"
fi

echo -e "\n${YELLOW}모든 테스트 완료${NC}" 