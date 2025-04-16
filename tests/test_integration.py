"""
시스템 통합 테스트 모듈

이 모듈은 전체 시스템의 통합 기능을 테스트합니다.
주요 테스트 항목:
1. 모든 서비스의 상태 확인 (헬스 체크)
2. 사용자 쿼리 처리 흐름 검증 (Orchestrator -> Broker -> Agent)

이 테스트는 실제 시스템이 모두 실행 중인 상태에서 수행되어야 합니다.
로컬 환경 또는 Docker 컨테이너를 통해 모든 서비스가 실행 중이어야 합니다.

테스트 실행 방법:
    $ python test_integration.py
"""

import os
import json
import requests
import time
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 서비스 URL
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:8000")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")
BROKER_URL = os.getenv("BROKER_URL", "http://localhost:8002")


def test_system_health():
    """
    전체 시스템 헬스 체크
    
    모든 주요 서비스(Registry, Orchestrator, Broker)의 상태를 확인합니다.
    각 서비스는 '/health' 엔드포인트를 통해 상태 정보를 제공해야 합니다.
    
    반환값:
        dict: 각 서비스별 상태 정보를 담은 딕셔너리
              {
                "service_name": {
                  "status": HTTP 상태 코드,
                  "body": 응답 본문 (JSON)
                }
              }
    
    서비스에 연결할 수 없는 경우 에러 정보를 포함합니다.
    """
    services = {
        "registry": f"{REGISTRY_URL}/health",
        "orchestrator": f"{ORCHESTRATOR_URL}/health",
        "broker": f"{BROKER_URL}/health",
    }
    
    results = {}
    
    for service_name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            results[service_name] = {
                "status": response.status_code,
                "body": response.json()
            }
        except Exception as e:
            results[service_name] = {
                "status": "error",
                "error": str(e)
            }
    
    return results


def test_query_flow(query="테스트 검색해줘"):
    """
    전체 쿼리 흐름 테스트
    
    사용자 쿼리가 시스템을 통과하는 전체 흐름을 테스트합니다:
    1. Orchestrator에 쿼리 전송
    2. 태스크 생성 및 처리 상태 확인
    
    향후 결과 조회 API가 구현되면 최종 결과까지 확인하도록 확장할 예정입니다.
    
    매개변수:
        query (str): 테스트할 사용자 쿼리 문자열
    
    반환값:
        dict: 테스트 결과 정보를 담은 딕셔너리
              성공 시: {"success": True, "conversation_id": "...", "result": {...}}
              실패 시: {"success": False, "error": "에러 메시지"}
    """
    try:
        # 1. Orchestrator에 쿼리 전송
        response = requests.post(
            f"{ORCHESTRATOR_URL}/query",
            json={"query": query, "user_id": "test_user"}
        )
        response.raise_for_status()
        
        result = response.json()
        conversation_id = result.get("conversation_id")
        
        print(f"쿼리 전송 완료: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # TODO: 결과 조회 API가 구현되면 여기서 결과 확인 로직 추가
        # 예: 주기적으로 결과 조회 API를 호출하여 처리 완료 상태 확인
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "result": result
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# 직접 실행 시 테스트
if __name__ == "__main__":
    """
    통합 테스트를 직접 실행합니다.
    1. 시스템 헬스 체크 수행
    2. 샘플 쿼리로 전체 흐름 테스트
    
    결과는 콘솔에 JSON 형태로 출력됩니다.
    """
    print("시스템 헬스 체크 중...")
    health_results = test_system_health()
    print(json.dumps(health_results, indent=2, ensure_ascii=False))
    
    print("\n쿼리 흐름 테스트 중...")
    query_result = test_query_flow("인공지능에 대한 보고서 작성해줘")
    print(json.dumps(query_result, indent=2, ensure_ascii=False)) 