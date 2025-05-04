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
    
    async def _get_agent_roles(self) -> List[Dict[str, Any]]:
        """
        사용 가능한 에이전트 역할 정보 조회
        
        Returns:
            에이전트 역할 정보 목록
        """
        agents = await self.registry_client.get_all_agents()
        agent_info = []
        
        for agent in agents:
            agent_info.append({
                "role": agent.role,
                "description": agent.description,
                "capabilities": [param.dict() for param in agent.params] if agent.params else []
            })
            
        logger.info(f"{len(agent_info)}개의 에이전트 역할 정보 조회 완료")
        return agent_info
    
    async def decompose_query(self, query: str, conversation_id: str = None, user_id: str = None) -> Tuple[List[Dict[str, Any]], List[List[int]], List[List[str]]]:
        """
        쿼리를 태스크로 분해
        
        Args:
            query: 사용자 쿼리
            conversation_id: 대화 ID
            user_id: 사용자 ID
            
        Returns:
            태스크 목록, 실행 레벨별 태스크 인덱스 목록, 실행 레벨별 자연어 태스크 설명 목록의 튜플
        """
        logger.info(f"쿼리 분해 시작: '{query}'")
        
        # 에이전트 역할 정보 조회
        agents_info = await self._get_agent_roles()
        if not agents_info:
            logger.warning("사용 가능한 에이전트가 없습니다")
            return [], [], []
        
        # 역할별 에이전트 기능 사전 생성
        agent_capabilities = {}
        for agent in agents_info:
            role = agent.get("role")
            description = agent.get("description", "")
            capabilities = agent.get("capabilities", [])
            agent_capabilities[role] = {
                "description": description,
                "capabilities": capabilities
            }
        
        logger.info(f"에이전트 역할 정보 조회 완료: {len(agent_capabilities)}개의 에이전트 발견")
        
        # LLM을 사용하여 태스크 분해
        # 등록된 에이전트의 상세 정보를 활용하여 더 정확한 태스크 분해 수행
        detailed_roles_description = await self.registry_client.generate_detailed_role_descriptions()
        
        # 사용 가능한 모든 에이전트에 대한 자세한 능력과 파라미터 정보 제공
        agents_detail = self._format_agent_details(agents_info)
        
        # 태스크 분해 수행 (사용 가능한 에이전트의 상세 정보 포함)
        decomposition_result = await self.llm_client.decompose_tasks(
            query, 
            detailed_roles_description,
            agents_detail=agents_detail
        )

        # 태스크 목록 및 실행 레벨 추출
        tasks = decomposition_result.get("tasks", [])
        
        # 태스크 파라미터 검증 및 수정
        for task in tasks:
            role = task.get("role")
            params = task.get("params", {})
            
            # stock_analysis 에이전트 처리 - 문자열로 된 stock_data 처리
            if role == "stock_analysis" and "stock_data" in params:
                if isinstance(params["stock_data"], str):
                    str_value = params["stock_data"]
                    logger.warning(f"문자열 형태의 stock_data 파라미터 발견: {str_value}")
                    
                    if str_value.lower() in ["이전 태스크의 결과", "previous task result", "stock_data", "의존성", "depends"]:
                        # 의존성 결과로부터 데이터를 사용할 것임을 알려주는 일반적인 문자열인 경우
                        logger.info("의존성 데이터 참조 문자열로 판단하여 빈 객체로 초기화")
                        params["stock_data"] = {}  # 빈 객체로 설정
                    else:
                        # LLM을 사용하여 문자열을 분석하고 필요한 경우 구조화된 데이터로 변환 시도
                        logger.info("LLM을 사용하여 문자열 분석 시도")
                        try:
                            # 프롬프트 작성
                            prompt = f"""
다음 문자열은 주식 분석에 필요한 데이터에 대한 설명입니다:
"{str_value}"

이 설명을 기반으로, 주식 분석 API에 사용할 수 있는 적절한 JSON 구조의 데이터를 생성해 주세요.
가능하다면, 아래와 유사한 형태의 Time Series 데이터 구조로 응답해 주세요:

```json
{{
  "Meta Data": {{
    "1. Information": "Daily Prices",
    "2. Symbol": "[적절한 주식 심볼]"
  }},
  "Time Series (Daily)": {{
    "2023-01-01": {{
      "1. open": "100.00",
      "2. high": "105.00",
      "3. low": "99.00",
      "4. close": "102.50",
      "5. volume": "10000"
    }}
  }}
}}
```

또는 쿼리에서 주식 정보가 충분하지 않다면, 빈 객체 {{}}를 반환하고 그 이유를 설명해 주세요.
응답은 유효한 JSON 형태로만 제공해 주세요.
"""
                            # LLM 호출하여 구조화된 데이터 생성 시도
                            response = await self.llm_client.ask(prompt)
                            
                            # JSON 추출 시도
                            try:
                                # 응답에서 JSON 부분 추출
                                import re
                                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
                                
                                if json_match:
                                    json_str = json_match.group(1).strip()
                                else:
                                    # JSON 블록이 없으면 응답 전체를 JSON으로 해석 시도
                                    json_str = response.strip()
                                
                                # JSON 파싱
                                structured_data = json.loads(json_str)
                                
                                if structured_data and isinstance(structured_data, dict):
                                    logger.info("LLM을 통해 문자열을 구조화된 데이터로 변환 성공")
                                    params["stock_data"] = structured_data
                                else:
                                    logger.warning("LLM이 유효한 데이터를 생성하지 못함, 빈 객체 사용")
                                    params["stock_data"] = {}
                            except Exception as e:
                                logger.error(f"JSON 파싱 실패: {str(e)}, 빈 객체 사용")
                                params["stock_data"] = {}
                        except Exception as e:
                            logger.error(f"LLM 호출 실패: {str(e)}, 빈 객체 사용")
                            params["stock_data"] = {}
        
        # 의존성 그래프 구성 및 실행 레벨 결정
        # 모든 태스크의 의존성 관계를 분석하여 실행 순서 결정
        execution_levels = []
        remaining = set(range(len(tasks)))
        dependents = {i: set(task.get("depends_on", [])) for i, task in enumerate(tasks)}
        
        # 의존성이 없는 태스크부터 실행 레벨에 추가
        while remaining:
            current_level = []
            for task_idx in list(remaining):
                if all(dep not in remaining for dep in dependents[task_idx]):
                    current_level.append(task_idx)
                    
            # 순환 의존성이 있는 경우 나머지 태스크 모두 추가
            if not current_level:
                logger.warning("순환 의존성 감지됨, 남은 태스크를 현재 레벨에 추가")
                current_level = list(remaining)
                
            execution_levels.append(current_level)
            remaining -= set(current_level)
        
        # 자연어 태스크 설명 목록 생성
        natural_language_tasks = []
        
        # 로깅 강화: 태스크 간 의존성 정보 출력
        for level_idx, level in enumerate(execution_levels):
            tasks_in_level = [tasks[idx]["description"] for idx in level]
            logger.info(f"실행 레벨 {level_idx+1}: {tasks_in_level}")
            # 자연어 설명 목록에 추가
            natural_language_tasks.append(tasks_in_level)
        
        logger.info(f"쿼리 분해 완료: {len(tasks)}개의 태스크 생성됨")
        
        # 자연어 태스크 설명도 함께 반환
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