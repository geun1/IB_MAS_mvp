import httpx
import asyncio
import json
import uuid
import logging
import sys
import time

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agent_register")

# 설정
REGISTRY_URL = "http://localhost:8000"

# 에이전트 정의
TEST_AGENTS = [
    {
        "id": f"writer_agent_{uuid.uuid4().hex[:8]}",
        "role": "writer",
        "description": "테스트용 문서 작성 에이전트",
        "params": [
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
                "required": False,
                "enum": ["formal", "casual", "technical", "neutral"],
                "default": "neutral"
            },
            {
                "name": "length",
                "description": "문서의 길이(단어 수)",
                "type": "integer",
                "required": False,
                "minimum": 100,
                "maximum": 2000,
                "default": 500
            }
        ],
        "endpoint": "http://localhost:8010/process",  # 실제 엔드포인트 URL로 변경
        "status": "available",
        "load": 0.2,
        "active_tasks": 0
    },
    {
        "id": f"search_agent_{uuid.uuid4().hex[:8]}",
        "role": "search",
        "description": "테스트용 검색 에이전트",
        "params": [
            {
                "name": "query",
                "description": "검색 쿼리",
                "type": "string",
                "required": True
            },
            {
                "name": "limit",
                "description": "결과 제한 수",
                "type": "integer",
                "required": False,
                "minimum": 1,
                "maximum": 20,
                "default": 5
            }
        ],
        "endpoint": "http://localhost:8011/process",  # 실제 엔드포인트 URL로 변경
        "status": "available",
        "load": 0.1,
        "active_tasks": 0
    }
]

async def register_agent(agent_data):
    """에이전트 등록"""
    logger.info(f"에이전트 '{agent_data['id']}' ({agent_data['role']}) 등록 중...")
    
    # 등록 전에 중복 여부 확인
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            check_response = await client.get(f"{REGISTRY_URL}/agents?id={agent_data['id']}")
            
            if check_response.status_code == 200:
                existing_agents = check_response.json().get("agents", [])
                if existing_agents:
                    logger.info(f"에이전트 '{agent_data['id']}'가 이미 등록되어 있습니다.")
                    return True
    except Exception as e:
        logger.warning(f"에이전트 중복 확인 중 오류: {str(e)}")
    
    # 에이전트 등록
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.debug(f"등록 데이터: {json.dumps(agent_data, indent=2)}")
            
            response = await client.post(
                f"{REGISTRY_URL}/register", 
                json=agent_data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info(f"✅ 에이전트 '{agent_data['id']}' 등록 성공")
                return True
            else:
                logger.error(f"❌ 에이전트 '{agent_data['id']}' 등록 실패: {response.status_code} - {response.text}")
                
                # 에러 응답 확인 및 디버깅
                try:
                    error_detail = response.json()
                    logger.error(f"에러 세부정보: {error_detail}")
                except:
                    logger.error(f"원본 응답: {response.text}")
                
                return False
                
    except Exception as e:
        logger.error(f"에이전트 '{agent_data['id']}' 등록 중 예외 발생: {str(e)}")
        return False

async def check_registry_connection():
    """레지스트리 서비스 연결 확인"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{REGISTRY_URL}/health")
            if response.status_code == 200:
                logger.info("✅ 레지스트리 서비스 연결 성공")
                return True
            else:
                logger.error(f"❌ 레지스트리 서비스 응답 오류: {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"❌ 레지스트리 서비스 연결 실패: {str(e)}")
        return False

async def main():
    """메인 함수"""
    logger.info("=== 테스트용 에이전트 등록 시작 ===")
    
    # 레지스트리 서비스 연결 확인
    if not await check_registry_connection():
        logger.error("레지스트리 서비스에 연결할 수 없습니다. 서비스가 실행 중인지 확인하세요.")
        return 1
    
    # 에이전트 등록
    success_count = 0
    for agent in TEST_AGENTS:
        if await register_agent(agent):
            success_count += 1
    
    # 결과 보고
    logger.info(f"=== 에이전트 등록 완료: {success_count}/{len(TEST_AGENTS)} 성공 ===")
    
    # 잠시 대기 (등록 처리 완료 대기)
    logger.info("등록된 에이전트 목록 확인 중...")
    await asyncio.sleep(2)
    
    # 등록된 에이전트 확인
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{REGISTRY_URL}/agents")
            if response.status_code == 200:
                agents = response.json().get("agents", [])
                logger.info(f"현재 등록된 에이전트: {len(agents)}개")
                for agent in agents:
                    logger.info(f"- {agent.get('id')} ({agent.get('role')}): {agent.get('status')}")
            else:
                logger.error(f"에이전트 목록 조회 실패: {response.status_code}")
    except Exception as e:
        logger.error(f"에이전트 목록 조회 중 오류: {str(e)}")
    
    return 0 if success_count == len(TEST_AGENTS) else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 