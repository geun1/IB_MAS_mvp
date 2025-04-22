import httpx
import asyncio
import time
import json
import logging
from pprint import pprint

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("param_inference_test")

# 테스트 설정
BROKER_URL = "http://localhost:8002"

async def test_param_inference_direct():
    """파라미터 추론 직접 테스트 (inference API)"""
    logger.info("=== 파라미터 추론 직접 테스트 시작 ===")
    
    # 테스트 1: 문서 작성 태스크 (어조와 길이만 누락)
    writer_test = {
        "task_description": "인공지능의 역사와 발전 과정에 대한 문서를 작성해주세요",
        "param_schemas": [
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
                "required": True,
                "enum": ["formal", "casual", "technical", "neutral"]
            },
            {
                "name": "length",
                "description": "문서 길이(단어 수)",
                "type": "number",
                "required": True,
                "default": 500
            }
        ],
        "existing_params": {
            "topic": "인공지능의 역사와 발전 과정"
        }
    }
    
    async with httpx.AsyncClient() as client:
        # 테스트 1 실행
        logger.info("문서 작성 태스크 파라미터 추론 테스트...")
        response = await client.post(f"{BROKER_URL}/test/infer-simple", json=writer_test)
        
        if response.status_code != 200:
            logger.error(f"파라미터 추론 API 호출 실패: {response.status_code} - {response.text}")
            return False
            
        result = response.json()
        logger.info("추론 결과:")
        pprint(result["inferred_params"])
        
        # 추론 결과 검증
        inferred = result["inferred_params"]
        if "tone" not in inferred or "length" not in inferred:
            logger.error("누락된 필수 파라미터가 추론되지 않았습니다")
            return False
            
        if inferred["tone"] not in ["formal", "casual", "technical", "neutral"]:
            logger.error(f"추론된 tone 값이 열거형 제약조건을 벗어납니다: {inferred['tone']}")
            return False
            
        if not isinstance(inferred["length"], (int, float)) or inferred["length"] <= 0:
            logger.error(f"추론된 length 값이 유효하지 않습니다: {inferred['length']}")
            return False
            
        logger.info("파라미터 추론 검증 성공!")
        return True

async def test_param_inference_with_task():
    """태스크 처리를 통한 파라미터 추론 테스트"""
    logger.info("=== 태스크 처리를 통한 파라미터 추론 테스트 시작 ===")
    
    # 의도적으로 필수 파라미터 누락
    task_request = {
        "role": "writer",
        "params": {
            "topic": "인공지능의 미래 전망"
            # tone과 length는 의도적으로 누락
        },
        "conversation_id": f"test_param_{int(time.time())}"
    }
    
    async with httpx.AsyncClient() as client:
        # 태스크 생성 - /task에서 /tasks로 변경
        logger.info("누락된 파라미터가 있는 태스크 생성 중...")
        response = await client.post(f"{BROKER_URL}/tasks", json=task_request)
        
        if response.status_code != 200:
            logger.error(f"태스크 생성 실패: {response.status_code} - {response.text}")
            return False
            
        result = response.json()
        task_id = result["task_id"]
        logger.info(f"태스크 생성됨: {task_id}")
        
        # 태스크 완료 대기 및 결과 확인
        logger.info("태스크 완료 대기 중...")
        completed = False
        max_wait = 60  # 최대 60초 대기
        start_time = time.time()
        
        while not completed and time.time() - start_time < max_wait:
            await asyncio.sleep(3)
            
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
                    return True
                else:
                    logger.error(f"태스크 실패: {task_info.get('error', '알 수 없음')}")
                    return False
                    
        if not completed:
            logger.warning("태스크가 시간 내에 완료되지 않았습니다")
            return False

async def main():
    """테스트 실행 메인 함수"""
    # 테스트 1: 직접 추론 API 테스트
    direct_result = await test_param_inference_direct()
    if direct_result:
        logger.info("✅ 파라미터 추론 직접 테스트 성공!")
    else:
        logger.error("❌ 파라미터 추론 직접 테스트 실패")
    
    # 테스트 2: 태스크 처리를 통한 파라미터 추론 테스트
    task_result = await test_param_inference_with_task()
    if task_result:
        logger.info("✅ 태스크 처리를 통한 파라미터 추론 테스트 성공!")
    else:
        logger.error("❌ 태스크 처리를 통한 파라미터 추론 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main()) 