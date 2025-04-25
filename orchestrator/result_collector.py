"""
여러 태스크의 결과를 수집하고 통합하는 모듈
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
import time
from random import randint

from .broker_client import BrokerClient
from .llm_client import OrchestratorLLMClient
from .config import DEFAULT_TASK_TIMEOUT
from .models import Task
from .context_manager import ContextManager

# 로깅 설정
logger = logging.getLogger(__name__)

class ResultCollector:
    """태스크 결과 수집 및 통합 클래스"""
    
    def __init__(self, broker_client: BrokerClient, llm_client: OrchestratorLLMClient, context_manager: Optional[ContextManager] = None):
        """
        결과 수집기 초기화
        
        Args:
            broker_client: 브로커 클라이언트
            llm_client: LLM 클라이언트
            context_manager: 컨텍스트 관리자
        """
        self.broker_client = broker_client
        self.llm_client = llm_client
        self.context_manager = context_manager
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
            
    async def integrate_results(self, original_query: str, results: List[Dict[str, Any]], conversation_id: str = None) -> Dict[str, Any]:
        """
        여러 태스크 결과를 통합
        
        Args:
            original_query: 원본 쿼리
            results: 태스크 결과 목록
            conversation_id: 대화 ID
        
        Returns:
            통합된 결과
        """
        try:
            # 성공적인 태스크 결과만 필터링
            successful_results = []
            
            for result in results:
                # 결과의 상태 확인 (completed도 성공으로 간주)
                if (result.get("status") == "success" or result.get("status") == "completed" or 
                    (isinstance(result.get("result"), dict) and result["result"].get("status") == "success")):
                    # 통합할 때 사용할 수 있도록 결과 형식 조정
                    content = None
                    
                    # 직접 content 필드가 있는 경우
                    if "content" in result:
                        content = result["content"]
                    # result 필드 내에 content가 있는 경우 (writer 에이전트)
                    elif isinstance(result.get("result"), dict) and "content" in result["result"]:
                        content = result["result"]["content"]
                    # code_generator 결과인 경우
                    elif isinstance(result.get("result"), dict) and "code_files" in result["result"]:
                        code_files = result["result"]["code_files"]
                        explanation = result["result"].get("explanation", "")
                        content = f"## 코드 설명\n{explanation}\n\n## 코드\n"
                        for filename, code in code_files.items():
                            content += f"\n### {filename}\n```python\n{code}\n```\n"
                    
                    if content:
                        successful_results.append({
                            "task_id": result.get("task_id", ""),
                            "role": result.get("role", "unknown"),
                            "content": content,
                            "description": result.get("description", "")
                        })
                        logger.info(f"통합할 결과에 추가: {result.get('role', 'unknown')} (ID: {result.get('task_id', '')})")
            
            logger.info(f"{len(successful_results)}개의 성공적인 태스크 결과를 통합합니다.")
            
            if not successful_results:
                logger.warning("통합할 성공적인 태스크 결과가 없습니다")
                return {
                    "status": "partial",
                    "message": "태스크가 모두 실패했거나 결과가 없습니다.",
                    "tasks": results
                }
            
            # LLM을 사용하여 결과 통합
            logger.info("LLM을 사용하여 태스크 결과 통합 중...")
            tasks_results_text = ""
            for idx, res in enumerate(successful_results):
                tasks_results_text += f"## 태스크 {idx+1}: {res['description']}\n{res['content']}\n\n"
            
            try:
                integration_result = await self.llm_client.integrate_results(original_query, tasks_results_text)
                
                # LLM 결과가 문자열인 경우 딕셔너리로 변환
                if isinstance(integration_result, str):
                    return {
                        "status": "success",
                        "message": integration_result,
                        "conversation_id": conversation_id
                    }
                # 이미 딕셔너리인 경우 그대로 사용
                elif isinstance(integration_result, dict):
                    if "message" not in integration_result:
                        integration_result["message"] = integration_result.get("content", "결과 생성 완료")
                    integration_result["status"] = "success"
                    integration_result["conversation_id"] = conversation_id
                    return integration_result
                else:
                    # 알 수 없는 형식의 결과
                    logger.warning(f"예상치 못한 결과 형식: {type(integration_result)}")
                    return {
                        "status": "partial",
                        "message": "결과 통합에 문제가 발생했습니다.",
                        "conversation_id": conversation_id,
                        "raw_results": str(integration_result)
                    }
            except Exception as e:
                logger.error(f"결과 통합 중 오류: {str(e)}")
                # 실패해도 원본 결과는 반환
                return {
                    "status": "partial",
                    "message": "모든 태스크가 완료되었으나, 결과 통합 중 오류가 발생했습니다.",
                    "conversation_id": conversation_id,
                    "error": str(e),
                    "tasks": successful_results
                }
        except Exception as e:
            logger.error(f"결과 통합 중 오류: {str(e)}")
            # 오류 발생 시 간단히 결과들을 연결하여 반환
            integration_result = {
                "message": f"태스크 결과 통합 중 오류가 발생했습니다: {str(e)}\n\n원본 태스크 결과: {tasks_results_text}",
                "status": "error"
            }
            return {
                "status": "error",
                "message": integration_result["message"],
                "tasks": successful_results
            }

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        태스크 처리 및 결과 반환
        
        Args:
            task: 처리할 태스크 정보
            
        Returns:
            태스크 처리 결과
        """
        task_role = task.get("role", "unknown")
        task_description = task.get("description", "알 수 없는 태스크")
        conversation_id = task.get("conversation_id", self.current_conversation_id)
        
        # 대화 ID 설정 (없는 경우)
        if not hasattr(self, 'current_conversation_id') or not self.current_conversation_id:
            self.current_conversation_id = conversation_id
        
        # 결과 저장소 초기화
        if not hasattr(self, 'task_results'):
            self.task_results = {}

        # 태스크 ID 초기화 - 태스크에서 가져오거나 생성
        task_id = task.get("task_id", None)
        
        # 의존성 정보 확인
        depends_on = task.get("depends_on", [])
        depends_results = []
        
        # 의존 태스크 결과 수집
        if depends_on:
            logger.info(f"태스크 {task_description}의 의존성 처리 중: {depends_on}")
            for dep_task_id in depends_on:
                # 의존성이 문자열 태스크 ID인지 확인
                if not isinstance(dep_task_id, str) or not dep_task_id.startswith("task_"):
                    logger.warning(f"유효하지 않은 의존성 ID 무시: {dep_task_id}")
                    continue
                    
                logger.info(f"의존성 태스크 결과 조회: {dep_task_id}")
                dep_result = await self.broker_client.get_task_result(dep_task_id)
                
                if dep_result:
                    depends_results.append(dep_result)
                    logger.info(f"의존성 결과 추가: {dep_task_id} (역할: {dep_result.get('role', 'unknown')})")
                else:
                    logger.warning(f"의존성 태스크 {dep_task_id}의 결과를 찾을 수 없습니다")
        
        # 태스크 파라미터 준비
        params = task.get("params", {})
        
        # 컨텍스트 정보 구성
        context = {"depends_results": depends_results} if depends_results else None
        
        # 브로커에 태스크 생성 요청
        task_id = await self.broker_client.create_task(
            role=task_role,
            params=params,
            conversation_id=conversation_id,
            context=context
        )
        
        # 태스크 결과 대기 및 조회
        result = await self.broker_client.wait_for_task_completion(task_id)
        
        # 결과에 메타데이터 추가
        result["task_id"] = task_id
        result["role"] = task_role
        result["description"] = task_description
        
        # level 정보 추가 (의존성 처리를 위해)
        if "level" not in result:
            # role이 code_generator면 level 1, 그 외에는 level 2로 설정
            if task_role == "code_generator":
                result["level"] = 1
            else:
                result["level"] = 2
        
        # 결과 저장
        self.task_results[task_id] = result
        
        return result

    async def process_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        여러 태스크 처리 및 결과 수집
        
        Args:
            tasks: 처리할 태스크 목록
            
        Returns:
            태스크 결과 목록
        """
        try:
            results = []
            self.task_results = {}  # 태스크 결과 저장 딕셔너리 초기화
            
            # 각 태스크 순차 처리
            for task in tasks:
                task_description = task.get("description", "알 수 없는 태스크")
                task_idx = len(results)
                
                # 이전 태스크 결과를 현재 태스크에 전달하기 위한 처리
                if task_idx > 0 and results:
                    # 직전 태스크 결과 추출
                    prev_results = [results[i] for i in range(task_idx) if results[i].get("status") == "completed"]
                    
                    # 태스크에 이전 결과 컨텍스트 추가
                    if "params" not in task:
                        task["params"] = {}
                    
                    # 태스크 역할에 따른 컨텍스트 형식 맞춤화
                    if task.get("role") == "writer" and prev_results:
                        # 코드 생성기 결과가 있는 경우
                        for prev_result in prev_results:
                            if "code_files" in prev_result.get("result", {}):
                                code_content = prev_result["result"]["code_files"].get("main.py", "")
                                explanation = prev_result["result"].get("explanation", "")
                                
                                # writer 에이전트 요청 형식에 맞게 조정
                                task["params"]["code_content"] = code_content
                                task["params"]["code_explanation"] = explanation
                                task["params"]["source_code"] = code_content
                                break
                
                # 태스크 처리 및 결과 저장
                logger.info(f"태스크 {task_idx+1}/{len(tasks)} 처리 중: {task_description}")
                result = await self.process_task(task)
                
                # 태스크 ID 저장 (이후 의존성 처리에 사용)
                task_id = result.get("task_id", f"task_{task_idx}")
                self.task_results[task_id] = result
                
                results.append(result)
            
            # 성공한 태스크 결과 필터링
            successful_results = [r for r in results if r.get("status") == "completed"]
            
            if not successful_results:
                logger.warning("통합할 성공적인 태스크 결과가 없습니다")
                return results
            
            # 태스크 결과 통합 - 결과 수집 및 저장
            logger.info(f"{len(results)}개의 태스크 결과 통합 시작")
            
            return results
        except Exception as e:
            logger.error(f"태스크 처리 중 오류 발생: {str(e)}")
            return []

    async def create_task_with_dependencies(self, role, description, params, dependent_tasks=None):
        """의존성을 설정하여 태스크 생성"""
        task_id = f"task_{role}_{self.current_conversation_id}_{randint(-9223372036854775808, 9223372036854775807)}"
        
        # 로깅 강화
        logger.info(f"태스크 생성: {role} (설명: {description})")
        if dependent_tasks:
            logger.info(f"의존 태스크 설정: {dependent_tasks}")
        
        # 의존성 결과 수집
        depends_results = []
        if dependent_tasks:
            for dep_task_id in dependent_tasks:
                dep_result = await self.broker_client.get_task_result(dep_task_id)
                if dep_result:
                    logger.info(f"의존 태스크 {dep_task_id} 결과 수집됨")
                    depends_results.append(dep_result)
                else:
                    logger.warning(f"의존 태스크 {dep_task_id} 결과를 찾을 수 없음")
        
        # 태스크 생성 요청에 의존성 결과 포함
        context = {"depends_results": depends_results} if depends_results else None
        
        # 태스크 생성 요청
        logger.info(f"브로커에 태스크 생성 요청: {role} ({description})")
        task_id = await self.broker_client.create_task(
            role=role,
            params=params,
            conversation_id=self.current_conversation_id,
            context=context
        )
        
        logger.info(f"태스크 생성 성공: {task_id}")
        return task_id

    def get_all_results(self) -> List[Dict[str, Any]]:
        """
        지금까지 수집된 모든 태스크 결과 반환
        
        Returns:
            태스크 결과 목록
        """
        try:
            # 결과 저장소에서 모든 결과 가져오기
            all_results = []
            
            # self.task_results가 있는 경우 (신규 구현에서 사용)
            if hasattr(self, 'task_results') and self.task_results:
                for task_id, result in self.task_results.items():
                    # 유효한 task_id 확인 및 설정
                    if "task_id" not in result or not result["task_id"]:
                        result["task_id"] = task_id
                    all_results.append(result)
                    logger.info(f"태스크 결과 포함: {task_id} (역할: {result.get('role', 'unknown')})")
            
            # self.results가 있는 경우 (기존 구현에서 사용)
            elif hasattr(self, 'results') and self.results:
                for task_idx, result in self.results.items():
                    # 결과 객체에 level 정보 추가 (의존성 처리를 위해)
                    if isinstance(result, dict) and "level" not in result:
                        task_id = result.get("task_id", "")
                        if task_id and "_" in task_id:
                            # task_id에서 role 추출 (예: task_code_generator_...)
                            parts = task_id.split("_")
                            if len(parts) > 2:
                                role = parts[1]
                                # 첫 번째 레벨인지 여부 결정
                                result["level"] = result.get("level", 1)
                
                    all_results.append(result)
            
            logger.info(f"{len(all_results)}개의 태스크 결과 반환")
            return all_results
        except Exception as e:
            logger.error(f"태스크 결과 수집 중 오류: {str(e)}")
            return [] 