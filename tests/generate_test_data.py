import httpx
import asyncio
import json
import random
import uuid
import time
import logging
from typing import List

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_data_generator")

# 설정
REGISTRY_URL = "http://localhost:8000"
BROKER_URL = "http://localhost:8001"

# 샘플 에이전트 정의
SAMPLE_AGENTS = [
    {
        "role": "writer",
        "description": "다양한 주제에 대한 문서를 작성하는 에이전트",
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
        "endpoint": "http://agent-writer:8000/run"
    },
    {
        "role": "search",
        "description": "웹에서 정보를 검색하는 에이전트",
        "params": [
            {
                "name": "query",
                "description": "검색 쿼리",
                "type": "string",
                "required": True
            },
            {
                "name": "num_results",
                "description": "검색 결과 수",
                "type": "number",
                "required": False,
                "default": 5
            }
        ],
        "endpoint": "http://agent-search:8000/run"
    },
    {
        "role": "calculator",
        "description": "수학 연산을 수행하는 에이전트",
        "params": [
            {
                "name": "expression",
                "description": "계산할 수식",
                "type": "string",
                "required": True
            }
        ],
        "endpoint": "http://agent-calculator:8000/run"
    }
]

# 샘플 태스크 생성
SAMPLE_TASKS = [
    {
        "role": "writer",
        "params": {
            "topic": "인공지능의 미래",
            "tone": "formal",
            "length": 500
        }
    },
    {
        "role": "writer",
        "params": {
            "topic": "클라우드 컴퓨팅 기술 동향",
            "tone": "technical",
            "length": 800
        }
    },
    {
        "role": "search",
        "params": {
            "query": "최신 딥러닝 프레임워크",
            "num_results": 5
        }
    },
    {
        "role": "search",
        "params": {
            "query": "인공지능 윤리적 고려사항",
            "num_results": 10
        }
    },
    {
        "role": "calculator",
        "params": {
            "expression": "2 * (3 + 4) / 2"
        }
    }
]

async def register_test_agents(num_agents: int = 3) -> List[str]:
    """테스트용 에이전트 등록"""
    logger.info(f"{num_agents}개의 테스트 에이전트 등록 중...")
    agent_ids = []
    
    async with httpx.AsyncClient() as client:
        for i in range(num_agents):
            # 무작위로 에이전트 템플릿 선택
            template = random.choice(SAMPLE_AGENTS)
            
            # 고유 ID 생성
            agent_id = f"test_{template['role']}_{uuid.uuid4().hex[:8]}"
            
            # 에이전트 데이터 생성
            agent_data = {
                "id": agent_id,
                "role": template["role"],
                "description": template["description"],
                "params": template["params"],
                "type": "function",
                "endpoint": template["endpoint"],
                "status": "available",
                "load": 0.0,
                "active_tasks": 0
            }
            
            # 에이전트 등록
            response = await client.post(f"{REGISTRY_URL}/register", json=agent_data)
            
            if response.status_code == 200:
                logger.info(f"에이전트 등록 성공: {agent_id} ({template['role']})")
                agent_ids.append(agent_id)
            else:
                logger.error(f"에이전트 등록 실패: {response.status_code} - {response.text}")
                
    logger.info(f"{len(agent_ids)}개의 에이전트가 성공적으로 등록되었습니다")
    return agent_ids

async def generate_test_tasks(num_tasks: int = 10) -> List[str]:
    """테스트용 태스크 생성"""
    logger.info(f"{num_tasks}개의 테스트 태스크 생성 중...")
    task_ids = []
    
    async with httpx.AsyncClient() as client:
        for i in range(num_tasks):
            # 무작위로 태스크 템플릿 선택
            template = random.choice(SAMPLE_TASKS)
            
            # 태스크 데이터 생성
            task_data = {
                "role": template["role"],
                "params": template["params"],
                "conversation_id": f"test_{int(time.time())}_{i}"
            }
            
            # 태스크 생성
            response = await client.post(f"{BROKER_URL}/task", json=task_data)
            
            if response.status_code == 200:
                result = response.json()
                task_id = result["task_id"]
                logger.info(f"태스크 생성 성공: {task_id} ({template['role']})")
                task_ids.append(task_id)
            else:
                logger.error(f"태스크 생성 실패: {response.status_code} - {response.text}")
                
    logger.info(f"{len(task_ids)}개의 태스크가 성공적으로 생성되었습니다")
    return task_ids

async def main():
    # 테스트 에이전트 등록
    agent_ids = await register_test_agents(5)
    
    if not agent_ids:
        logger.error("테스트 에이전트 등록에 실패했습니다")
        return
        
    # 잠시 대기
    logger.info("에이전트 등록 완료. 태스크 생성 전 5초 대기 중...")
    await asyncio.sleep(5)
    
    # 테스트 태스크 생성
    task_ids = await generate_test_tasks(10)
    
    if not task_ids:
        logger.error("테스트 태스크 생성에 실패했습니다")
        return
        
    logger.info("테스트 데이터 생성 완료!")
    logger.info(f"등록된 에이전트: {len(agent_ids)}개")
    logger.info(f"생성된 태스크: {len(task_ids)}개")

if __name__ == "__main__":
    asyncio.run(main()) 