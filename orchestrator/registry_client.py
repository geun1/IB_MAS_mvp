"""
Registry 서비스와의 통신을 담당하는 클라이언트
"""
import logging
import httpx
import asyncio
from typing import List, Dict, Optional, Any
from .models import Agent, AgentParam
from .config import REGISTRY_URL

# 로깅 설정
logger = logging.getLogger(__name__)

class RegistryClient:
    """레지스트리 서비스 클라이언트"""
    
    def __init__(self, registry_url: str = REGISTRY_URL):
        """
        레지스트리 클라이언트 초기화
        
        Args:
            registry_url: 레지스트리 서비스 URL
        """
        self.registry_url = registry_url
        logger.info(f"레지스트리 클라이언트 초기화 (URL: {registry_url})")
        
    async def get_all_agents(self) -> List[Agent]:
        """
        모든 등록된 에이전트 목록 조회
        
        Returns:
            Agent 객체 리스트
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.registry_url}/agents")
                response.raise_for_status()
                
                agents_data = response.json()
                if isinstance(agents_data, dict) and "agents" in agents_data:
                    agents = [Agent(**agent) for agent in agents_data["agents"]]
                else:
                    agents = [Agent(**agent) for agent in agents_data]
                    
                logger.info(f"{len(agents)}개의 에이전트 정보를 조회했습니다")
                return agents
                
        except Exception as e:
            logger.error(f"에이전트 목록 조회 중 오류: {str(e)}")
            return []
    
    async def get_agents_by_role(self, role: str, status: str = "available") -> List[Agent]:
        """
        특정 역할의 에이전트 목록 조회
        
        Args:
            role: 에이전트 역할
            status: 에이전트 상태 필터
            
        Returns:
            Agent 객체 리스트
        """
        try:
            url = f"{self.registry_url}/agents/by-role/{role}"
            params = {"status": status} if status else {}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                agents_data = response.json()
                if isinstance(agents_data, dict) and "agents" in agents_data:
                    agents = [Agent(**agent) for agent in agents_data["agents"]]
                else:
                    agents = [Agent(**agent) for agent in agents_data]
                    
                logger.info(f"{len(agents)}개의 '{role}' 역할 에이전트를 조회했습니다")
                return agents
                
        except Exception as e:
            logger.error(f"역할별 에이전트 조회 중 오류: {str(e)}")
            return []
    
    async def generate_role_descriptions(self) -> str:
        """
        모든 에이전트 역할에 대한 설명 생성
        LLM 프롬프트에 사용할 역할 정보
        
        Returns:
            역할 정보 문자열
        """
        agents = await self.get_all_agents()
        
        # 역할별로 그룹화
        roles = {}
        for agent in agents:
            if agent.role not in roles:
                roles[agent.role] = {
                    "description": agent.description,
                    "params": [param.dict() for param in agent.params]
                }
        
        # 포맷팅된 문자열 생성
        result = []
        for role, info in roles.items():
            params_str = "\n".join([
                f"    - {param['name']}: {param['description']} " +
                f"({'필수' if param.get('required', False) else '선택'})"
                for param in info["params"]
            ])
            
            result.append(f"- 역할: {role}\n  설명: {info['description']}\n  파라미터:\n{params_str}")
        
        return "\n\n".join(result)
    
    async def check_health(self) -> Dict[str, Any]:
        """
        레지스트리 서비스 상태 확인
        
        Returns:
            상태 정보 딕셔너리
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.registry_url}/health")
                if response.status_code == 200:
                    return {"status": "healthy", "details": response.json()}
                else:
                    return {"status": "unhealthy", "details": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "unhealthy", "details": str(e)}
    
    async def get_agent_configs(self, role: str) -> Optional[Dict[str, Any]]:
        """
        특정 역할에 대한 에이전트 설정 조회
        
        Args:
            role: 에이전트 역할
        
        Returns:
            에이전트 설정 딕셔너리 또는 None
        """
        try:
            url = f"{self.registry_url}/agents/configs/{role}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                
                config_data = response.json()
                logger.info(f"'{role}' 역할에 대한 에이전트 설정을 조회했습니다")
                return config_data
        except Exception as e:
            logger.error(f"에이전트 설정 조회 중 오류: {str(e)}")
            return None 