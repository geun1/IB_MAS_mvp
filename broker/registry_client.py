import httpx
import logging
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class AgentParam(BaseModel):
    name: str
    description: str
    type: str = "string"
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None

class Agent(BaseModel):
    id: str
    role: str
    description: str
    endpoint: str
    status: str
    params: List[AgentParam] = []
    load: float = 0.0
    active_tasks: int = 0
    # 기타 필요한 필드...

class RegistryClient:
    def __init__(self, registry_url: str):
        self.registry_url = registry_url
        self.logger = logging.getLogger("registry_client")
    
    async def get_agents_by_role(self, role: str) -> List[Agent]:
        """특정 역할을 가진 에이전트 목록 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.registry_url}/agents/by-role/{role}",
                    params={"status": "available", "max_load": 0.8}
                )
                response.raise_for_status()
                
                # 수정: 이미 response.json()은 객체이므로 await을 사용하지 않음
                agents_data = response.json()
                
                # 리스트 형태인지 확인하고 Agent 객체로 변환
                if isinstance(agents_data, list):
                    return [Agent(**agent) for agent in agents_data]
                elif "agents" in agents_data and isinstance(agents_data["agents"], list):
                    return [Agent(**agent) for agent in agents_data["agents"]]
                else:
                    self.logger.error(f"예상치 못한 응답 형식: {agents_data}")
                    return []
                    
        except Exception as e:
            self.logger.error(f"Registry 통신 오류: {str(e)}")
            return []
            
    async def get_agent_params(self, agent_id: str) -> List[AgentParam]:
        """특정 에이전트의 파라미터 스키마 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.registry_url}/agents/{agent_id}")
                response.raise_for_status()
                data = response.json()
                agent_data = data.get("data", {})
                return [AgentParam(**param) for param in agent_data.get("params", [])]
        except Exception as e:
            self.logger.error(f"파라미터 스키마 조회 오류: {str(e)}")
            return []

    async def update_agent_task_stats(self, agent_id: str, task_status: str, execution_time: Optional[float] = None):
        """에이전트 태스크 통계 업데이트"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.registry_url}/agents/{agent_id}/ta***REMOVED***stats",
                    json={
                        "status": task_status,
                        "execution_time": execution_time
                    }
                )
                response.raise_for_status()
                return True
        except Exception as e:
            self.logger.error(f"에이전트 통계 업데이트 오류: {str(e)}")
            return False

    async def check_health(self):
        """레지스트리 서비스 상태 확인"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.registry_url}/health")
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"status": "unhealthy", "detail": f"HTTP 오류: {response.status_code}"}
        except Exception as e:
            return {"status": "unhealthy", "detail": str(e)} 