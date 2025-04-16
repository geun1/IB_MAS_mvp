from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import os
import json
from typing import Dict, List, Optional

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="Agent Registry Service")

# Redis 연결
redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# 에이전트 모델 정의
class AgentParam(BaseModel):
    name: str
    description: str
    required: bool = False
    type: str = "string"

class Agent(BaseModel):
    id: str
    role: str
    description: str
    params: Optional[List[AgentParam]] = []
    type: str = "function"  # function, tool, react 등

# 에이전트 등록 API
@app.post("/register")
async def register_agent(agent: Agent):
    try:
        # TTL 30초로 설정 (하트비트로 갱신 필요)
        agent_key = f"agent:{agent.role}:{agent.id}"
        r.setex(agent_key, 30, json.dumps(agent.dict()))
        r.sadd(f"roles:{agent.role}", agent.id)
        return {"status": "success", "message": "Agent registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register agent: {str(e)}")

# 에이전트 목록 조회 API
@app.get("/agents")
async def list_agents():
    try:
        agents = []
        for key in r.keys("agent:*"):
            agent_data = r.get(key)
            if agent_data:
                agents.append(json.loads(agent_data))
        return {"agents": agents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")

# 역할별 에이전트 조회 API
@app.get("/agents/by-role/{role}")
async def get_agents_by_role(role: str):
    try:
        agent_ids = r.smembers(f"roles:{role}")
        agents = []
        for agent_id in agent_ids:
            agent_data = r.get(f"agent:{role}:{agent_id}")
            if agent_data:
                agents.append(json.loads(agent_data))
        return {"role": role, "agents": agents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agents by role: {str(e)}")

# 에이전트 하트비트 API
@app.post("/heartbeat/{role}/{agent_id}")
async def heartbeat(role: str, agent_id: str):
    try:
        agent_key = f"agent:{role}:{agent_id}"
        if not r.exists(agent_key):
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # TTL 갱신
        r.expire(agent_key, 30)
        return {"status": "success", "message": "Heartbeat processed"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process heartbeat: {str(e)}")

# 서버 상태 확인용 API
@app.get("/")
async def root():
    return {"status": "online", "service": "Agent Registry"}

# 서버 상태 확인용 API
@app.get("/health")
async def health():
    try:
        # Redis 연결 상태 확인
        ping = r.ping()
        return {"status": "healthy", "redis_connected": ping}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
