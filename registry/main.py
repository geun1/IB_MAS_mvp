import time
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import logging

from .models import Agent, AgentHeartbeat, AgentStatus, AgentList, ApiResponse, AgentStatistics
from .db import redis_client
from .config import DEFAULT_TTL, HOST, PORT
from common.models import AgentHeartbeat

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
    allow_origins=["*"],  # 개발 환경에서는 모든 origin 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 에이전트 활성화 요청 모델
class AgentEnablementRequest(BaseModel):
    """에이전트 활성화 요청 모델"""
    enabled: bool

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
    """애플리케이션 시작 시 초기화 작업"""
    # agents 딕셔너리 초기화
    app.state.agents = {}
    
    # 필요한 경우 Redis 연결 초기화 등 다른 작업도 여기서 수행
    logging.info("Registry 서비스가 시작되었습니다.")
    
    asyncio.create_task(cleanup_task())

# 라우트 정의
@app.post("/register", status_code=201)
async def register_agent(agent_data: dict):
    """새 에이전트 등록 API - 상세 오류 처리 추가"""
    try:
        # 요청 데이터 로깅
        logging.info(f"에이전트 등록 요청 데이터: {json.dumps(agent_data)}")
        
        # 필수 필드 확인
        required_fields = ["id", "role", "description", "endpoint"]
        for field in required_fields:
            if field not in agent_data:
                detail = f"필수 필드 누락: {field}"
                logging.error(detail)
                raise HTTPException(status_code=422, detail=detail)
        
        # Agent 모델 변환
        try:
            agent = Agent(**agent_data)
            logging.info(f"Agent 객체 생성 성공: {agent.id}")
        except Exception as e:
            error_msg = f"Agent 모델 변환 실패: {str(e)}"
            logging.error(error_msg)
            raise HTTPException(status_code=422, detail=error_msg)
        
        # 저장소에 저장
        try:
            success = await redis_client.register_agent(agent)
            if not success:
                raise HTTPException(status_code=500, detail="저장소( Redis / Memory )에 에이전트 등록 실패")
            
            return {
                "status": "success",
                "message": f"에이전트 '{agent.role}/{agent.id}' 등록 완료",
                "data": {"agent_id": agent.id}
            }
            
        except Exception as e:
            error_msg = f"에이전트 데이터 저장 실패: {str(e)}"
            logging.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"에이전트 등록 처리 중 예기치 않은 오류: {str(e)}"
        logging.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/heartbeat/{agent_type}/{agent_id}", status_code=200)
async def agent_heartbeat(agent_type: str, agent_id: str, heartbeat: AgentHeartbeat):
    try:
        # 수신한 heartbeat 데이터 로깅
        logging.debug(f"Heartbeat 수신: {agent_type}/{agent_id} - {heartbeat.model_dump(mode='json')}")
        
        # 등록된 에이전트 확인 
        if agent_id not in app.state.agents.get(agent_type, {}):
            # 자동 등록 로직 (선택 사항)
            app.state.agents.setdefault(agent_type, {})[agent_id] = {
                "id": agent_id,
                "type": agent_type,
                "status": heartbeat.status,
                "last_heartbeat": heartbeat.timestamp,
                "metrics": heartbeat.metrics.model_dump(mode='json'),
                "version": heartbeat.version
            }
            logging.info(f"새 에이전트 자동 등록: {agent_type}/{agent_id}")
        else:
            # 기존 에이전트 상태 업데이트
            app.state.agents[agent_type][agent_id].update({
                "status": heartbeat.status,
                "last_heartbeat": heartbeat.timestamp,
                "metrics": heartbeat.metrics.model_dump(mode='json')
            })
        
        return {"status": "success", "message": "Heartbeat received"}
    
    except Exception as e:
        logging.error(f"Heartbeat 처리 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Heartbeat 처리 중 오류: {str(e)}")

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

@app.delete("/agents/{role}/{agent_id}")
async def unregister_agent_by_path(role: str, agent_id: str):
    """에이전트 등록 해제 - 경로 파라미터 방식"""
    try:
        # 기존 구현된 메서드 활용
        success = await redis_client.unregister_agent(role, agent_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="등록되지 않은 에이전트")
        
        return {
            "status": "success", 
            "message": f"Agent {agent_id} unregistered successfully"
        }
    except Exception as e:
        logging.error(f"에이전트 등록 해제 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 등록 해제 중 오류: {str(e)}")

@app.get("/agents")
async def list_agents(
    role: Optional[str] = None,
    status: Optional[AgentStatus] = None,
    enabled_only: bool = Query(False, description="활성화된 에이전트만 조회할지 여부")
):
    """에이전트 목록 조회"""
    try:
        agents = await redis_client.list_agents(role, status, enabled_only)
        # 모든 에이전트 필드가 제대로 포함되었는지 확인
        for agent in agents:
            if not hasattr(agent, 'config_params'):
                logging.warning(f"에이전트 {agent.id}에 config_params 필드가 없습니다")
                
        return {
            "agents": agents,
            "total": len(agents),
            "timestamp": time.time()
        }
    except Exception as e:
        logging.error(f"에이전트 목록 조회 오류: {str(e)}")
        return {
            "agents": [],
            "total": 0,
            "timestamp": time.time()
        }

