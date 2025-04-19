import httpx
import asyncio
import time
import json
import logging
from pprint import pprint
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("broker_test")

# 테스트 설정
BROKER_URL = "http://localhost:8001"
REGISTRY_URL = "http://localhost:8000"

async def test_basic_task_lifecycle():
    """브로커 기본 작업 생명주기 테스트"""
    logger.info("=== 기본 태스크 생명주기 테스트 시작 ===")
    
    # 1. 태스크 생성 요청
    task_request = {
        "role": "writer",
        "params": {
            "topic": "인공지능의 윤리적 고려사항",
            "tone": "formal",
            "length": 500
        },
        "conversation_id": f"test_basic_{int(time.time())}"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 태스크 생성 요청
        logger.info("태스크 생성 요청 중...")
        response = await client.post(f"{BROKER_URL}/task", json=task_request)
        
        if response.status_code != 200:
            logger.error(f"태스크 생성 실패: {response.status_code} - {response.text}")
            return False
            
        result = response.json()
        task_id = result["task_id"]
        logger.info(f"태스크 생성됨: {task_id}")
        
        # 2. 태스크 상태 확인
        logger.info("태스크 처리 중 상태 확인...")
        await asyncio.sleep(2)  # 프로세싱 상태 확인을 위한 대기
        
        status_response = await client.get(f"{BROKER_URL}/tasks/{task_id}")
        if status_response.status_code != 200:
            logger.error(f"태스크 조회 실패: {status_response.status_code}")
            return False
            
        task_info = status_response.json()
        logger.info(f"현재 태스크 상태: {task_info['status']}")
        
        # 3. 태스크 완료 대기
        logger.info("태스크 완료 대기 중...")
        completed = False
        max_wait = 60  # 최대 60초 대기
        start_time = time.time()
        
        while not completed and time.time() - start_time < max_wait:
            await asyncio.sleep(3)  # 3초마다 확인
            
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
                logger.info(f"최종 상태: {current_status}")
                if current_status == "completed" and task_info.get("result"):
                    logger.info("태스크 결과:")
                    pprint(task_info["result"])
                elif current_status == "failed":
                    logger.error(f"태스크 실패 원인: {task_info.get('error', '알 수 없음')}")
                    
        if not completed:
            logger.warning("태스크가 시간 내에 완료되지 않았습니다")
            return False
            
        # 4. 태스크 목록 조회
        logger.info("태스크 목록 조회...")
        list_response = await client.get(f"{BROKER_URL}/tasks?role=writer&page=1&page_size=5")
        
        if list_response.status_code != 200:
            logger.error(f"태스크 목록 조회 실패: {list_response.status_code}")
            return False
            
        task_list = list_response.json()
        logger.info(f"총 태스크 수: {task_list['total']}")
        logger.info("최근 태스크 목록:")
        for task in task_list["tasks"]:
            logger.info(f"- {task['task_id'][:8]}...: {task['status']} ({task['role']})")
        
        return completed and task_info["status"] == "completed"

async def main():
    """테스트 실행 메인 함수"""
    # 브로커 연결 확인
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BROKER_URL}/health")
            if response.status_code != 200:
                logger.error(f"브로커 연결 실패: {response.status_code}")
                return
            logger.info("브로커 연결 성공")
    except Exception as e:
        logger.error(f"브로커 연결 오류: {str(e)}")
        return
        
    # 테스트 실행
    result = await test_basic_task_lifecycle()
    if result:
        logger.info("✅ 기본 태스크 생명주기 테스트 성공!")
    else:
        logger.error("❌ 기본 태스크 생명주기 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main()) 