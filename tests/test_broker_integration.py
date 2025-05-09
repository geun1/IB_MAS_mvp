import httpx
import asyncio
import time
import json
import logging
import uuid
from pprint import pprint

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("integration_test")

# 테스트 설정
BROKER_URL = "http://localhost:8001"
REGISTRY_URL = "http://localhost:8000"

async def register_test_agent():
    """테스트용 에이전트 등록"""
    logger.info("테스트용 에이전트 등록 중...")
    
    # 고유 ID 생성
    agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"
    
    # 테스트 에이전트 정의
    test_agent = {
        "id": agent_id,
        "role": "calculator",
        "description": "숫자 계산을 수행하는 에이전트",
        "params": [
            {
                "name": "expression",
                "description": "계산할 수식",
                "type": "string",
                "required": True
            },
            {
                "name": "precision",
                "description": "결과의 소수점 자릿수",
                "type": "number",
                "required": False,
                "default": 2
            }
        ],
        "type": "function",
        "endpoint": "http://localhost:9000/calculate",  # 실제로는 모의 엔드포인트
        "status": "available",
        "load": 0.0,
        "active_tasks": 0,
        "capabilities": ["계산", "수학"]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{REGISTRY_URL}/register", json=test_agent)
        
        if response.status_code != 200:
            logger.error(f"에이전트 등록 실패: {response.status_code} - {response.text}")
            return None
            
        result = response.json()
        logger.info(f"에이전트 등록 성공: {agent_id}")
        return agent_id

async def test_agent_statistics_update():
    """에이전트 통계 업데이트 테스트"""
    logger.info("=== 에이전트 통계 업데이트 테스트 시작 ===")
    
    # 1. 테스트 에이전트 등록
    agent_id = await register_test_agent()
    if not agent_id:
        logger.error("테스트 에이전트 등록 실패")
        return False
        
    # 2. 초기 통계 확인
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{REGISTRY_URL}/agents/{agent_id}/statistics")
        
        if response.status_code != 200:
            logger.error(f"초기 통계 조회 실패: {response.status_code}")
            return False
            
        initial_stats = response.json()
        logger.info("초기 에이전트 통계:")
        pprint(initial_stats)
        
        # 3. 수동으로 태스크 통계 업데이트
        logger.info("태스크 통계 업데이트 요청 중...")
        stat_update = {
            "status": "completed",
            "execution_time": 1.5
        }
        
        update_response = await client.post(
            f"{REGISTRY_URL}/agents/{agent_id}/taREMOVEDstats", 
            json=stat_update
        )
        
        if update_response.status_code != 200:
            logger.error(f"통계 업데이트 실패: {update_response.status_code}")
            return False
            
        # 4. 업데이트된 통계 확인
        logger.info("업데이트된 통계 확인 중...")
        response = await client.get(f"{REGISTRY_URL}/agents/{agent_id}/statistics")
        
        if response.status_code != 200:
            logger.error(f"업데이트 후 통계 조회 실패: {response.status_code}")
            return False
            
        updated_stats = response.json()
        logger.info("업데이트된 에이전트 통계:")
        pprint(updated_stats)
        
        # 5. 통계 변경 확인
        if updated_stats["total_tasks"] <= initial_stats["total_tasks"]:
            logger.error("총 태스크 수가 증가하지 않았습니다")
            return False
            
        if updated_stats["completed_tasks"] <= initial_stats["completed_tasks"]:
            logger.error("완료된 태스크 수가 증가하지 않았습니다")
            return False
            
        if updated_stats["avg_execution_time"] <= 0:
            logger.error("평균 실행 시간이 업데이트되지 않았습니다")
            return False
            
        logger.info("에이전트 통계 업데이트 테스트 성공!")
        return True

async def main():
    """테스트 실행 메인 함수"""
    # 테스트 1: 에이전트 통계 업데이트 테스트
    stats_result = await test_agent_statistics_update()
    if stats_result:
        logger.info("✅ 에이전트 통계 업데이트 테스트 성공!")
    else:
        logger.error("❌ 에이전트 통계 업데이트 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main()) 