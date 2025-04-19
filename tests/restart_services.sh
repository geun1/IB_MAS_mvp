#!/bin/bash

echo "===== 서비스 재시작 중 ====="

# 현재 디렉토리 확인
PROJECT_ROOT=$(dirname $(cd $(dirname $0) && pwd))
echo "프로젝트 루트: $PROJECT_ROOT"

# Docker Compose 환경인지 확인
if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    echo "Docker Compose 환경 감지됨"
    
    # 레지스트리 서비스 재시작
    echo "레지스트리 서비스 재시작 중..."
    docker-compose -f "$PROJECT_ROOT/docker-compose.yml" restart registry
    
    # 브로커 서비스 재시작
    echo "브로커 서비스 재시작 중..."
    docker-compose -f "$PROJECT_ROOT/docker-compose.yml" restart broker
    
    # 상태 확인
    echo "서비스 상태 확인 중..."
    docker-compose -f "$PROJECT_ROOT/docker-compose.yml" ps registry broker
else
    echo "Docker Compose 환경이 아닌 것으로 보입니다."
    echo "수동으로 서비스를 재시작하세요."
fi

echo "===== 서비스 재시작 완료 =====" 