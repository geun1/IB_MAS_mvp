import time
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

from .models import Agent, AgentHeartbeat, AgentStatus, AgentList, ApiResponse, AgentStatistics
from .db import redis_client
from .config import DEFAULT_TTL, HOST, PORT

app = FastAPI(
    title="Agent Registry API",
    description="에이전트 등록 및 관리를 위한 API 서비스",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "syntaxHighlight": {"theme": "monokai"},
        "deepLinking": True,
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
        "displayOperationId": True,
        "displayRequestDuration": True,
        "filter": True,
        "showExtensions": True,
        "tryItOutEnabled": True,
    }
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 비활성 에이전트 정리 백그라운드 태스크
async def cleanup_task():
    while True:
        try:
            # 60초 전 기준으로 비활성 에이전트 정리
            cutoff = time.time() - 60
            cleaned = await redis_client.cleanup_inactive_agents(cutoff)
            if cleaned > 0:
                print(f"{cleaned}개의 비활성 에이전트 정리됨")
        except Exception as e:
            print(f"정리 작업 오류: {str(e)}")
        
        await asyncio.sleep(30)  # 30초마다 실행

# 시작 시 백그라운드 작업 등록
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_task())

# 라우트 정의
@app.post("/register", response_model=ApiResponse, tags=["에이전트 관리"])
async def register_agent(agent: Agent):
    """새 에이전트 등록 또는 기존 에이전트 정보 업데이트"""
    success = await redis_client.register_agent(agent)
    
    if not success:
        raise HTTPException(status_code=500, detail="에이전트 등록 실패")
    
    return {
        "status": "success",
        "message": f"에이전트 '{agent.role}/{agent.id}' 등록됨",
        "data": {"agent_id": agent.id}
    }

@app.post("/heartbeat/{role}/{agent_id}", response_model=ApiResponse, tags=["에이전트 관리"])
async def agent_heartbeat(
    role: str, 
    agent_id: str, 
    heartbeat: AgentHeartbeat
):
    """에이전트 하트비트 갱신"""
    try:
        success = await redis_client.update_heartbeat(heartbeat)
        
        if not success:
            raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다")
            
        return {
            "status": "success",
            "message": "하트비트가 갱신되었습니다",
            "data": None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"하트비트 갱신 오류: {str(e)}"
        )

@app.post("/unregister", response_model=ApiResponse, tags=["에이전트 관리"])
async def unregister_agent(role: str = Query(...), agent_id: str = Query(...)):
    """에이전트 등록 해제"""
    success = await redis_client.unregister_agent(role, agent_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="등록되지 않은 에이전트")
    
    return {
        "status": "success",
        "message": f"에이전트 '{role}/{agent_id}' 등록 해제됨"
    }

@app.get("/agents", response_model=AgentList)
async def list_agents(
    role: Optional[str] = None,
    status: Optional[AgentStatus] = None
):
    """에이전트 목록 조회"""
    agents = await redis_client.list_agents(role, status)
    
    return {
        "agents": agents,
        "total": len(agents),
        "timestamp": time.time()
    }

@app.get("/agents/by-role/{role}", response_model=ApiResponse, tags=["에이전트 관리"])
async def get_agents_by_role(
    role: str, 
    status: Optional[str] = None,
    max_load: float = 1.0
):
    """특정 역할의 사용 가능한 에이전트 목록 반환"""
    try:
        agents = redis_client.get_agents_by_role(role, status, max_load)
        
        # 전체 에이전트 정보를 반환 (파라미터 스키마 포함)
        agent_list = [agent.dict() for agent in agents]
        
        return {
            "status": "success",
            "message": f"{len(agents)}개의 {role} 에이전트 조회 성공",
            "agents": agent_list
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"에이전트 조회 오류: {str(e)}"
        )

@app.get("/health", response_model=ApiResponse, tags=["시스템"])
async def health_check():
    """서비스 상태 확인"""
    try:
        # Redis 연결 확인
        redis_time = redis_client.redis.time()
        
        # 등록된 에이전트 통계
        roles = redis_client.redis.smembers("roles")
        total_agents = redis_client.redis.scard("agents")
        
        role_stats = {}
        for role in roles:
            role_stats[role] = redis_client.redis.scard(f"role:{role}")
        
        return {
            "status": "healthy",
            "message": "Registry 서비스 정상 작동 중",
            "data": {
                "redis_time": redis_time[0],
                "total_agents": total_agents,
                "roles": role_stats
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Registry 서비스 오류: {str(e)}"
        )

@app.get("/agents/{agent_id}/statistics", response_model=AgentStatistics)
async def get_agent_statistics(agent_id: str):
    """에이전트 태스크 처리 통계 조회"""
    try:
        stats_key = f"agent_stats:{agent_id}"
        stats_data = redis_client.redis.get(stats_key)
        
        if not stats_data:
            return AgentStatistics()
            
        return AgentStatistics(**json.loads(stats_data))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"통계 조회 오류: {str(e)}"
        )

@app.post("/agents/{agent_id}/ta***REMOVED***stats", response_model=ApiResponse)
async def update_agent_task_statistics(
    agent_id: str,
    data: Dict[str, Any]
):
    """에이전트 태스크 통계 업데이트"""
    try:
        status = data.get("status", "completed")
        execution_time = data.get("execution_time")
        
        result = await redis_client.update_agent_statistics(
            agent_id, status, execution_time
        )
        
        if result:
            return {
                "status": "success",
                "message": "에이전트 통계가 업데이트되었습니다",
                "data": None
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="에이전트 통계 업데이트 실패"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"에이전트 통계 업데이트 오류: {str(e)}"
        )

# 서비스 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
