#!/bin/bash

# 사용 방법
usage() {
  echo "사용법: $0 [옵션]"
  echo "옵션:"
  echo "  all       - 모든 에이전트 시작"
  echo "  web_search - Web Search 에이전트만 시작"
  echo "  writer    - Writer 에이전트만 시작"
  echo "  code_generator - Code Generator 에이전트만 시작"
  echo "  stop      - 모든 에이전트 중지"
  echo "  status    - 에이전트 상태 확인"
  exit 1
}

# 인자가 없으면 사용법 출력
if [ $# -eq 0 ]; then
  usage
fi

# 명령어 처리
case "$1" in
  all)
    echo "모든 에이전트를 시작합니다..."
    docker-compose up 
    ;;
  web_search)
    echo "Web Search 에이전트를 시작합니다..."
    cd web_search && docker-compose up 
    ;;
  writer)
    echo "Writer 에이전트를 시작합니다..."
    cd writer && docker-compose up 
    ;;
  code_generator)
    echo "Code Generator 에이전트를 시작합니다..."
    cd code_generator && docker-compose up 
    ;;
  stop)
    echo "모든 에이전트를 중지합니다..."
    docker-compose down
    ;;
  status)
    echo "에이전트 상태를 확인합니다..."
    docker-compose ps
    ;;
  *)
    usage
    ;;
esac

echo "완료되었습니다."