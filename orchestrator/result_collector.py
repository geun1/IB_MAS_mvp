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
        log_id = f"INTEGRATE_{int(time.time())}"
        
        try:
            # 로깅: 통합 시작 정보
            logger.info(f"[{log_id}] 결과 통합 시작: 원본 쿼리='{original_query}', 결과 수={len(results)}")
            logger.info(f"[{log_id}] 전체 결과 목록: {[r.get('task_id', 'unknown') for r in results]}")
            
            # 모든 결과의 상태 로깅
            for idx, result in enumerate(results):
                task_id = result.get('task_id', f'unknown_{idx}')
                status = result.get('status', 'unknown')
                role = result.get('role', 'unknown')
                
                # 상세 상태 정보
                result_data = result.get('result', {})
                inner_status = None
                if isinstance(result_data, dict):
                    inner_status = result_data.get('status')
                
                logger.info(f"[{log_id}] 결과[{idx}] 상태 확인: ID={task_id}, 역할={role}, 상태={status}, 내부상태={inner_status}")
            
            # 성공적인 태스크 결과만 필터링 (조건 확장)
            successful_results = []
            
            for result in results:
                # 매우 상세한 상태 로깅
                task_id = result.get('task_id', 'unknown')
                status = result.get('status', 'unknown')
                
                # 결과 구조 로깅 - 디버깅에 유용
                logger.info(f"[{log_id}] 결과 구조 분석: ID={task_id}")
                logger.info(f"[{log_id}] - 최상위 키: {list(result.keys())}")
                
                if 'result' in result and isinstance(result['result'], dict):
                    logger.info(f"[{log_id}] - result 내부 키: {list(result['result'].keys())}")
                
                # 성공 조건 확인 (조건 확장)
                is_success = False
                success_reason = "실패"
                
                # 조건 1: 최상위 status가 success 또는 completed
                if status in ['success', 'completed']:
                    is_success = True
                    success_reason = f"최상위 상태가 '{status}'임"
                
                # 조건 2: result 딕셔너리 내부의 status가 success
                elif isinstance(result.get('result'), dict) and result['result'].get('status') in ['success', 'completed']:
                    is_success = True  
                    success_reason = f"내부 result 상태가 '{result['result'].get('status')}'임"
                
                # 내용 추출 로직
                content = None
                content_source = "없음"
                
                # 직접 content 필드가 있는 경우
                if "content" in result:
                    content = result["content"]
                    content_source = "최상위 content"
                # result 필드 내에 content가 있는 경우 (writer 에이전트)
                elif isinstance(result.get("result"), dict) and "content" in result["result"]:
                    content = result["result"]["content"]
                    content_source = "result.content"
                # result.result.content (writer agent의 중첩 구조)
                elif (
                    isinstance(result.get("result"), dict)
                    and isinstance(result["result"].get("result"), dict)
                    and "content" in result["result"]["result"]
                ):
                    content = result["result"]["result"]["content"]
                    content_source = "result.result.content"
                # code_generator 결과인 경우
                elif isinstance(result.get("result"), dict) and "code_files" in result["result"]:
                    code_files = result["result"]["code_files"]
                    explanation = result["result"].get("explanation", "")
                    content = f"## 코드 설명\n{explanation}\n\n## 코드\n"
                    for filename, code in code_files.items():
                        content += f"\n### {filename}\n```python\n{code}\n```\n"
                    content_source = "code_files + explanation"
                
                # 내용 및 성공 여부 로깅
                has_content = content is not None and len(str(content).strip()) > 0
                logger.info(f"[{log_id}] 결과 평가: ID={task_id}, 성공={is_success} ({success_reason}), " 
                           f"내용={has_content} (출처: {content_source})")
                
                # 성공이고 내용이 있으면 통합 대상에 추가
                if is_success and has_content:
                    successful_results.append({
                        "task_id": result.get("task_id", ""),
                        "role": result.get("role", "unknown"),
                        "content": content,
                        "description": result.get("description", "")
                    })
                    logger.info(f"[{log_id}] 통합 대상에 추가됨: {result.get('task_id', '')}")
                else:
                    logger.warning(f"[{log_id}] 통합 대상에서 제외됨: {result.get('task_id', '')}, " 
                                 f"이유: {'성공 아님' if not is_success else '내용 없음'}")
            
            logger.info(f"[{log_id}] {len(successful_results)}개의 성공적인 태스크 결과를 통합합니다.")
            
            if not successful_results:
                logger.warning(f"[{log_id}] 통합할 성공적인 태스크 결과가 없습니다")
                # 원본 결과 로깅
                logger.error(f"[{log_id}] 전체 원본 결과: {results}")
                return {
                    "status": "partial",
                    "message": "태스크가 모두 실패했거나 결과가 없습니다.",
                    "tasks": results
                }
            
            # LLM을 사용하여 결과 통합
            logger.info(f"[{log_id}] LLM을 사용하여 태스크 결과 통합 중...")
            tasks_results_text = ""
            for idx, res in enumerate(successful_results):
                tasks_results_text += f"## 태스크 {idx+1}: {res['description']}\n{res['content']}\n\n"
            
            logger.info(f"[{log_id}] 통합할 텍스트 준비 완료 (길이: {len(tasks_results_text)})")
            
            try:
                integration_result = await self.llm_client.integrate_results(original_query, tasks_results_text)
                logger.info(f"[{log_id}] LLM 통합 결과 수신 (타입: {type(integration_result)})")
                
                # LLM 결과가 문자열인 경우 딕셔너리로 변환
                if isinstance(integration_result, str):
                    logger.info(f"[{log_id}] 문자열 통합 결과 변환 (길이: {len(integration_result)})")
                    return {
                        "status": "success",
                        "message": integration_result,
                        "conversation_id": conversation_id
                    }
                # 이미 딕셔너리인 경우 그대로 사용
                elif isinstance(integration_result, dict):
                    logger.info(f"[{log_id}] 딕셔너리 통합 결과 키: {list(integration_result.keys())}")
                    if "message" not in integration_result:
                        integration_result["message"] = integration_result.get("content", "결과 생성 완료")
                    integration_result["status"] = "success"
                    integration_result["conversation_id"] = conversation_id
                    return integration_result
                else:
                    # 알 수 없는 형식의 결과
                    logger.warning(f"[{log_id}] 예상치 못한 결과 형식: {type(integration_result)}")
                    return {
                        "status": "partial",
                        "message": "결과 통합에 문제가 발생했습니다.",
                        "conversation_id": conversation_id,
                        "raw_results": str(integration_result)
                    }
            except Exception as e:
                logger.error(f"[{log_id}] 결과 통합 중 오류: {str(e)}", exc_info=True)
                # 실패해도 원본 결과는 반환
                return {
                    "status": "partial",
                    "message": "모든 태스크가 완료되었으나, 결과 통합 중 오류가 발생했습니다.",
                    "conversation_id": conversation_id,
                    "error": str(e),
                    "tasks": successful_results
                }
        except Exception as e:
            logger.error(f"[{log_id}] 결과 통합 중 예외 발생: {str(e)}", exc_info=True)
            # 오류 발생 시 간단히 결과들을 연결하여 반환
            return {
                "status": "error",
                "message": f"태스크 결과 통합 중 오류가 발생했습니다: {str(e)}",
                "tasks": results
            }

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        태스크 처리 및 결과 반환
        
        Args:
            task: 처리할 태스크 정보
            
        Returns:
            태스크 처리 결과
        """
        # 로깅 ID 생성 (디버깅 추적용)
        log_id = f"TASK_{int(time.time())}_{id(task)}"
        
        try:
            # 태스크 메타 정보 로깅
            task_role = task.get("role", "unknown")
            task_description = task.get("description", "알 수 없는 태스크")
            conversation_id = task.get("conversation_id", self.current_conversation_id)
            
            logger.info(f"[{log_id}] 태스크 처리 시작: 역할={task_role}, 설명={task_description}")
            logger.info(f"[{log_id}] 태스크 전체 데이터: {task}")
            
            # 대화 ID 설정 (없는 경우)
            if not hasattr(self, 'current_conversation_id') or not self.current_conversation_id:
                self.current_conversation_id = conversation_id
                logger.info(f"[{log_id}] 현재 대화 ID 설정: {conversation_id}")
            
            # 결과 저장소 초기화
            if not hasattr(self, 'task_results'):
                self.task_results = {}
                logger.info(f"[{log_id}] 태스크 결과 저장소 초기화")

            # 태스크 ID 초기화 - 태스크에서 가져오거나 생성
            task_id = task.get("task_id", None)
            logger.info(f"[{log_id}] 태스크 ID: {task_id}")
            
            # 의존성 정보 확인
            depends_on = task.get("depends_on", [])
            depends_results = []
            
            # 의존 태스크 결과 수집
            if depends_on:
                logger.info(f"[{log_id}] 태스크의 의존성 처리 시작: {depends_on}")
                for dep_task_id in depends_on:
                    # 의존성이 문자열 태스크 ID인지 확인
                    if not isinstance(dep_task_id, str) or not dep_task_id.startswith("task_"):
                        logger.warning(f"[{log_id}] 유효하지 않은 의존성 ID 무시: {dep_task_id} (타입: {type(dep_task_id)})")
                        continue
                        
                    logger.info(f"[{log_id}] 의존성 태스크 결과 조회 중: {dep_task_id}")
                    try:
                        dep_result = await self.broker_client.get_task_result(dep_task_id)
                        
                        if dep_result:
                            logger.info(f"[{log_id}] 의존성 결과 추가 성공: {dep_task_id}")
                            logger.debug(f"[{log_id}] 의존성 결과 데이터: {dep_result}")
                            depends_results.append(dep_result)
                        else:
                            logger.warning(f"[{log_id}] 의존성 태스크 {dep_task_id}의 결과가 없음 (None)")
                    except Exception as e:
                        logger.error(f"[{log_id}] 의존성 결과 조회 중 오류: {str(e)}")
                
                logger.info(f"[{log_id}] 의존성 처리 완료: {len(depends_results)}개 성공")
            
            # 태스크 파라미터 준비
            params = task.get("params", {})
            logger.info(f"[{log_id}] 태스크 파라미터: {params}")
            
            # 컨텍스트 정보 구성
            context = {"depends_results": depends_results} if depends_results else None
            logger.info(f"[{log_id}] 컨텍스트 구성 완료: {context is not None}")
            
            # 브로커에 태스크 생성 요청
            logger.info(f"[{log_id}] 브로커에 태스크 생성 요청: 역할={task_role}, 대화ID={conversation_id}")
            try:
                task_id = await self.broker_client.create_task(
                    role=task_role,
                    params=params,
                    conversation_id=conversation_id,
                    context=context
                )
                logger.info(f"[{log_id}] 브로커 태스크 생성 성공: {task_id}")
            except Exception as e:
                logger.error(f"[{log_id}] 브로커 태스크 생성 중 오류: {str(e)}", exc_info=True)
                raise
            
            # 태스크 결과 대기 및 조회
            logger.info(f"[{log_id}] 태스크 {task_id} 완료 대기 중...")
            try:
                start_time = time.time()
                result = await self.broker_client.wait_for_task_completion(task_id)
                elapsed_time = time.time() - start_time
                logger.info(f"[{log_id}] 태스크 {task_id} 완료 (소요시간: {elapsed_time:.2f}초)")
                logger.debug(f"[{log_id}] 태스크 결과 데이터: {result}")
            except Exception as e:
                logger.error(f"[{log_id}] 태스크 결과 대기 중 오류: {str(e)}", exc_info=True)
                raise
            
            # 결과 검증
            if not result:
                logger.warning(f"[{log_id}] 태스크 결과가 없음 (None)")
                result = {
                    "status": "failed",
                    "error": "태스크 결과가 없음"
                }
            
            # 결과 상태 확인
            status = result.get("status", "unknown")
            logger.info(f"[{log_id}] 태스크 상태: {status}")
            
            # 결과에 메타데이터 추가
            result["task_id"] = task_id
            result["role"] = task_role
            result["description"] = task_description
            
            # level 정보 추가 (의존성 처리를 위해)
            if "level" not in result:
                # role이 code_generator면 level 1, 그 외에는 level 2로 설정
                level = 1 if task_role == "code_generator" else 2
                result["level"] = level
                logger.info(f"[{log_id}] 태스크 레벨 설정: {level}")
            
            # 결과의 content/output 형식 확인
            if isinstance(result.get("result"), dict):
                logger.info(f"[{log_id}] 결과 내부 키: {result['result'].keys()}")
                if "content" in result["result"]:
                    logger.info(f"[{log_id}] 결과 content 존재 (길이: {len(str(result['result']['content']))})")
                if "output" in result["result"]:
                    logger.info(f"[{log_id}] 결과 output 존재 (길이: {len(str(result['result']['output']))})")
            
            # 결과 저장
            self.task_results[task_id] = result
            logger.info(f"[{log_id}] 태스크 결과 저장 완료 (task_id: {task_id})")
            
            return result
        except Exception as e:
            logger.error(f"[{log_id}] 태스크 처리 중 예외 발생: {str(e)}", exc_info=True)
            # 오류가 발생해도 최소한의 결과 반환
            error_result = {
                "status": "failed",
                "error": str(e),
                "task_id": task.get("task_id", None) or f"error_{int(time.time())}",
                "role": task.get("role", "unknown"),
                "description": task.get("description", "알 수 없는 태스크")
            }
            return error_result

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