#!/bin/bash

# 에이전트 테스트를 위한 스크립트
# 에이전트를 독립적으로 실행하여 테스트합니다

# 사용 방법
usage() {
  echo "사용법: $0 [web_search|writer|all]"
  echo "  web_search: 웹 검색 에이전트만 실행"
  echo "  writer: 작성 에이전트만 실행"
  echo "  all: 모든 에이전트 실행"
  exit 1
}

# 환경 변수 로드
source "$(dirname "$0")/agents.env"

# 웹 검색 에이전트 실행
run_web_search() {
  echo "웹 검색 에이전트 실행 중..."
  cd ../agents/web_search
  PORT=8003 CONTAINER_NAME=localhost python -m uvicorn main:app --host 0.0.0.0 --port 8003
}

# 작성 에이전트 실행
run_writer() {
  echo "작성 에이전트 실행 중..."
  cd ../agents/writer
  PORT=8004 CONTAINER_NAME=localhost python -m uvicorn main:app --host 0.0.0.0 --port 8004
}

# 인자 확인
if [ $# -eq 0 ]; then
  usage
fi

# 명령 실행
case "$1" in
  web_search)
    run_web_search
    ;;
  writer)
    run_writer
    ;;
  all)
    echo "모든 에이전트를 실행합니다 (두 개의 터미널에서 각각 실행해야 함)"
    echo "터미널 1: $0 web_search"
    echo "터미널 2: $0 writer"
    ;;
  *)
    usage
    ;;
esac 