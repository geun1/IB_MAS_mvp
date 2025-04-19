import httpx
import asyncio
import logging
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("broker_api_check")

# 브로커 URL
BROKER_URL = "http://localhost:8001"

# 테스트할 API 경로 목록
TEST_PATHS = [
    "/health",
    "/query",
    "/tasks",
    "/task",
    "/api/tasks",
    "/api/task",
    "/api/v1/tasks",
    "/api/v1/task"
]

async def check_broker_api_paths():
    """브로커 API 경로 확인"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        logger.info("=== 브로커 API 경로 테스트 ===")
        
        # 각 경로 테스트
        for path in TEST_PATHS:
            full_url = f"{BROKER_URL}{path}"
            try:
                response = await client.get(full_url)
                logger.info(f"GET {path}: {response.status_code}")
                
                # 응답 상세 정보
                if response.status_code < 500:  # 서버 오류가 아닌 경우만 표시
                    try:
                        response_data = response.json()
                        logger.info(f"  응답: {json.dumps(response_data)[:100]}...")
                    except:
                        logger.info(f"  응답: {response.text[:100]}...")
            except Exception as e:
                logger.error(f"GET {path} 오류: {str(e)}")
                
        # POST 요청 테스트 (태스크 생성)
        logger.info("\n=== 브로커 태스크 생성 테스트 ===")
        
        # 테스트할 POST 경로들
        post_paths = ["/task", "/tasks", "/api/task", "/api/tasks", "/api/v1/task", "/api/v1/tasks"]
        
        # 간단한 테스트 태스크 데이터
        test_task = {
            "role": "test",
            "params": {
                "test_param": "test_value"
            },
            "conversation_id": "test_conversation"
        }
        
        for path in post_paths:
            full_url = f"{BROKER_URL}{path}"
            try:
                response = await client.post(full_url, json=test_task)
                logger.info(f"POST {path}: {response.status_code}")
                
                # 응답 상세 정보
                if response.status_code < 500:  # 서버 오류가 아닌 경우만 표시
                    try:
                        response_data = response.json()
                        logger.info(f"  응답: {json.dumps(response_data)}")
                    except:
                        logger.info(f"  응답: {response.text[:100]}...")
                        
                # 성공 시 해당 경로가 올바른 것
                if response.status_code == 200 or response.status_code == 201:
                    logger.info(f"✅ 태스크 API 경로 발견: {path}")
                    return path
            except Exception as e:
                logger.error(f"POST {path} 오류: {str(e)}")
                
        logger.warning("❌ 유효한 태스크 API 경로를 찾지 못했습니다.")
        return None

async def main():
    correct_path = await check_broker_api_paths()
    
    if correct_path:
        logger.info(f"\n모든 테스트에서 '{correct_path}'를 사용하세요.")
    else:
        logger.error("\n브로커 서비스의 태스크 API 구현을 확인하세요.")

if __name__ == "__main__":
    asyncio.run(main()) 