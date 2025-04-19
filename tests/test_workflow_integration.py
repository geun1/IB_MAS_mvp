import httpx
import asyncio
import time
import json
import logging
import uuid
from pprint import pprint
from typing import Dict, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("workflow_test")

# 테스트 설정
REGISTRY_URL = "http://localhost:8000"
BROKER_URL = "http://localhost:8001"
TASKS_ENDPOINT = f"{BROKER_URL}/tasks"  # API 경로 수정
AGENT_ENDPOINTS = {
    "writer": "http://localhost:8010",
    "search": "http://localhost:8011"
}
MAX_WAIT_TIME = 120  # 태스크 완료 대기 최대 시간(초)

async def test_end_to_end_workflow():
    """
    레지스트리-브로커-에이전트 전체 워크플로우 통합 테스트
    
    1. 에이전트 등록 상태 확인
    2. 태스크 요청 생성
    3. 태스크 처리 및 완료 대기
    4. 결과 검증
    """
    logger.info("=== 전체 워크플로우 통합 테스트 시작 ===")
    
    # 1. 에이전트 상태 확인
    async with httpx.AsyncClient() as client:
        try:
            logger.info("에이전트 상태 확인 중...")
            response = await client.get(f"{REGISTRY_URL}/agents?role=writer&status=available")
            if response.status_code != 200:
                logger.error(f"에이전트 상태 조회 실패: {response.status_code}")
                return False
                
            agents_data = response.json()
            available_agents = agents_data.get("agents", [])
            
            if not available_agents:
                logger.error("사용 가능한 writer 에이전트가 없습니다")
                return False
                
            logger.info(f"{len(available_agents)}개의 writer 에이전트를 찾았습니다")
            
            # 2. 태스크 요청 생성
            logger.info("태스크 요청 생성 중...")
            task_request = {
                "role": "writer",
                "params": {
                    "topic": "인공지능과 인간의 미래",
                    "tone": "technical",
                    "length": 800
                },
                "conversation_id": f"test_workflow_{uuid.uuid4().hex[:8]}"
            }
            
            response = await client.post(TASKS_ENDPOINT, json=task_request)
            if response.status_code != 200:
                logger.error(f"태스크 생성 실패: {response.status_code} - {response.text}")
                return False
                
            result = response.json()
            task_id = result["task_id"]
            logger.info(f"태스크 생성됨: {task_id}")
            
            # 3. 태스크 처리 및 완료 대기
            logger.info("태스크 처리 및 완료 대기 중...")
            completed = False
            start_time = time.time()
            
            while not completed and time.time() - start_time < MAX_WAIT_TIME:
                await asyncio.sleep(3)  # 3초마다 상태 확인
                
                status_response = await client.get(f"{BROKER_URL}/tasks/{task_id}")
                if status_response.status_code != 200:
                    logger.error(f"태스크 조회 실패: {status_response.status_code}")
                    continue
                    
                task_info = status_response.json()
                current_status = task_info["status"]
                logger.info(f"현재 태스크 상태: {current_status}")
                
                if current_status in ["completed", "failed", "cancelled"]:
                    completed = True
                    logger.info("태스크 처리 완료!")
                    
                    if current_status == "completed":
                        logger.info("태스크가 성공적으로 완료되었습니다!")
                        logger.info("태스크 결과:")
                        pprint(task_info.get("result", {}))
                        
                        # 4. 결과 검증
                        result = task_info.get("result", {})
                        if not result or not isinstance(result, dict):
                            logger.error("태스크 결과가 없거나 형식이 잘못되었습니다")
                            return False
                            
                        # 결과에 필요한 필드가 있는지 확인
                        if "content" not in result:
                            logger.error("태스크 결과에 필수 필드(content)가 없습니다")
                            return False
                            
                        logger.info("결과 검증 성공!")
                        return True
                    else:
                        logger.error(f"태스크 실패: {task_info.get('error', '알 수 없는 오류')}")
                        return False
            
            if not completed:
                logger.error(f"태스크가 {MAX_WAIT_TIME}초 내에 완료되지 않았습니다")
                return False
                
        except Exception as e:
            logger.error(f"테스트 중 오류 발생: {str(e)}")
            return False

async def main():
    """테스트 실행 메인 함수"""
    # 1. 전체 워크플로우 테스트
    workflow_result = await test_end_to_end_workflow()
    if workflow_result:
        logger.info("✅ 전체 워크플로우 통합 테스트 성공!")
    else:
        logger.error("❌ 전체 워크플로우 통합 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main()) 