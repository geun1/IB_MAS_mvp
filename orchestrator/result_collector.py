"""
여러 태스크의 결과를 수집하고 통합하는 모듈
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
import time

from .broker_client import BrokerClient
from .llm_client import OrchestratorLLMClient
from .config import DEFAULT_TASK_TIMEOUT

# 로깅 설정
logger = logging.getLogger(__name__)

class ResultCollector:
    """태스크 결과 수집 및 통합 클래스"""
    
    def __init__(self, broker_client: BrokerClient, llm_client: OrchestratorLLMClient):
        """
        결과 수집기 초기화
        
        Args:
            broker_client: 브로커 클라이언트
            llm_client: LLM 클라이언트
        """
        self.broker_client = broker_client
        self.llm_client = llm_client
        self.results = {}
        logger.info("결과 수집기 초기화 완료")
    
    async def execute_tasks(
        self, 
        tasks: List[Dict[str, Any]], 
        conversation_id: str, 
        execution_levels: Optional[List[List[int]]] = None
    ) -> Dict[str, Any]:
        """
        태스크 실행 및 결과 수집
        
        Args:
            tasks: 태스크 목록
            conversation_id: 대화 ID
            execution_levels: 실행 레벨별 태스크 인덱스 목록
            
        Returns:
            실행 결과 딕셔너리
        """
        # 실행 레벨이 없으면 모든 태스크를 하나의 레벨로 간주
        if not execution_levels:
            execution_levels = [[i for i in range(len(tasks))]]
            
        logger.info(f"태스크 실행 시작 (대화 ID: {conversation_id}, 총 {len(tasks)}개)")
        
        # 모든 태스크의 결과를 저장할 딕셔너리
        all_results = {}
        failed_tasks = []
        
        # 각 레벨별로 태스크 실행
        for level_idx, level_tasks in enumerate(execution_levels):
            logger.info(f"레벨 {level_idx+1} 태스크 실행 중 ({len(level_tasks)}개)")
            level_results = await self._execute_level_tasks(level_tasks, tasks, conversation_id)
            
            # 결과 및 실패한 태스크 업데이트
            for task_idx, result in level_results.items():
                all_results[task_idx] = result
                if result.get("status") != "completed":
                    failed_tasks.append(task_idx)
            
            # 중요한 태스크가 실패했으면 나머지 레벨 실행 중단
            if failed_tasks and level_idx < len(execution_levels) - 1:
                logger.warning(f"중요 태스크 {failed_tasks}가 실패하여 남은 레벨 실행 중단")
                break
        
        logger.info(f"모든 태스크 실행 완료 (성공: {len(all_results) - len(failed_tasks)}, 실패: {len(failed_tasks)})")
        
        # 태스크별 정렬된 결과
        ordered_results = [all_results.get(i, {"status": "not_executed"}) for i in range(len(tasks))]
        
        return {
            "conversation_id": conversation_id,
            "results": ordered_results,
            "failed_tasks": failed_tasks,
            "status": "completed" if not failed_tasks else "partially_completed"
        }
    
    async def _execute_level_tasks(
        self, 
        level_tasks: List[int], 
        all_tasks: List[Dict[str, Any]], 
        conversation_id: str
    ) -> Dict[int, Dict[str, Any]]:
        """
        한 레벨의 태스크 병렬 실행
        
        Args:
            level_tasks: 현재 레벨의 태스크 인덱스 목록
            all_tasks: 모든 태스크 목록
            conversation_id: 대화 ID
            
        Returns:
            태스크 인덱스를 키로 하는 결과 딕셔너리
        """
        # 각 태스크별 실행 작업 생성
        tasks_coroutines = []
        for task_idx in level_tasks:
            task_data = all_tasks[task_idx]
            coroutine = self._execute_single_task(task_data, conversation_id, task_idx)
            tasks_coroutines.append(coroutine)
        
        # 병렬 실행 및 결과 수집
        results = await asyncio.gather(*tasks_coroutines, return_exceptions=True)
        
        # 결과 매핑
        level_results = {}
        for i, task_idx in enumerate(level_tasks):
            result = results[i]
            
            # 예외가 반환된 경우 처리
            if isinstance(result, Exception):
                level_results[task_idx] = {
                    "status": "failed",
                    "error": str(result),
                    "task_id": None
                }
                logger.error(f"태스크 {task_idx} 실행 중 예외 발생: {str(result)}")
            else:
                level_results[task_idx] = result
        
        return level_results
    
    async def _execute_single_task(
        self, 
        task: Dict[str, Any], 
        conversation_id: str, 
        task_idx: int
    ) -> Dict[str, Any]:
        """
        단일 태스크 실행
        
        Args:
            task: 태스크 데이터
            conversation_id: 대화 ID
            task_idx: 태스크 인덱스
            
        Returns:
            태스크 실행 결과
        """
        role = task.get("role")
        params = task.get("params", {})
        
        try:
            # 브로커에 태스크 생성 요청
            logger.info(f"태스크 {task_idx} 생성 요청 (역할: {role})")
            task_response = await self.broker_client.create_task(role, params, conversation_id)
            
            # 태스크 ID 가져오기
            task_id = task_response.get("task_id")
            if not task_id:
                return {
                    "status": "failed",
                    "error": "태스크 ID를 가져올 수 없음",
                    "task_id": None
                }
            
            # 태스크 완료 대기
            logger.info(f"태스크 {task_idx} ({task_id}) 완료 대기 중")
            result = await self.broker_client.wait_for_task_completion(
                task_id, timeout=DEFAULT_TASK_TIMEOUT
            )
            
            logger.info(f"태스크 {task_idx} ({task_id}) 완료: {result.get('status')}")
            return result
            
        except Exception as e:
            logger.error(f"태스크 {task_idx} 실행 중 오류: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "task_id": None
            }
            
    async def integrate_results(
        self, 
        original_query: str, 
        results: List[Dict[str, Any]]
    ) -> str:
        """
        태스크 결과 통합하여 최종 응답 생성
        
        Args:
            original_query: 원래 사용자 질의
            results: 태스크 결과 목록
            
        Returns:
            통합된 최종 응답
        """
        # 결과를 LLM 클라이언트에 전달하여 통합
        return await self.llm_client.integrate_results(original_query, results)

    async def process_tasks(self, tasks):
        """
        태스크 처리 및 결과 수집
        """
        results = []
        for task in tasks:
            try:
                # 태스크 처리 로직
                result = await self.process_single_task(task)
                results.append(result)
            except Exception as e:
                logger.error(f"태스크 처리 중 오류 발생: {e}")
                results.append({
                    "status": "error",
                    "error": str(e)
                })
        return results

    async def process_single_task(self, task) -> Dict[str, Any]:
        """
        단일 태스크 처리
        
        Args:
            task: 처리할 태스크 정보
            
        Returns:
            처리 결과
        """
        try:
            # 필요한 정보 추출
            role = task.get("role")
            params = task.get("params", {})
            task_description = task.get("description", "태스크")
            
            if not role:
                logger.error(f"역할이 지정되지 않은 태스크: {task}")
                return {
                    "status": "failed",
                    "error": "태스크 역할이 지정되지 않았습니다",
                    "task_description": task_description
                }
            
            # 브로커 클라이언트를 통해 태스크 생성
            # conversation_id가 없으면 임시 ID 생성
            conversation_id = task.get("conversation_id", f"temp_{int(time.time())}")
            
            logger.info(f"브로커에 태스크 생성 요청: {role} ({task_description})")
            response = await self.broker_client.create_task(role, params, conversation_id)
            
            # 태스크 ID 추출
            task_id = response.get("task_id")
            if not task_id:
                logger.error(f"유효한 태스크 ID를 받지 못함: {response}")
                return {
                    "status": "failed",
                    "error": "유효한 태스크 ID를 받지 못했습니다",
                    "task_description": task_description
                }
            
            # 태스크 완료 대기
            logger.info(f"태스크 {task_id} 완료 대기 중 ({task_description})")
            result = await self.broker_client.wait_for_task_completion(
                task_id, timeout=DEFAULT_TASK_TIMEOUT
            )
            
            # 결과 필드 추가
            result["task_description"] = task_description
            logger.info(f"태스크 {task_id} 완료: {result.get('status')}")
            return result
            
        except Exception as e:
            logger.error(f"태스크 처리 중 오류: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "task_description": task.get("description", "알 수 없는 태스크")
            } 