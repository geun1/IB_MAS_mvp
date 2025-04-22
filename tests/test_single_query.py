"""
오케스트레이터 단일 쿼리 테스트 스크립트
"""
import asyncio
import httpx
import logging
import json
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 서버 URL
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")

async def test_complex_query():
    """복잡한 쿼리 테스트"""
    # 테스트할 복잡한 쿼리
    complex_query = """
    디지털 트랜스포메이션이 금융, 의료, 교육 산업에 미치는 영향을 비교 분석하고, 
    각 산업별 성공적인 디지털 전환 사례 2개씩을 상세히 조사해 주세요. 
    또한 이 세 산업에서 공통적으로 나타나는 디지털 전환의 장애 요소와 
    이를 극복하기 위한 전략적 방안을 제시해 주세요.
    """
    
    try:
        # 1. 쿼리 요청
        logger.info(f"쿼리 전송 중: {complex_query[:100]}...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/query",
                json={"query": complex_query}
            )
            response.raise_for_status()
            result = response.json()
            
            # 응답 정보 출력
            conversation_id = result.get("conversation_id")
            logger.info(f"응답 받음 - 대화 ID: {conversation_id}")
            
            # 2. 태스크 정보 출력
            tasks = result.get("tasks", [])
            logger.info(f"\n==== 생성된 태스크 ({len(tasks)}개) ====")
            
            # 역할별로 태스크 그룹화
            role_tasks = {}
            for task in tasks:
                role = task.get("role", "unknown")
                if role not in role_tasks:
                    role_tasks[role] = []
                role_tasks[role].append(task)
            
            # 역할별 태스크 출력
            for role, tasks_list in role_tasks.items():
                logger.info(f"\n역할: {role} ({len(tasks_list)}개 태스크)")
                for i, task in enumerate(tasks_list):
                    logger.info(f"  {i+1}. {task.get('description', '설명 없음')}")
                    
                    # 파라미터 정보 출력
                    params = task.get("params", {})
                    if params:
                        logger.info(f"     파라미터: {json.dumps(params, ensure_ascii=False, indent=2)}")
            
            logger.info("\n테스트 완료! 태스크 분해 결과를 확인하세요.")
            return True
            
    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_complex_query()) 