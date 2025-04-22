from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
import os
import json
from typing import Dict, List, Optional, Any
import time
import psutil
from datetime import datetime
import logging

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Web Search Agent API",
    description="웹 검색 기능을 제공하는 에이전트 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "syntaxHighlight": {"theme": "nord"},
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    }
)

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # 기본값 20초

# 모델 정의
class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    results: List[Dict[str, str]]

# 초기 등록을 위한 변수들
AGENT_ID = "web_search_agent_1"
AGENT_ROLE = "web_search"
AGENT_DESCRIPTION = "웹에서 정보를 검색하고 관련 결과를 반환합니다."

# 상태 초기화
app.state.active_tasks = set()  # 활성 작업 추적을 위한 set

# 등록 태스크
async def register_agent():
    """레지스트리에 에이전트 등록"""
    try:
        # 컨테이너 외부에서 접근 가능한 엔드포인트 구성
        container_name = os.getenv("CONTAINER_NAME", "web_search_agent")
        port = int(os.getenv("PORT", "8000"))
        
        # 포트가 기본 8000이 아닌 경우를 처리
        if port != 8000:
            service_endpoint = f"http://{container_name}:{port}"
        else:
            service_endpoint = f"http://{container_name}:8000"
            
        # 에이전트 데이터 준비
        agent_data = {
            "id": AGENT_ID,
            "role": AGENT_ROLE,
            "description": AGENT_DESCRIPTION,
            "endpoint": service_endpoint,  # 엔드포인트 추가
            "type": "function",
            "params": [
                {
                    "name": "query",
                    "description": "검색할 쿼리 또는 키워드",
                    "required": True,
                    "type": "string"
                }
            ]
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
    """Registry에 하트비트 전송"""
    while True:
        try:
            heartbeat_data = {
                "status": "active",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "memory_usage": psutil.virtual_memory().percent,
                    "cpu_usage": psutil.cpu_percent(),
                    "active_tasks": 0  # 현재는 단순히 0으로 설정
                },
                "version": "1.0.0"
            }
            
            url = f"{REGISTRY_URL}/heartbeat/{AGENT_ROLE}/{AGENT_ID}"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=heartbeat_data, timeout=5)
                if response.status_code == 200:
                    logging.info("Heartbeat 전송 성공")
                else:
                    logging.warning(f"Heartbeat 전송 실패: {response.status_code}")
        
        except Exception as e:
            logging.error(f"Heartbeat 전송 중 오류: {str(e)}")
        
        await asyncio.sleep(HEARTBEAT_INTERVAL)

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

# 루트 경로에도 동일한 핸들러 등록 (호환성 유지)
@app.post("/")
async def run_task_root(task: dict):
    """루트 경로 태스크 실행 (호환성용)"""
    return await run_task(task)

@app.post("/run")
async def run_task(task: dict):
    """태스크 실행 엔드포인트"""
    try:
        logger.info(f"태스크 수신: {task.get('task_id')}")
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

# 종료 이벤트 핸들러 추가
@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 처리"""
    try:
        # 일반 unregister 엔드포인트 시도
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{REGISTRY_URL}/unregister",
                    params={"role": AGENT_ROLE, "agent_id": AGENT_ID}
                )
                logging.info(f"에이전트 등록 해제 응답: {response.status_code}")
                
                # 실패 시 백업 메서드 사용
                if response.status_code != 200:
                    backup_response = await client.post(
                        f"{REGISTRY_URL}/unregister_direct",
                        params={"role": AGENT_ROLE, "agent_id": AGENT_ID}
                    )
                    logging.info(f"백업 등록 해제 응답: {backup_response.status_code}")
            except Exception as req_error:
                logging.error(f"등록 해제 요청 중 오류: {str(req_error)}")
                
    except Exception as e:
        logging.error(f"에이전트 등록 해제 중 오류: {str(e)}")
