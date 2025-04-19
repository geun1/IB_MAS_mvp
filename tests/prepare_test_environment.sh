#!/bin/bash

echo "===== 테스트 환경 준비 시작 ====="

# 0. Redis 데이터 초기화 (레지스트리, 브로커 관련 키만)
echo -e "\n0. Redis 데이터 초기화 중..."
python reset_redis.py || { echo "Redis 초기화 실패. 테스트를 중단합니다."; exit 1; }

# 서비스 재시작
echo -e "\n서비스 재시작 중..."
./restart_services.sh

# 서비스가 다시 시작될 때까지 대기
echo "서비스 시작 대기 중..."
sleep 15

# 1. Redis 연결 테스트
echo -e "\n1. Redis 연결 테스트 중..."
python test_redis.py || { echo "Redis 연결 실패. 테스트를 중단합니다."; exit 1; }

# 2. API 엔드포인트 확인
echo -e "\n2. API 엔드포인트 확인 중..."
python debug_api_endpoints.py

# 2.1 브로커 API 확인
echo -e "\n2.1 브로커 API 경로 확인 중..."
python check_broker_api.py

# 3. 테스트용 에이전트 등록
echo -e "\n3. 테스트용 에이전트 등록 중..."
python register_test_agents.py || { echo "에이전트 등록 실패. 일부 테스트가 실패할 수 있습니다."; }

# 4. 환경 변수 설정
echo -e "\n4. 환경 변수 설정 중..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/..
echo "PYTHONPATH 설정: $PYTHONPATH"

echo -e "\n===== 테스트 환경 준비 완료 ====="
echo "이제 다음 명령으로 통합 테스트를 실행할 수 있습니다:"
echo "  ./run_integration_tests.sh" 