import random
from typing import List, Optional
from .registry_client import RegistryClient, Agent

class TaskRouter:
    def __init__(self, registry_client: RegistryClient):
        self.registry_client = registry_client
    
    async def select_agent(self, role: str, exclude_agent_id: Optional[str] = None) -> Optional[Agent]:
        """
        역할에 맞는 에이전트 선택
        
        Args:
            role: 필요한 에이전트 역할
            exclude_agent_id: 제외할 에이전트 ID (ReACT 에이전트 자신 등)
            
        Returns:
            선택된 에이전트 또는 None
        """
        agents = await self.registry_client.get_agents_by_role(role)
        
        if not agents:
            return None
        
        # 특정 에이전트 제외
        if exclude_agent_id:
            agents = [agent for agent in agents if agent.id != exclude_agent_id]
            
            if not agents:
                return None
        
        # 가장 부하가 적은 에이전트 선택 (부하가 같으면 랜덤)
        agents.sort(key=lambda a: a.load)
        min_load = agents[0].load
        candidates = [a for a in agents if a.load == min_load]
        
        return random.choice(candidates) if candidates else None 

def get_agent_url(agent_info):
    base_url = f"http://{agent_info['host']}:{agent_info['port']}"
    # 엔드포인트가 이미 포함되어 있는지 확인
    if "/run" not in base_url:
        return f"{base_url}/run"
    return base_url 