import httpx
import asyncio
import logging
import json
from pprint import pprint

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("api_debug")

# 서비스 URL
REGISTRY_URL = "http://localhost:8000"
BROKER_URL = "http://localhost:8001"

async def check_api_endpoints():
    """API 엔드포인트 확인"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 레지스트리 API 확인
        logger.info("=== 레지스트리 API 경로 확인 ===")
        
        # 상태 확인
        try:
            response = await client.get(f"{REGISTRY_URL}/health")
            logger.info(f"레지스트리 상태 확인: {response.status_code}")
            if response.status_code == 200:
                logger.info(f"응답: {response.text}")
        except Exception as e:
            logger.error(f"레지스트리 상태 확인 오류: {str(e)}")
        
        # 에이전트 목록 확인
        try:
            response = await client.get(f"{REGISTRY_URL}/agents")
            logger.info(f"에이전트 목록 확인: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"에이전트 수: {len(data.get('agents', []))}")
        except Exception as e:
            logger.error(f"에이전트 목록 확인 오류: {str(e)}")
        
        # Swagger/OpenAPI 문서 확인
        try:
            response = await client.get(f"{REGISTRY_URL}/openapi.json")
            logger.info(f"OpenAPI 문서 확인: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                paths = list(data.get("paths", {}).keys())
                logger.info(f"사용 가능한 API 경로: {paths}")
        except Exception as e:
            logger.error(f"OpenAPI 문서 확인 오류: {str(e)}")
            
        logger.info("\n=== 브로커 API 경로 확인 ===")
        
        # 브로커 상태 확인
        try:
            response = await client.get(f"{BROKER_URL}/health")
            logger.info(f"브로커 상태 확인: {response.status_code}")
            if response.status_code == 200:
                logger.info(f"응답: {response.text}")
        except Exception as e:
            logger.error(f"브로커 상태 확인 오류: {str(e)}")
        
        # 브로커 API 경로 확인
        try:
            response = await client.get(f"{BROKER_URL}/openapi.json")
            logger.info(f"브로커 OpenAPI 문서 확인: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                paths = list(data.get("paths", {}).keys())
                logger.info(f"사용 가능한 API 경로: {paths}")
                
                # 태스크 관련 경로 찾기
                task_paths = [p for p in paths if "task" in p.lower()]
                logger.info(f"태스크 관련 API 경로: {task_paths}")
        except Exception as e:
            logger.error(f"브로커 OpenAPI 문서 확인 오류: {str(e)}")

async def main():
    await check_api_endpoints()

if __name__ == "__main__":
    asyncio.run(main()) 