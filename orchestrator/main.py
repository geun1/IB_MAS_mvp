from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
import os
import json
from typing import Dict, List, Optional, Any

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="Orchestrator Service")

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
BROKER_URL = os.getenv("BROKER_URL", "http://broker:8000")

# 모델 정의
class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None

class Task(BaseModel):
    role: str
    params: Dict[str, Any]
    task_id: Optional[str] = None

class TaskResponse(BaseModel):
    tasks: List[Task]
    conversation_id: str

# 생성된 작업 처리
async def process_tasks(tasks: List[Task], conversation_id: str):
    async with httpx.AsyncClient() as client:
        for task in tasks:
            try:
                # Broker에 작업 전달
                response = await client.post(
                    f"{BROKER_URL}/task",
                    json={
                        "role": task.role,
                        "params": task.params,
                        "conversation_id": conversation_id
                    }
                )
                response.raise_for_status()
            except Exception as e:
                print(f"Error sending task to broker: {str(e)}")

# 사용자 쿼리 처리 API
@app.post("/query")
async def process_query(request: QueryRequest, background_tasks: BackgroundTasks):
    try:
        # 고유 대화 ID 생성
        conversation_id = f"conv_{request.user_id}_{hash(request.query)}"
        
        # 간단한 규칙 기반 태스크 분해 (실제로는 LLM 사용)
        tasks = []
        
        if "검색" in request.query or "찾아" in request.query:
            tasks.append(Task(
                role="web_search",
                params={"query": request.query}
            ))
        
        if "보고서" in request.query or "작성" in request.query:
            tasks.append(Task(
                role="writer",
                params={"topic": request.query}
            ))
        
        # 태스크가 없으면 기본적으로 writer 사용
        if not tasks:
            tasks.append(Task(
                role="writer",
                params={"topic": request.query}
            ))
        
        # 백그라운드에서 태스크 처리
        background_tasks.add_task(process_tasks, tasks, conversation_id)
        
        return {"status": "processing", "conversation_id": conversation_id, "tasks": [t.dict() for t in tasks]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")

# 서버 상태 확인용 API
@app.get("/")
async def root():
    return {"status": "online", "service": "Orchestrator"}

# 서버 상태 확인용 API
@app.get("/health")
async def health():
    try:
        # Registry 서비스 상태 확인
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{REGISTRY_URL}/health")
            registry_status = response.json()
        
        return {
            "status": "healthy", 
            "registry": registry_status
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e)
        }
