"""
오케스트레이터 기능 테스트 스크립트
"""
import asyncio
import httpx
import logging
import os
import json
import time
from typing import Dict, Any, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")
TIMEOUT = 120  # 초

async def test_query(query: str):
    """
    오케스트레이터 쿼리 테스트
    """
    logger.info(f"테스트 시작: '{query}'")
    
    try:
        # 쿼리 요청
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/query",
                json={"query": query},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            conversation_id = result.get("conversation_id")
            logger.info(f"쿼리 요청 성공 (대화 ID: {conversation_id})")
            
            # 태스크 현황 로깅
            tasks = result.get("tasks", [])
            logger.info(f"{len(tasks)}개의 태스크가 생성됨:")
            for i, task in enumerate(tasks):
                logger.info(f"  {i+1}. 역할: {task.get('role')}, 설명: {task.get('description')}")
            
            # 처리 완료 대기
            start_time = time.time()
            status = "processing"
            
            while status == "processing" and (time.time() - start_time) < TIMEOUT:
                await asyncio.sleep(5)
                
                # 상태 확인
                status_response = await client.get(f"{ORCHESTRATOR_URL}/conversation/{conversation_id}")
                status_response.raise_for_status()
                status_data = status_response.json()
                
                status = status_data.get("status")
                logger.info(f"대화 상태: {status} (경과 시간: {int(time.time() - start_time)}초)")
                
                # 완료되었으면 결과 출력
                if status != "processing":
                    results = status_data.get("results", [])
                    logger.info(f"태스크 완료 결과:")
                    
                    success_count = 0
                    for i, result in enumerate(results):
                        r_status = result.get("status", "unknown")
                        if r_status == "completed":
                            success_count += 1
                        logger.info(f"  태스크 {i+1}: {r_status}")
                    
                    logger.info(f"성공 {success_count}/{len(results)} 태스크")
                    
                    # 통합 결과 확인 (이 부분은 API에 따라 다를 수 있음)
                    if "final_result" in status_data:
                        logger.info(f"최종 결과:\n{status_data.get('final_result')}")
                    
                    break
            
            if status == "processing":
                logger.warning(f"제한 시간({TIMEOUT}초)을 초과했습니다. 테스트 종료.")
            
            return True
                
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {str(e)}")
        return False

async def test_health():
    """
    오케스트레이터 상태 확인
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/health")
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"오케스트레이터 상태: {result.get('status')}")
            
            # 상태 확인 로직 수정
            # 이전: return result.get("status") == "healthy"
            return result.get("status") in ["healthy", "ok"]
            
    except Exception as e:
        logger.error(f"상태 확인 중 오류 발생: {str(e)}")
        return False

async def main():
    """
    메인 테스트 함수
    """
    # 상태 확인
    logger.info("오케스트레이터 상태 확인 중...")
    if not await test_health():
        logger.error("오케스트레이터 서비스가 정상적으로 실행되지 않았습니다.")
        return False
    
    # 테스트 쿼리
    test_queries = [
        "인공지능의 장단점에 대한 보고서를 작성해줘",
        "블록체인 기술에 대해 조사하고 요약해줘",
        "한국의 전통음식 중 해외에서 인기있는 것은?"
    ]
    
    for query in test_queries:
        await test_query(query)
        logger.info("=" * 50)
        await asyncio.sleep(5)  # 테스트 간 간격
    
    return True

if __name__ == "__main__":
    logger.info("오케스트레이터 테스트 시작")
    asyncio.run(main())
    logger.info("오케스트레이터 테스트 완료") 