@app.get("/active-agents", response_model=AgentList, tags=["에이전트 조회"])
async def list_active_agents(
    role: Optional[str] = None
):
    """활성화된 에이전트만 조회"""
    try:
        agents = await redis_client.get_active_agents(role)
        return {
            "agents": agents,
            "total": len(agents),
            "timestamp": time.time()
        }
    except Exception as e:
        logging.error(f"활성화된 에이전트 목록 조회 오류: {str(e)}")
        return {
            "agents": [],
            "total": 0,
            "timestamp": time.time()
        }

@app.patch("/agents/{agent_id}/enablement", response_model=ApiResponse, tags=["에이전트 관리"])
async def set_agent_enablement(agent_id: str, request: AgentEnablementRequest):
    """에이전트 활성화 상태 설정"""
    try:
        success = await redis_client.set_agent_enablement(agent_id, request.enabled)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"에이전트 {agent_id}를 찾을 수 없습니다.")
        
        status_text = "활성화" if request.enabled else "비활성화"
        return {
            "status": "success",
            "message": f"에이전트 {agent_id}가 {status_text}되었습니다."
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"에이전트 활성화 상태 변경 중 오류: {str(e)}"
        logging.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/agents/by-role/{role}", response_model=List[Agent], tags=["에이전트 조회"])
async def get_agents_by_role(
    role: str, 
    status: Optional[str] = Query(None), 
    max_load: Optional[float] = Query(None),
    enabled_only: bool = Query(False, description="활성화된 에이전트만 조회할지 여부")
):
    """역할별 에이전트 목록 조회"""
    try:
        # 올바른 비동기 호출 방식으로 수정
        agents = await redis_client.get_agents_by_role(role, status, max_load)
        
        # 활성화된 에이전트만 필터링
        if enabled_only:
            agents = [agent for agent in agents if getattr(agent, 'is_enabled', True)]
            
        return agents
    except Exception as e:
        logging.error(f"역할별 에이전트 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"역할별 에이전트 조회 중 오류: {str(e)}")

@app.get("/health", status_code=200)
async def health_check():
    """헬스체크 엔드포인트"""
    return {"status": "ok"}

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

@app.post("/debug/redis-keys")
async def debug_redis_keys():
    """Redis에 저장된 모든 키를 조회"""
    try:
        all_keys = redis_client.redis.keys("*")
        key_types = {}
        
        # 모든 키의 타입 확인
        for key in all_keys:
            key_types[key] = redis_client.redis.type(key)
            
        return {
            "keys": all_keys,
            "types": key_types,
            "total": len(all_keys)
        }
    except Exception as e:
        logging.error(f"Redis 키 디버깅 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/unregister_direct", response_model=ApiResponse, tags=["에이전트 관리"])
async def unregister_agent_direct(role: str = Query(...), agent_id: str = Query(...)):
    """에이전트 등록 직접 해제 (백업 메서드)"""
    try:
        # 디버깅 정보 로깅
        all_keys = redis_client.redis.keys("*")
        logging.info(f"Redis 키 목록: {all_keys}")
        
        # 등록한 방식과 일치하게 해시에서 삭제
        deleted_hash = redis_client.redis.hdel("agents", agent_id)
        logging.info(f"해시 삭제 결과: {deleted_hash}")
        
        # 역할별 인덱스에서 삭제
        deleted_role = redis_client.redis.srem(f"role:{role}", agent_id)
        logging.info(f"역할 인덱스 삭제 결과: {deleted_role}")
        
        # 에이전트 ID 목록에서 삭제
        deleted_id = redis_client.redis.srem("agent_ids", agent_id)
        logging.info(f"ID 목록 삭제 결과: {deleted_id}")
        
        # TTL 키 삭제
        deleted_ttl = redis_client.redis.delete(f"ttl:{agent_id}")
        logging.info(f"TTL 키 삭제 결과: {deleted_ttl}")
        
        return {
            "status": "success",
            "message": f"에이전트 '{role}/{agent_id}' 등록 해제됨 (직접 삭제)"
        }
    except Exception as e:
        logging.error(f"에이전트 직접 등록 해제 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 등록 해제 중 오류: {str(e)}")

@app.post("/debug/agent-keys")
async def debug_agent_keys():
    """Redis에 저장된 에이전트 관련 모든 키 조회 (디버깅용)"""
    try:
        # 모든 키 패턴 조회
        all_keys = redis_client.redis.keys("*agent*")
        role_keys = redis_client.redis.keys("*role*")
        status_keys = redis_client.redis.keys("*status*")
        
        return {
            "agent_keys": all_keys,
            "role_keys": role_keys,
            "status_keys": status_keys,
            "total_keys": len(all_keys) + len(role_keys) + len(status_keys)
        }
    except Exception as e:
        logging.error(f"키 디버깅 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"키 디버깅 중 오류: {str(e)}")

# 서비스 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
