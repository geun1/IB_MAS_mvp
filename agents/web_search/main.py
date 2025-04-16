from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
import os
import json
from typing import Dict, List, Optional, Any
import time

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="Web Search Agent")

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")

# 모델 정의
class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    results: List[Dict[str, str]]

# 초기 등록을 위한 변수들
AGENT_ID = "web_search_agent_1"
AGENT_ROLE = "web_search"
AGENT_DESCRIPTION = "웹에서 정보를 검색하고 관련 결과를 반환합니다."

# 등록 태스크
async def register_agent():
    try:
        agent_data = {
            "id": AGENT_ID,
            "role": AGENT_ROLE,
            "description": AGENT_DESCRIPTION,
            "params": [
                {
                    "name": "query",
                    "description": "검색할 쿼리 또는 키워드",
                    "required": True,
                    "type": "string"
                }
            ],
            "type": "function"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{REGISTRY_URL}/register",
                json=agent_data
            )
            print(f"Agent registration response: {response.status_code}, {response.text}")
            
    except Exception as e:
        print(f"Failed to register agent: {str(e)}")

# 하트비트 보내기
async def send_heartbeat():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{REGISTRY_URL}/heartbeat/{AGENT_ROLE}/{AGENT_ID}"
                )
                print(f"Heartbeat response: {response.status_code}")
        except Exception as e:
            print(f"Failed to send heartbeat: {str(e)}")
        
        # 20초마다 하트비트 전송
        await asyncio.sleep(20)

# 시작 시 등록
@app.on_event("startup")
async def startup_event():
    # 에이전트 등록
    await register_agent()
    
    # 하트비트 태스크 시작
    asyncio.create_task(send_heartbeat())

# 검색 API
@app.post("/search")
async def search(request: SearchRequest):
    try:
        # 실제로는 검색 API를 호출해야 함
        # 여기서는 간단한 응답 반환
        mock_results = [
            {
                "title": f"검색 결과 1: {request.query}",
                "snippet": f"{request.query}에 관한 첫 번째 검색 결과입니다.",
                "url": f"https://example.com/result1?q={request.query}"
            },
            {
                "title": f"검색 결과 2: {request.query}",
                "snippet": f"{request.query}에 관한 두 번째 검색 결과입니다.",
                "url": f"https://example.com/result2?q={request.query}"
            }
        ]
        
        return {"results": mock_results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# 작업 실행 API
@app.post("/run")
async def run_task(task: Dict[str, Any]):
    try:
        query = task.get("params", {}).get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")
            
        # 검색 실행
        search_request = SearchRequest(query=query)
        result = await search(search_request)
        
        return {
            "status": "success",
            "result": result
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")

# 서버 상태 확인용 API
@app.get("/")
async def root():
    return {"status": "online", "service": "Web Search Agent", "id": AGENT_ID, "role": AGENT_ROLE}

# 서버 상태 확인용 API
@app.get("/health")
async def health():
    return {"status": "healthy"}

# asyncio 임포트
import asyncio
