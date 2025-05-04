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
    
    async def generate_role_descriptions(self, disabled_agents: Optional[List[str]] = None) -> str:
        """
        모든 에이전트 역할에 대한 설명 생성
        LLM 프롬프트에 사용할 역할 정보
        
        Args:
            disabled_agents: 비활성화된 에이전트 역할 목록
            
        Returns:
            역할 정보 문자열
        """
        agents = await self.get_all_agents()
        
        # 역할별로 그룹화
        roles = {}
        for agent in agents:
            # 비활성화된 에이전트 제외
            if disabled_agents and agent.role in disabled_agents:
                continue
                
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
    
    async def generate_detailed_role_descriptions(self, disabled_agents: Optional[List[str]] = None) -> str:
        """
        모든 에이전트 역할에 대한 상세 설명 생성
        LLM 프롬프트에 사용할 확장된 역할 정보
        
        Args:
            disabled_agents: 비활성화된 에이전트 역할 목록
        
        Returns:
            상세 역할 정보 문자열
        """
        agents = await self.get_all_agents()
        
        # 역할별로 그룹화
        roles = {}
        total_active_agents = 0
        
        for agent in agents:
            # 비활성화된 에이전트 제외
            if disabled_agents and agent.role in disabled_agents:
                continue
                
            total_active_agents += 1
            
            if agent.role not in roles:
                roles[agent.role] = {
                    "description": agent.description,
                    "params": [param.dict() for param in agent.params],
                    "count": 1  # 해당 역할을 가진 에이전트 수
                }
            else:
                roles[agent.role]["count"] += 1
        
        # 포맷팅된 문자열 생성 (더 상세한 정보 포함)
        result = []
        result.append(f"총 {len(roles)} 종류의 역할, {total_active_agents}개의 활성화된 에이전트가 사용 가능합니다.\n")
        
        # 활성화된 에이전트가 없는 경우
        if not roles:
            result.append("현재 사용 가능한 활성화된 에이전트가 없습니다. 모든 에이전트가 비활성화되었습니다.")
            return "\n".join(result)
        
        for role, info in roles.items():
            # 파라미터 정보 포맷팅
            params_detail = []
            for param in info["params"]:
                param_type = param.get("type", "string")
                required = "필수" if param.get("required", False) else "선택사항"
                description = param.get("description", "설명 없음")
                
                params_detail.append(
                    f"    - **{param['name']}** ({param_type}, {required}): {description}"
                )
            
            params_str = "\n".join(params_detail) if params_detail else "    - 파라미터 없음"
            
            # 역할 상세 정보 추가
            result.append(
                f"## {role} ({info['count']}개 인스턴스)\n"
                f"**설명**: {info['description']}\n\n"
                f"**입력 파라미터**:\n{params_str}\n\n"
                f"**적합한 사용 사례**: {self._generate_use_cases(role, info['description'])}"
            )
        
        return "\n\n".join(result)
    
    def _generate_use_cases(self, role: str, description: str) -> str:
        """
        역할과 설명을 기반으로 적합한 사용 사례 생성
        
        Args:
            role: 에이전트 역할
            description: 에이전트 설명
            
        Returns:
            적합한 사용 사례 문자열
        """
        # 역할별 사용 사례 매핑
        role_case_mapping = {
            "writer": "문서 작성, 리포트 생성, 콘텐츠 요약, 텍스트 편집",
            "web_search": "정보 검색, 최신 뉴스 조회, 사실 확인, 데이터 수집",
            "code_generator": "코드 생성, 함수 구현, 버그 수정, 코드 리팩토링",
            "stock_data_agent": "주식 데이터 조회, 시장 정보 수집, 금융 데이터 검색",
            "stock_analysis_agent": "주식 데이터 분석, 기술적 지표 계산, 금융 인사이트 제공",
            "data_analysis_agent": "데이터 분석, 통계 계산, 차트 생성, 데이터 인사이트 도출",
            "react_agent": "사용자 인터페이스 개발, UI 컴포넌트 생성, 프론트엔드 구현"
        }
        
        # 기본 사용 사례
        if role in role_case_mapping:
            return role_case_mapping[role]
        
        # 역할명에 특정 키워드가 포함된 경우
        if "search" in role.lower():
            return "정보 검색, 데이터 수집, 질의응답"
        elif "write" in role.lower() or "text" in role.lower():
            return "텍스트 생성, 콘텐츠 작성, 요약, 편집"
        elif "code" in role.lower() or "develop" in role.lower():
            return "코드 생성, 프로그래밍 지원, 개발 지원"
        elif "data" in role.lower() or "analysis" in role.lower():
            return "데이터 처리, 분석, 시각화, 인사이트 도출"
        
        # 설명에서 키워드 추출
        desc_lower = description.lower()
        if "검색" in desc_lower or "서치" in desc_lower:
            return "정보 검색, 데이터 수집, 질의응답"
        elif "작성" in desc_lower or "텍스트" in desc_lower:
            return "텍스트 생성, 콘텐츠 작성, 요약, 편집"
        elif "코드" in desc_lower or "개발" in desc_lower:
            return "코드 생성, 프로그래밍 지원, 개발 지원"
        elif "데이터" in desc_lower or "분석" in desc_lower:
            return "데이터 처리, 분석, 시각화, 인사이트 도출"
        
        # 기본 사용 사례
        return "일반적인 작업 수행, 정보 처리, 사용자 요청 처리"
    
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