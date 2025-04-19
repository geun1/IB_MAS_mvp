import httpx
import asyncio
import time
import json
import logging
from pprint import pprint

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("caching_test")

# 테스트 설정
BROKER_URL = "http://localhost:8001"

async def test_task_caching():
    """동일한 파라미터로 여러 번 태스크를 요청하여 캐싱 확인"""
    logger.info("=== 태스크 결과 캐싱 테스트 시작 ===")
    
    # 테스트 태스크 요청
    task_request = {
        "role": "search",
        "params": {
            "query": "최신 인공지능 기술 동향",
            "num_results": 5
        },
        "conversation_id": f"test_cache_{int(time.time())}"
    }
    
    async with httpx.AsyncClient() as client:
        # 첫 번째 태스크 요청
        logger.info("첫 번째 태스크 요청 중...")
        response1 = await client.post(f"{BROKER_URL}/task", json=task_request)
        
        if response1.status_code != 200:
            logger.error(f"첫 번째 태스크 생성 실패: {response1.status_code} - {response1.text}")
            return False
            
        result1 = response1.json()
        task_id1 = result1["task_id"]
        logger.info(f"첫 번째 태스크 생성됨: {task_id1}")
        
        # 첫 번째 태스크 완료 대기
        logger.info("첫 번째 태스크 완료 대기 중...")
        completed = False
        max_wait = 60  # 최대 60초 대기
        start_time = time.time()
        first_task_result = None
        first_task_execution_time = None
        
        while not completed and time.time() - start_time < max_wait:
            await asyncio.sleep(3)
            
            status_response = await client.get(f"{BROKER_URL}/tasks/{task_id1}")
            if status_response.status_code != 200:
                logger.error(f"태스크 조회 실패: {status_response.status_code}")
                continue
                
            task_info = status_response.json()
            current_status = task_info["status"]
            logger.info(f"현재 태스크 상태: {current_status}")
            
            if current_status == "completed":
                completed = True
                logger.info("첫 번째 태스크 완료!")
                first_task_result = task_info.get("result")
                first_task_execution_time = task_info.get("execution_time")
                logger.info(f"첫 번째 태스크 실행 시간: {first_task_execution_time}초")
                
        if not completed or not first_task_result:
            logger.error("첫 번째 태스크가 성공적으로 완료되지 않았습니다")
            return False
            
        # 잠시 대기
        await asyncio.sleep(5)
        
        # 두 번째 태스크 요청 (동일한 파라미터)
        logger.info("두 번째 태스크 요청 중 (동일한 파라미터)...")
        task_request["conversation_id"] = f"test_cache_{int(time.time())}"  # ID만 변경
        response2 = await client.post(f"{BROKER_URL}/task", json=task_request)
        
        if response2.status_code != 200:
            logger.error(f"두 번째 태스크 생성 실패: {response2.status_code} - {response2.text}")
            return False
            
        result2 = response2.json()
        task_id2 = result2["task_id"]
        logger.info(f"두 번째 태스크 생성됨: {task_id2}")
        
        # 두 번째 태스크 상태 즉시 확인 (캐시 히트로 인해 바로 완료되어야 함)
        status_response = await client.get(f"{BROKER_URL}/tasks/{task_id2}")
        if status_response.status_code != 200:
            logger.error(f"두 번째 태스크 조회 실패: {status_response.status_code}")
            return False
            
        task_info = status_response.json()
        logger.info(f"두 번째 태스크 상태: {task_info['status']}")
        logger.info(f"캐시 히트 여부: {task_info.get('cache_hit', False)}")
        
        # 캐시 히트 검증
        if not task_info.get('cache_hit', False):
            logger.error("두 번째 태스크에서 캐시 히트가 발생하지 않았습니다")
            return False
            
        if task_info["status"] != "completed":
            logger.error("캐시 히트에도 불구하고 태스크가 완료 상태가 아닙니다")
            return False
            
        # 두 태스크의 결과 비교
        second_task_result = task_info.get("result")
        if json.dumps(first_task_result, sort_keys=True) != json.dumps(second_task_result, sort_keys=True):
            logger.error("첫 번째와 두 번째 태스크의 결과가 다릅니다")
            return False
            
        logger.info("첫 번째와 두 번째 태스크의 결과가 동일합니다")
        logger.info("캐싱 테스트 성공!")
        return True

async def main():
    """테스트 실행 메인 함수"""
    result = await test_task_caching()
    if result:
        logger.info("✅ 태스크 결과 캐싱 테스트 성공!")
    else:
        logger.error("❌ 태스크 결과 캐싱 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main()) 