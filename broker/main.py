from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
import json
from typing import Dict, List, Optional, Any

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="Broker Service")

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")

# 모델 정의
class TaskRequest(BaseModel):
    role: str
    params: Dict[str, Any]
    conversation_id: str

class TaskResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

# 작업 처리 API
@app.post("/task")
async def process_task(task: TaskRequest):
    try:
        # 1. Registry에서 역할에 맞는 에이전트 찾기
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{REGISTRY_URL}/agents/by-role/{task.role}")
            response.raise_for_status()
            agents_data = response.json()
        
        # 에이전트가 없으면 오류
        if not agents_data.get("agents"):
            raise HTTPException(status_code=404, detail=f"No agent found for role: {task.role}")
        
        # 첫 번째 에이전트 선택 (실제로는 더 복잡한 선택 로직 필요)
        agent = agents_data["agents"][0]
        agent_id = agent["id"]
        
        # 태스크 ID 생성
        task_id = f"task_{task.role}_{task.conversation_id}_{hash(json.dumps(task.params))}"
        
        # 나중에 실제 에이전트 호출 로직 구현 필요
        
        return {
            "task_id": task_id,
            "status": "queued",
            "message": f"Task sent to agent {agent_id} with role {task.role}"
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process task: {str(e)}")

# 서버 상태 확인용 API
@app.get("/")
async def root():
    return {"status": "online", "service": "Broker"}

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
