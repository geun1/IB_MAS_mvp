"""
사용자 요청을 세부 태스크로 분해하는 모듈
"""
import logging
import asyncio
import time
import uuid
import json
from typing import List, Dict, Any, Optional, Tuple

from .models import Task, TaskDecomposition
from .llm_client import OrchestratorLLMClient
from .registry_client import RegistryClient
from .config import DEFAULT_TASK_TIMEOUT

# 로깅 설정
logger = logging.getLogger(__name__)

class TaskDecomposer:
    """사용자 요청을 여러 태스크로 분해하는 클래스"""
    
    def __init__(self, registry_client: RegistryClient, llm_client: OrchestratorLLMClient):
        """
        태스크 분해기 초기화
        
        Args:
            registry_client: 레지스트리 클라이언트
            llm_client: LLM 클라이언트
        """
        self.registry_client = registry_client
        self.llm_client = llm_client
        logger.info("태스크 분해기 초기화 완료")
    
    async def _get_agent_roles(self, disabled_agents: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        사용 가능한 에이전트 역할 정보 조회
        
        Args:
            disabled_agents: 비활성화된 에이전트 역할 목록
        
        Returns:
            에이전트 역할 정보 목록
        """
        agents = await self.registry_client.get_all_agents()
        agent_info = []
        
        for agent in agents:
            # 비활성화된 에이전트인 경우 건너뛰기
            if disabled_agents and agent.role in disabled_agents:
                logger.info(f"비활성화된 에이전트 건너뛰기: {agent.role}")
                continue
                
            agent_info.append({
                "role": agent.role,
                "description": agent.description,
                "capabilities": [param.dict() for param in agent.params] if agent.params else []
            })
            
        logger.info(f"{len(agent_info)}개의 활성화된 에이전트 역할 정보 조회 완료")
        
        # 비활성화된 에이전트가 있는 경우 로그 출력
        if disabled_agents:
            logger.info(f"{len(disabled_agents)}개의 비활성화된 에이전트: {', '.join(disabled_agents)}")
            
        return agent_info
    
    async def decompose_query(self, query: str, conversation_id: str = None, user_id: str = None, disabled_agents: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], List[List[int]], List[List[str]]]:
        """
        쿼리를 태스크로 분해
        
        Args:
            query: 사용자 쿼리
            conversation_id: 대화 ID
            user_id: 사용자 ID
            disabled_agents: 비활성화된 에이전트 역할 목록
            
        Returns:
            태스크 목록, 실행 레벨별 태스크 인덱스 목록, 실행 레벨별 자연어 태스크 설명 목록의 튜플
        """
        logger.info(f"쿼리 분해 시작: '{query}'")
        
        # 레지스트리에서 모든 에이전트 정보 조회
        all_agents_raw = await self.registry_client.get_all_agents() # RegistryClient의 반환 타입 확인 필요 (Agent 모델 리스트 가정)
        if not all_agents_raw:
            logger.warning("레지스트리에서 에이전트 정보를 가져올 수 없습니다.")
            return [], [], []

        # 비활성화된 역할(role) 집합 생성
        disabled_roles = set()
        if disabled_agents:
            for agent in all_agents_raw:
                if agent.id in disabled_agents:
                    disabled_roles.add(agent.role)
            logger.info(f"비활성화된 역할: {disabled_roles}")

        # LLM에게 전달할 활성화된 에이전트 정보 필터링 및 포맷팅
        active_agents_info = []
        for agent in all_agents_raw:
            if agent.role not in disabled_roles:
                active_agents_info.append({
                    "role": agent.role,
                    "description": agent.description,
                    "capabilities": [param.dict() for param in agent.params] if agent.params else []
                })
        
        if not active_agents_info:
            logger.warning("사용 가능한 활성화된 에이전트가 없습니다.")
            return [], [], []
            
        logger.info(f"{len(active_agents_info)}개의 활성화된 에이전트 발견")

        # LLM을 사용하여 태스크 분해 (활성화된 에이전트 정보만 사용)
        detailed_roles_description = await self.registry_client.generate_detailed_role_descriptions(disabled_roles)
        agents_detail = self._format_agent_details(active_agents_info)
        
        decomposition_result = await self.llm_client.decompose_tasks(
            query, 
            detailed_roles_description,
            agents_detail=agents_detail
        )

        # 태스크 목록 추출
        tasks_from_llm = decomposition_result.get("tasks", [])
        
        # LLM이 생성한 태스크 중 비활성화된 역할을 사용하는 태스크 필터링 및 인덱스 재구성
        valid_tasks = []
        original_indices = {} # 원래 인덱스 -> 새 인덱스 매핑
        current_valid_index = 0
        
        for original_index, task in enumerate(tasks_from_llm):
            role = task.get("role")
            
            # 역할이 없거나 비활성화된 역할이면 제외
            if not role or role in disabled_roles:
                logger.warning(f"역할이 없거나 비활성화된 역할('{role}')의 태스크를 제외합니다: {task.get('description')}")
                continue 
            
            # 유효한 태스크 추가 및 인덱스 매핑
            valid_tasks.append(task)
            original_indices[original_index] = current_valid_index
            current_valid_index += 1

            # stock_analysis 에이전트 파라미터 처리 (기존 로직 유지)
            params = task.get("params", {})
            if role == "stock_analysis" and "stock_data" in params:
                if isinstance(params["stock_data"], str):
                    str_value = params["stock_data"]
                    logger.warning(f"문자열 형태의 stock_data 파라미터 발견: {str_value}")
                    if str_value.lower() in ["이전 태스크의 결과", "previous task result", "stock_data", "의존성", "depends"]:
                        params["stock_data"] = {}
                    else:
                        try:
                            prompt = f"""
다음 문자열은 주식 분석에 필요한 데이터에 대한 설명입니다:
"{str_value}"
이 설명을 기반으로, 주식 분석 API에 사용할 수 있는 적절한 JSON 구조의 데이터를 생성해 주세요.
가능하다면, 아래와 유사한 형태의 Time Series 데이터 구조로 응답해 주세요:
```json
{{
  "Meta Data": {{...}},
  "Time Series (Daily)": {{...}}
}}
```
또는 쿼리에서 주식 정보가 충분하지 않다면, 빈 객체 {{}}를 반환하고 그 이유를 설명해 주세요.
응답은 유효한 JSON 형태로만 제공해 주세요.
"""
                            response = await self.llm_client.ask(prompt)
                            try:
                                import re
                                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
                                json_str = json_match.group(1).strip() if json_match else response.strip()
                                structured_data = json.loads(json_str)
                                if structured_data and isinstance(structured_data, dict):
                                    params["stock_data"] = structured_data
                                else:
                                    params["stock_data"] = {}
                            except Exception as e:
                                logger.error(f"JSON 파싱 실패: {str(e)}, 빈 객체 사용")
                                params["stock_data"] = {}
                        except Exception as e:
                            logger.error(f"LLM 호출 실패: {str(e)}, 빈 객체 사용")
                            params["stock_data"] = {}
        
        # 최종 유효 태스크 목록
        tasks = valid_tasks
        if not tasks:
             logger.warning("활성화된 에이전트를 사용하는 유효한 태스크가 없습니다.")
             return [], [], []

        # 의존성 그래프 구성 및 실행 레벨 결정 (유효 태스크 기준)
        execution_levels = []
        remaining = set(range(len(tasks))) 
        dependents = {}
        for new_idx, task in enumerate(tasks):
            original_deps = task.get("depends_on", [])
            # 원래 의존성 인덱스를 새 인덱스로 변환 (유효한 태스크만 포함)
            new_deps = {original_indices[dep] for dep in original_deps if dep in original_indices}
            dependents[new_idx] = new_deps
            task["depends_on"] = list(new_deps) # task 객체 내 의존성 업데이트

        # 실행 레벨 결정
        while remaining:
            current_level_indices = set()
            for task_idx in list(remaining):
                if all(dep not in remaining for dep in dependents[task_idx]):
                    current_level_indices.add(task_idx)

            if not current_level_indices:
                logger.warning(f"실행 가능한 다음 태스크를 찾을 수 없습니다 (순환 의존성 가능성). 남은 태스크 인덱스: {remaining}")
                execution_levels.append(list(remaining)) # 남은 태스크 강제 실행
                break 
            
            execution_levels.append(list(current_level_indices))
            remaining -= current_level_indices
        
        # 자연어 태스크 설명 목록 생성
        natural_language_tasks = []
        for level in execution_levels:
            tasks_in_level = [tasks[idx]["description"] for idx in level]
            logger.info(f"실행 레벨 {len(natural_language_tasks) + 1}: {tasks_in_level}")
            natural_language_tasks.append(tasks_in_level)
        
        logger.info(f"쿼리 분해 완료: {len(tasks)}개의 유효한 태스크 생성됨")
        
        return tasks, execution_levels, natural_language_tasks
        
    async def _decompose_with_llm(self, query: str, agent_capabilities: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM을 사용하여 쿼리를 태스크로 분해
        
        Args:
            query: 사용자 쿼리
            agent_capabilities: 에이전트 역할 및 기능 정보
            
        Returns:
            분해된 태스크 정보
        """
        # 역할 정보 문자열 생성
        roles_description = ""
        for role, info in agent_capabilities.items():
            description = info["description"]
            roles_description += f"- {role}: {description}\n"
            
            if info["capabilities"]:
                caps = info["capabilities"]
                param_details = []
                for cap in caps:
                    param_name = cap.get("name", "")
                    param_desc = cap.get("description", "")
                    param_required = "필수" if cap.get("required", False) else "선택"
                    param_details.append(f"{param_name} ({param_required}): {param_desc}")
                    
                roles_description += "  파라미터: " + "\n    - ".join([""] + param_details) + "\n"
                
        # LLM 호출
        agents_detail = self._format_agent_details(agent_capabilities)
        decomposition_result = await self.llm_client.decompose_tasks(query, roles_description, agents_detail=agents_detail)
        return decomposition_result

    def analyze_dependencies(self, tasks: List[Task]) -> List[List[int]]:
        """
        태스크 의존성 분석 및 실행 레벨 결정
        
        Args:
            tasks: 태스크 목록
            
        Returns:
            실행 레벨별 태스크 인덱스 목록
        """
        # 의존성 그래프 생성
        graph = {i: task.depends_on for i, task in enumerate(tasks)}
        
        # 실행 레벨 계산
        levels = []
        remaining = set(range(len(tasks)))
        
        while remaining:
            # 현재 레벨에서 실행 가능한 태스크 (의존성이 모두 해결된 태스크)
            current_level = []
            
            for task_idx in list(remaining):
                dependencies = graph[task_idx]
                if all(dep not in remaining for dep in dependencies):
                    current_level.append(task_idx)
            
            # 실행 가능한 태스크가 없으면 순환 의존성이 있음
            if not current_level:
                logger.warning("순환 의존성 감지됨, 남은 태스크를 현재 레벨에 추가")
                current_level = list(remaining)
            
            levels.append(current_level)
            remaining -= set(current_level)
        
        return levels 

    def _format_agent_details(self, agents_info: List[Dict[str, Any]]) -> str:
        """
        에이전트 상세 정보를 포맷팅하여 LLM에게 전달할 문자열 생성
        
        Args:
            agents_info: 에이전트 정보 목록
            
        Returns:
            포맷팅된 에이전트 상세 정보 문자열
        """
        result = "## 사용 가능한 에이전트 정보\n\n"
        
        for agent in agents_info:
            role = agent.get("role", "알 수 없음")
            description = agent.get("description", "설명 없음")
            capabilities = agent.get("capabilities", [])
            
            result += f"### {role}\n"
            result += f"{description}\n\n"
            
            if capabilities:
                result += "#### 파라미터:\n"
                for param in capabilities:
                    param_name = param.get("name", "알 수 없음")
                    param_desc = param.get("description", "설명 없음")
                    param_type = param.get("type", "string")
                    required = "필수" if param.get("required", False) else "선택"
                    
                    result += f"- **{param_name}** ({param_type}, {required}): {param_desc}\n"
            
            result += "\n"
        
        return result 