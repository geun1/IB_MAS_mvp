"""
사용자 요청을 세부 태스크로 분해하는 모듈
"""
import logging
import asyncio
import time
import uuid
from typing import List, Dict, Any, Optional

from .models import Task, TaskDecomposition
from .llm_client import OrchestratorLLMClient
from .registry_client import RegistryClient
from .config import DEFAULT_TASK_TIMEOUT

# 로깅 설정
logger = logging.getLogger(__name__)

class TaskDecomposer:
    """사용자 요청을 여러 태스크로 분해하는 클래스"""
    
    def __init__(self, llm_client: OrchestratorLLMClient, registry_client: RegistryClient):
        """
        태스크 분해기 초기화
        
        Args:
            llm_client: LLM 클라이언트
            registry_client: 레지스트리 클라이언트
        """
        self.llm_client = llm_client
        self.registry_client = registry_client
        logger.info("태스크 분해기 초기화 완료")
    
    async def decompose_query(self, query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        사용자 쿼리를 분석하여 태스크로 분해
        
        Args:
            query: 사용자 요청 쿼리
            user_id: 사용자 ID
            
        Returns:
            분해된 태스크 정보 및 대화 ID가 포함된 딕셔너리
        """
        # 대화 ID 생성
        conversation_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        logger.info(f"새 대화 시작: {conversation_id} (사용자: {user_id or '익명'})")
        
        try:
            # 레지스트리에서 역할 정보 가져오기
            role_descriptions = await self.registry_client.generate_role_descriptions()
            logger.info("에이전트 역할 정보 조회 완료")
            
            # LLM을 사용하여 태스크 분해
            logger.info(f"쿼리 분해 시작: '{query[:50]}...'")
            
            try:
                decomposition_result = await self.llm_client.decompose_tasks(query, role_descriptions)
            except Exception as llm_error:
                logger.error(f"LLM 호출 중 오류 발생: {str(llm_error)}")
                # LLM 오류 시 기본 태스크 생성
                return {
                    "conversation_id": conversation_id,
                    "original_query": query,
                    "tasks": [{
                        "role": "writer",
                        "description": "기본 태스크 (LLM 오류 복구)",
                        "params": {"topic": query},
                        "depends_on": []
                    }],
                    "reasoning": "LLM 오류로 기본 태스크 생성"
                }
            
            # 결과 파싱 및 태스크 객체 생성
            tasks = []
            raw_tasks = decomposition_result.get("tasks", [])
            reasoning = decomposition_result.get("reasoning", "태스크 분해 로직 없음")
            
            for i, task_data in enumerate(raw_tasks):
                # Task 모델 생성 전에 필수 필드 확인 및 기본값 설정
                if "role" not in task_data:
                    task_data["role"] = "writer"  # 기본 역할
                    
                if "description" not in task_data:
                    task_data["description"] = f"태스크 {i+1}"
                    
                if "params" not in task_data:
                    task_data["params"] = {"topic": query}
                    
                if "depends_on" not in task_data:
                    task_data["depends_on"] = []
                
                # 딕셔너리 형태로 저장 (Task 모델 대신)
                tasks.append(task_data)
            
            logger.info(f"쿼리 분해 완료: {len(tasks)}개의 태스크 생성됨")
            
            # 결과 반환
            return {
                "conversation_id": conversation_id,
                "original_query": query,
                "tasks": tasks,
                "reasoning": reasoning
            }
            
        except Exception as e:
            logger.error(f"태스크 분해 중 오류 발생: {str(e)}")
            
            # 오류 발생 시 기본 태스크 생성
            return {
                "conversation_id": conversation_id,
                "original_query": query,
                "tasks": [{
                    "role": "writer",
                    "description": "기본 태스크 (오류 복구)",
                    "params": {"topic": query},
                    "depends_on": []
                }],
                "error": str(e),
                "reasoning": "오류 발생으로 기본 태스크 생성"
            }
    
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