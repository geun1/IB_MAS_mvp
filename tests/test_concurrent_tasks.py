import httpx
import asyncio
import time
import json
import logging
import uuid
import random
from pprint import pprint
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("concurrent_test")

# 테스트 설정
REGISTRY_URL = "http://localhost:8000"
BROKER_URL = "http://localhost:8001"
MAX_WAIT_TIME = 180  # 태스크 완료 대기 최대 시간(초)
NUM_CONCURRENT_TASKS = 5  # 동시에 생성할 태스크 수

async def create_task(role, params):
    """태스크 생성"""
    conversation_id = f"test_concurrent_{uuid.uuid4().hex[:8]}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BROKER_URL}/task", 
                json={
                    "role": role,
                    "params": params,
                    "conversation_id": conversation_id
                }
            )
            
            if response.status_code != 200:
                logger.error(f"태스크 생성 실패: {response.status_code} - {response.text}")
                return None
                
            result = response.json()
            return result["task_id"]
            
        except Exception as e:
            logger.error(f"태스크 생성 중 오류: {str(e)}")
            return None

async def check_task_status(task_id):
    """태스크 상태 확인 및 완료 대기"""
    start_time = time.time()
    completed = False
    result = None
    
    async with httpx.AsyncClient() as client:
        while not completed and time.time() - start_time < MAX_WAIT_TIME:
            try:
                await asyncio.sleep(random.uniform(3, 5))  # 무작위 대기 시간
                
                response = await client.get(f"{BROKER_URL}/tasks/{task_id}")
                if response.status_code != 200:
                    logger.error(f"태스크 {task_id} 조회 실패: {response.status_code}")
                    continue
                    
                task_info = response.json()
                current_status = task_info["status"]
                logger.info(f"태스크 {task_id[:8]}... 상태: {current_status}")
                
                if current_status in ["completed", "failed", "cancelled"]:
                    completed = True
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    if current_status == "completed":
                        logger.info(f"태스크 {task_id[:8]}... 완료! (소요시간: {duration:.2f}초)")
                        result = {
                            "task_id": task_id,
                            "status": "completed",
                            "duration": duration,
                            "result": task_info.get("result")
                        }
                    else:
                        logger.error(f"태스크 {task_id[:8]}... 실패: {task_info.get('error', '알 수 없음')}")
                        result = {
                            "task_id": task_id,
                            "status": current_status,
                            "duration": duration,
                            "error": task_info.get("error")
                        }
            except Exception as e:
                logger.error(f"태스크 {task_id} 상태 확인 중 오류: {str(e)}")
        
        if not completed:
            logger.warning(f"태스크 {task_id[:8]}... 시간 초과!")
            result = {
                "task_id": task_id,
                "status": "timeout",
                "duration": MAX_WAIT_TIME
            }
            
        return result

async def test_concurrent_task_processing():
    """동시 태스크 처리 테스트"""
    logger.info(f"=== 동시 태스크 처리 테스트 시작 ({NUM_CONCURRENT_TASKS}개 태스크) ===")
    
    # 1. 테스트할 태스크 목록 생성
    task_configs = [
        {
            "role": "writer",
            "params": {
                "topic": f"인공지능의 미래 가능성 {i+1}",
                "tone": random.choice(["formal", "casual", "technical"]),
                "length": random.randint(300, 1000)
            }
        }
        for i in range(NUM_CONCURRENT_TASKS)
    ]
    
    # 2. 태스크 동시 생성
    logger.info("동시에 여러 태스크 생성 중...")
    start_time = time.time()
    
    tasks_creation = [create_task(config["role"], config["params"]) for config in task_configs]
    task_ids = await asyncio.gather(*tasks_creation)
    
    # 생성 실패한 태스크 제외
    valid_task_ids = [task_id for task_id in task_ids if task_id]
    
    if not valid_task_ids:
        logger.error("모든 태스크 생성에 실패했습니다")
        return False
        
    logger.info(f"{len(valid_task_ids)}/{NUM_CONCURRENT_TASKS}개 태스크 생성 성공!")
    
    # 3. 모든 태스크 상태 동시 확인
    logger.info("모든 태스크의 상태를 동시에 모니터링 중...")
    
    status_tasks = [check_task_status(task_id) for task_id in valid_task_ids]
    results = await asyncio.gather(*status_tasks)
    
    # 4. 결과 분석
    end_time = time.time()
    total_duration = end_time - start_time
    
    completed_tasks = [r for r in results if r and r["status"] == "completed"]
    failed_tasks = [r for r in results if r and r["status"] in ["failed", "cancelled"]]
    timeout_tasks = [r for r in results if r and r["status"] == "timeout"]
    
    logger.info(f"테스트 결과 요약 (총 소요시간: {total_duration:.2f}초):")
    logger.info(f"- 완료된 태스크: {len(completed_tasks)}/{len(valid_task_ids)}")
    logger.info(f"- 실패한 태스크: {len(failed_tasks)}/{len(valid_task_ids)}")
    logger.info(f"- 시간 초과 태스크: {len(timeout_tasks)}/{len(valid_task_ids)}")
    
    if completed_tasks:
        durations = [r["duration"] for r in completed_tasks]
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)
        
        logger.info(f"완료된 태스크 처리 시간 통계:")
        logger.info(f"- 평균: {avg_duration:.2f}초")
        logger.info(f"- 최대: {max_duration:.2f}초")
        logger.info(f"- 최소: {min_duration:.2f}초")
    
    # 테스트 성공 여부 판단 (50% 이상 완료 시 성공으로 간주)
    success_rate = len(completed_tasks) / len(valid_task_ids) if valid_task_ids else 0
    return success_rate >= 0.5

async def main():
    """테스트 실행 메인 함수"""
    # 동시 태스크 처리 테스트
    concurrent_result = await test_concurrent_task_processing()
    if concurrent_result:
        logger.info("✅ 동시 태스크 처리 테스트 성공!")
    else:
        logger.error("❌ 동시 태스크 처리 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main()) 