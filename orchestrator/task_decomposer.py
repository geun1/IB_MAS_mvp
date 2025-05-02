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
        
        logger.info("에이전트 역할 정보 조회 완료")
        
        # LLM을 사용하여 태스크 분해
        roles_description = await self.registry_client.generate_role_descriptions()
        decomposition_result = await self.llm_client.decompose_tasks(query, roles_description)
        
        # 태스크 목록 및 실행 레벨 추출
        tasks = decomposition_result.get("tasks", [])
        
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
                roles_description += "  지원 기능: " + ", ".join(caps) + "\n"
                
        # LLM 호출
        decomposition_result = await self.llm_client.decompose_tasks(query, roles_description)
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