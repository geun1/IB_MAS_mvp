"""
오케스트레이터 고급 테스트 스크립트
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
TIMEOUT = 240  # 초 (복잡한 요청은 더 긴 시간이 필요할 수 있음)

async def test_query(query: str, description: str = ""):
    """
    오케스트레이터 쿼리 테스트
    """
    logger.info(f"테스트 시작: '{query}'")
    if description:
        logger.info(f"설명: {description}")
    
    try:
        # 쿼리 요청
        async with httpx.AsyncClient() as client:
            start_time = time.time()
            
            response = await client.post(
                f"{ORCHESTRATOR_URL}/query",
                json={"query": query},
                timeout=60.0  # 더 긴 타임아웃 적용
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
            
            # 태스크의 복잡성 측정
            roles = set(task.get('role') for task in tasks)
            logger.info(f"필요한 역할 유형 수: {len(roles)}")
            logger.info(f"태스크 체인 복잡성: {compute_task_complexity(tasks)}")
            
            # 처리 완료 대기
            status = "processing"
            while status == "processing" and (time.time() - start_time) < TIMEOUT:
                await asyncio.sleep(10)  # 더 긴 간격으로 폴링
                
                # 상태 확인
                status_response = await client.get(f"{ORCHESTRATOR_URL}/conversation/{conversation_id}")
                status_response.raise_for_status()
                status_data = status_response.json()
                
                status = status_data.get("status")
                elapsed = int(time.time() - start_time)
                logger.info(f"대화 상태: {status} (경과 시간: {elapsed}초)")
                
                # 태스크별 상태 확인
                if "results" in status_data:
                    completed = sum(1 for r in status_data["results"] if r.get("status") == "completed")
                    logger.info(f"진행률: {completed}/{len(tasks)} 태스크 완료")
                
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
                    
                    # 통합 결과 확인
                    if "final_result" in status_data:
                        final_result = status_data.get("final_result", "")
                        logger.info(f"최종 결과 길이: {len(final_result)} 문자")
                        logger.info(f"최종 결과 (앞부분):\n{final_result[:500]}...")
                    
                    break
            
            if status == "processing":
                logger.warning(f"제한 시간({TIMEOUT}초)을 초과했습니다. 테스트 종료.")
            
            logger.info(f"총 소요 시간: {int(time.time() - start_time)}초")
            return True
                
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {str(e)}")
        return False

def compute_task_complexity(tasks):
    """태스크 구조의 복잡성 계산"""
    # 태스크 간 의존성 복잡도
    dependencies = sum(len(task.get('depends_on', [])) for task in tasks)
    # 각 태스크 설명의 평균 길이
    avg_desc_len = sum(len(task.get('description', '')) for task in tasks) / max(len(tasks), 1)
    # 파라미터 복잡도
    param_complexity = sum(len(task.get('params', {})) for task in tasks)
    
    return {
        'dependencies': dependencies,
        'avg_description_length': avg_desc_len,
        'parameter_count': param_complexity
    }

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
            return result.get("status") in ["healthy", "ok"]
    except Exception as e:
        logger.error(f"상태 확인 중 오류 발생: {str(e)}")
        return False

# 복잡한 테스트 쿼리 목록
COMPLEX_QUERIES = [
    {
        "query": "최근 5년간 인공지능 기술의 발전 동향과 윤리적 문제를 분석하고, 향후 10년간 예상되는 변화와 대응 방안을 제시하는 포괄적인 보고서를 작성해주세요.",
        "description": "다단계 연구 및 분석이 필요한 복잡한 보고서 작성 요청"
    },
    {
        "query": "기후 변화가 농업 생산성, 생물 다양성, 해수면 상승에 미치는 영향을 각각 분석하고, 지역별 대응 전략과 국제 협력 방안을 포함한 종합적인 대책을 제안해주세요.",
        "description": "여러 도메인에 걸친 복합적 문제 분석 및 해결책 요청"
    },
    {
        "query": "블록체인 기술의 금융, 공공서비스, 공급망 관리 분야 적용 사례를 분석하고, 각 분야별 장단점과 기술적 한계, 향후 발전 가능성을 비교하는 심층 보고서를 작성해주세요.",
        "description": "다양한 분야에 걸친 비교 분석 보고서"
    },
    {
        "query": "한국 전통문화와 현대 기술을 융합한 새로운 문화 콘텐츠 기획안을 준비해주세요. 역사적 배경 조사, 기술 적용 가능성 분석, 시장성 평가, 구체적인 제작 계획을 포함해야 합니다.",
        "description": "창의적 기획과 다양한 분석이 필요한 복합 요청"
    },
    {
        "query": "대도시의 교통 체증, 주차 문제, 대기 오염을 동시에 해결할 수 있는 스마트시티 솔루션을 조사하고, 기술적 구현 방법, 비용 분석, 예상 효과, 실제 적용 사례를 포함한 보고서를 작성해주세요.",
        "description": "도시 문제에 대한 복합적 솔루션 분석 요청"
    }
]

async def main():
    """
    메인 테스트 함수
    """
    # 상태 확인
    logger.info("오케스트레이터 상태 확인 중...")
    if not await test_health():
        logger.error("오케스트레이터 서비스가 정상적으로 실행되지 않았습니다.")
        return False
    
    # 테스트 쿼리 실행
    total_success = 0
    
    for query_info in COMPLEX_QUERIES:
        success = await test_query(query_info["query"], query_info["description"])
        if success:
            total_success += 1
        logger.info("=" * 80)
        await asyncio.sleep(10)  # 테스트 간 간격 증가
    
    logger.info(f"테스트 결과 요약: {total_success}/{len(COMPLEX_QUERIES)} 성공")
    return True

if __name__ == "__main__":
    logger.info("오케스트레이터 고급 테스트 시작")
    asyncio.run(main())
    logger.info("오케스트레이터 고급 테스트 완료") 