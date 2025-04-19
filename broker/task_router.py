import random
from typing import List, Optional
from .registry_client import RegistryClient, Agent

class TaskRouter:
    def __init__(self, registry_client: RegistryClient):
        self.registry_client = registry_client
    
    async def select_agent(self, role: str) -> Optional[Agent]:
        """역할에 맞는 에이전트 선택"""
        agents = await self.registry_client.get_agents_by_role(role)
        
        if not agents:
            return None
        
        # 가장 부하가 적은 에이전트 선택 (부하가 같으면 랜덤)
        agents.sort(key=lambda a: a.load)
        min_load = agents[0].load
        candidates = [a for a in agents if a.load == min_load]
        
        return random.choice(candidates) if candidates else None 