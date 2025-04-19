#!/bin/bash

echo "===== 통합 테스트 시작 ====="

# 환경 준비
echo "환경 변수 설정..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/..

# Redis 연결 테스트
echo -e "\n1. Redis 연결 테스트"
python test_redis.py

# 기본 브로커 테스트
echo -e "\n2. 브로커 기본 기능 테스트"
python test_broker_basic.py

# 전체 워크플로우 테스트
echo -e "\n3. 전체 워크플로우 통합 테스트"
python test_workflow_integration.py

# 장애 복구 테스트
echo -e "\n4. 에이전트 장애 복구 테스트"
python test_resilience.py

# 동시 요청 테스트
echo -e "\n5. 동시 태스크 처리 테스트"
python test_concurrent_tasks.py

echo -e "\n===== 테스트 완료 =====" 