import httpx
import asyncio
import time
import json
import logging
import uuid
import random
from pprint import pprint

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("resilience_test")

# 테스트 설정
REGISTRY_URL = "http://localhost:8000"
BROKER_URL = "http://localhost:8001"
MAX_WAIT_TIME = 180  # 태스크 완료 대기 최대 시간(초)

async def create_faulty_agent():
    """장애가 발생하는 가상 에이전트 등록"""
    logger.info("장애 발생 가상 에이전트 등록 중...")
    
    # 고유 ID 생성
    agent_id = f"faulty_agent_{uuid.uuid4().hex[:8]}"
    
    # 테스트 에이전트 정의
    test_agent = {
        "id": agent_id,
        "role": "writer",
        "description": "장애가 발생하는 작성 에이전트 (테스트용)",
        "params": [
            {
                "name": "topic",
                "description": "작성할 문서의 주제",
                "type": "string",
                "required": True
            },
            {
                "name": "tone",
                "description": "문서의 어조",
                "type": "string",
                "required": False,
                "enum": ["formal", "casual", "technical", "neutral"],
                "default": "neutral"
            }
        ],
        "endpoint": "http://nonexistent-host:9999/process",  # 존재하지 않는 엔드포인트
        "status": "available",
        "load": 0.1,
        "active_tasks": 0
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{REGISTRY_URL}/register", json=test_agent)
        
        if response.status_code != 200:
            logger.error(f"장애 에이전트 등록 실패: {response.status_code} - {response.text}")
            return None
            
        result = response.json()
        logger.info(f"장애 에이전트 등록 성공: {agent_id}")
        return agent_id

async def register_backup_agent():
    """백업 에이전트 등록"""
    logger.info("백업 에이전트 등록 중...")
    
    # 고유 ID 생성
    agent_id = f"backup_agent_{uuid.uuid4().hex[:8]}"
    
    # 백업 에이전트 정의
    backup_agent = {
        "id": agent_id,
        "role": "writer",
        "description": "백업 작성 에이전트 (장애 복구 테스트용)",
        "params": [
            {
                "name": "topic",
                "description": "작성할 문서의 주제",
                "type": "string",
                "required": True
            },
            {
                "name": "tone",
                "description": "문서의 어조",
                "type": "string",
                "required": False,
                "enum": ["formal", "casual", "technical", "neutral"],
                "default": "neutral"
            }
        ],
        "endpoint": "http://localhost:8010/process",  # 실제 작동하는 엔드포인트
        "status": "available",
        "load": 0.5,  # 우선순위 낮게 설정
        "active_tasks": 0
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{REGISTRY_URL}/register", json=backup_agent)
        
        if response.status_code != 200:
            logger.error(f"백업 에이전트 등록 실패: {response.status_code} - {response.text}")
            return None
            
        result = response.json()
        logger.info(f"백업 에이전트 등록 성공: {agent_id}")
        return agent_id

async def test_agent_failure_recovery():
    """에이전트 장애 복구 테스트"""
    logger.info("=== 에이전트 장애 복구 테스트 시작 ===")
    
    # 1. 장애 에이전트 및 백업 에이전트 등록
    faulty_agent_id = await create_faulty_agent()
    if not faulty_agent_id:
        logger.error("장애 에이전트 등록 실패로 테스트를 종료합니다")
        return False
        
    backup_agent_id = await register_backup_agent()
    if not backup_agent_id:
        logger.error("백업 에이전트 등록 실패로 테스트를 종료합니다")
        return False
    
    # 잠시 대기 - 에이전트 등록 처리 완료 대기
    await asyncio.sleep(3)
    
    # 2. 태스크 요청 생성
    async with httpx.AsyncClient() as client:
        logger.info("태스크 요청 생성 중...")
        task_request = {
            "role": "writer",
            "params": {
                "topic": "인공지능 시스템의 장애 복구 메커니즘",
                "tone": "technical"
            },
            "conversation_id": f"test_resilience_{uuid.uuid4().hex[:8]}"
        }
        
        response = await client.post(f"{BROKER_URL}/task", json=task_request)
        if response.status_code != 200:
            logger.error(f"태스크 생성 실패: {response.status_code} - {response.text}")
            return False
            
        result = response.json()
        task_id = result["task_id"]
        logger.info(f"태스크 생성됨: {task_id}")
        
        # 3. 태스크 처리 및 완료 대기 - 재시도와 장애 복구가 발생할 것으로 예상
        logger.info("태스크 처리 및 복구 대기 중... (장애 발생 후 백업 에이전트로 전환될 것임)")
        completed = False
        start_time = time.time()
        
        while not completed and time.time() - start_time < MAX_WAIT_TIME:
            await asyncio.sleep(5)  # 5초마다 상태 확인 (더 긴 간격으로 설정)
            
            status_response = await client.get(f"{BROKER_URL}/tasks/{task_id}")
            if status_response.status_code != 200:
                logger.error(f"태스크 조회 실패: {status_response.status_code}")
                continue
                
            task_info = status_response.json()
            current_status = task_info["status"]
            current_agent = task_info.get("agent_id", "알 수 없음")
            
            logger.info(f"현재 태스크 상태: {current_status}, 처리 에이전트: {current_agent}")
            
            if current_status in ["completed", "failed", "cancelled"]:
                completed = True
                logger.info("태스크 처리 완료!")
                
                if current_status == "completed":
                    logger.info("태스크가 성공적으로 완료되었습니다!")
                    logger.info("장애 복구 성공 - 백업 에이전트가 태스크를 완료함")
                    
                    # 처리한 에이전트 확인
                    if current_agent == faulty_agent_id:
                        logger.warning("장애 에이전트가 태스크를 처리했습니다? (예상치 못한 결과)")
                    elif current_agent == backup_agent_id:
                        logger.info("✅ 백업 에이전트가 태스크를 처리했습니다 (예상대로)")
                    else:
                        logger.info(f"다른 에이전트({current_agent})가 태스크를 처리했습니다")
                    
                    return True
                else:
                    logger.error(f"태스크 실패: {task_info.get('error', '알 수 없는 오류')}")
                    return False
        
        if not completed:
            logger.error(f"태스크가 {MAX_WAIT_TIME}초 내에 완료되지 않았습니다")
            return False

async def main():
    """테스트 실행 메인 함수"""
    # 에이전트 장애 복구 테스트
    resilience_result = await test_agent_failure_recovery()
    if resilience_result:
        logger.info("✅ 에이전트 장애 복구 테스트 성공!")
    else:
        logger.error("❌ 에이전트 장애 복구 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main()) 