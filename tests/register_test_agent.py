import httpx
import asyncio
import json

async def register_agent_with_params():
    """파라미터 스키마가 포함된 테스트 에이전트 등록"""
    registry_url = "http://localhost:8000"
    
    # 웹 검색 에이전트 등록
    web_search_agent = {
        "id": "web_search_test_agent",
        "role": "web_search",
        "description": "웹에서 정보를 검색하고 관련 결과를 반환합니다.",
        "params": [
            {
                "name": "query",
                "description": "검색할 쿼리 또는 키워드",
                "type": "string",
                "required": True
            },
            {
                "name": "num_results",
                "description": "반환할 검색 결과 수",
                "type": "number",
                "required": False,
                "default": 5
            },
            {
                "name": "language",
                "description": "검색 결과 언어",
                "type": "string",
                "required": False,
                "default": "ko",
                "enum": ["ko", "en", "jp", "cn"]
            }
        ],
        "type": "function",
        "endpoint": "http://agent_web_search:8000/run",
        "status": "available",
        "load": 0.0,
        "active_tasks": 0,
        "capabilities": ["검색", "정보 수집"]
    }
    
    # 문서 작성 에이전트 등록
    writer_agent = {
        "id": "writer_test_agent",
        "role": "writer",
        "description": "주어진 주제에 대한 문서를 작성합니다.",
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
                "default": "neutral",
                "enum": ["formal", "casual", "technical", "neutral"]
            },
            {
                "name": "length",
                "description": "문서 길이(단어 수)",
                "type": "number",
                "required": False,
                "default": 500
            }
        ],
        "type": "function",
        "endpoint": "http://agent_writer:8000/run",
        "status": "available",
        "load": 0.0,
        "active_tasks": 0,
        "capabilities": ["문서 작성", "요약", "편집"]
    }
    
    async with httpx.AsyncClient() as client:
        # 웹 검색 에이전트 등록
        response1 = await client.post(f"{registry_url}/register", json=web_search_agent)
        print(f"웹 검색 에이전트 등록 결과: {response1.status_code}")
        print(json.dumps(response1.json(), indent=2, ensure_ascii=False))
        
        # 문서 작성 에이전트 등록
        response2 = await client.post(f"{registry_url}/register", json=writer_agent)
        print(f"문서 작성 에이전트 등록 결과: {response2.status_code}")
        print(json.dumps(response2.json(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(register_agent_with_params()) 