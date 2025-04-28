"""
Fallback 매니저
ReACT 에이전트의 실패 복구 전략을 관리하는 모듈
"""
import logging
import time
import random
import asyncio
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union, TypeVar, Generic

logger = logging.getLogger(__name__)

# Fallback 상태
class FallbackStatus(str, Enum):
    SUCCESS = "success"         # 성공적으로 복구됨
    RETRY = "retry"             # 재시도 필요
    ALTERNATIVE = "alternative" # 대체 전략 사용
    FAILURE = "failure"         # 최종 실패

# Fallback 결과 타입 정의
T = TypeVar('T')
class FallbackResult(Generic[T]):
    """Fallback 처리 결과"""
    
    def __init__(
        self, 
        status: FallbackStatus,
        result: Optional[T] = None,
        message: str = "",
        attempt: int = 0,
        metadata: Dict[str, Any] = None
    ):
        self.status = status
        self.result = result
        self.message = message
        self.attempt = attempt
        self.metadata = metadata or {}
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "status": self.status.value,
            "result": self.result,
            "message": self.message,
            "attempt": self.attempt,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def success(cls, result: T, message: str = "성공적으로 복구됨", metadata: Dict[str, Any] = None) -> 'FallbackResult[T]':
        """성공 결과 생성"""
        return cls(
            status=FallbackStatus.SUCCESS,
            result=result,
            message=message,
            metadata=metadata
        )
    
    @classmethod
    def retry(cls, message: str = "재시도 필요", attempt: int = 1, metadata: Dict[str, Any] = None) -> 'FallbackResult[T]':
        """재시도 결과 생성"""
        return cls(
            status=FallbackStatus.RETRY,
            message=message,
            attempt=attempt,
            metadata=metadata
        )
    
    @classmethod
    def alternative(cls, result: T, message: str = "대체 전략 사용", metadata: Dict[str, Any] = None) -> 'FallbackResult[T]':
        """대체 전략 결과 생성"""
        return cls(
            status=FallbackStatus.ALTERNATIVE,
            result=result,
            message=message,
            metadata=metadata
        )
    
    @classmethod
    def failure(cls, message: str = "복구 실패", metadata: Dict[str, Any] = None) -> 'FallbackResult[T]':
        """실패 결과 생성"""
        return cls(
            status=FallbackStatus.FAILURE,
            message=message,
            metadata=metadata
        )

# Fallback 전략 정의
class FallbackStrategy:
    """Fallback 전략"""
    
    def __init__(
        self, 
        name: str, 
        handler: Callable,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        jitter: float = 0.5,
        description: str = "",
        order: int = 0
    ):
        """
        Fallback 전략 초기화
        
        Args:
            name: 전략 이름
            handler: 전략 처리 함수
            max_retries: 최대 재시도 횟수
            retry_delay: 재시도 지연 시간 (초)
            jitter: 지연 시간 변동폭 (초)
            description: 전략 설명
            order: 전략 실행 순서 (낮을수록 먼저 실행)
        """
        self.name = name
        self.handler = handler
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.jitter = jitter
        self.description = description
        self.order = order
    
    async def execute(self, context: Dict[str, Any], attempt: int = 1) -> FallbackResult:
        """
        전략 실행
        
        Args:
            context: 실행 컨텍스트
            attempt: 시도 횟수
            
        Returns:
            FallbackResult: 실행 결과
        """
        logger.info(f"Fallback 전략 '{self.name}' 실행 (시도 {attempt}/{self.max_retries})")
        
        try:
            # 전략 함수 호출
            result = await self.handler(context, attempt)
            
            # 결과가 FallbackResult 타입이 아닌 경우 변환
            if not isinstance(result, FallbackResult):
                result = FallbackResult.success(result, f"전략 '{self.name}' 성공")
            
            return result
            
        except Exception as e:
            logger.error(f"Fallback 전략 '{self.name}' 실행 중 오류: {str(e)}")
            
            # 재시도 여부 결정
            if attempt < self.max_retries:
                # 지연 시간 계산 (지터 추가)
                delay = self.retry_delay + random.uniform(-self.jitter, self.jitter)
                delay = max(0.1, delay)  # 최소 0.1초
                
                logger.info(f"Fallback 전략 '{self.name}' {delay:.2f}초 후 재시도 예정 ({attempt}/{self.max_retries})")
                
                # 지연 후 재시도
                await asyncio.sleep(delay)
                return await self.execute(context, attempt + 1)
            else:
                # 최대 재시도 횟수 초과
                return FallbackResult.failure(
                    message=f"전략 '{self.name}' 최대 재시도 횟수 초과: {str(e)}",
                    metadata={"error": str(e), "error_type": type(e).__name__}
                )

class FallbackManager:
    """
    Fallback 관리자
    다양한 실패 상황에 대한 복구 전략을 관리하고 실행
    """
    
    def __init__(self):
        """Fallback 관리자 초기화"""
        # 실패 유형별 전략 목록
        self.strategies: Dict[str, List[FallbackStrategy]] = {}
        
        # 기본 전략 등록
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """기본 전략 등록"""
        # 예: 태스크 실행 실패에 대한 기본 전략
        self.register_strategy(
            "task_execution_failure",
            FallbackStrategy(
                name="simple_retry",
                handler=self._simple_retry_handler,
                max_retries=3,
                retry_delay=2.0,
                description="단순 재시도 전략",
                order=0
            )
        )
        
        # 에이전트 선택 실패에 대한 기본 전략
        self.register_strategy(
            "agent_selection_failure",
            FallbackStrategy(
                name="find_alternative_agent",
                handler=self._find_alternative_agent_handler,
                max_retries=2,
                description="대체 에이전트 검색 전략",
                order=0
            )
        )
        
        # 파라미터 유효성 검사 실패에 대한 기본 전략
        self.register_strategy(
            "param_validation_failure",
            FallbackStrategy(
                name="param_fix_retry",
                handler=self._param_fix_retry_handler,
                max_retries=2,
                description="파라미터 수정 후 재시도 전략",
                order=0
            )
        )
    
    def register_strategy(self, failure_type: str, strategy: FallbackStrategy):
        """
        Fallback 전략 등록
        
        Args:
            failure_type: 실패 유형
            strategy: Fallback 전략
        """
        if failure_type not in self.strategies:
            self.strategies[failure_type] = []
        
        # 전략 추가
        self.strategies[failure_type].append(strategy)
        
        # 순서대로 정렬
        self.strategies[failure_type].sort(key=lambda s: s.order)
        
        logger.info(f"Fallback 전략 '{strategy.name}' 등록됨 (유형: {failure_type})")
    
    async def handle_failure(
        self, 
        failure_type: str, 
        context: Dict[str, Any], 
        error: Optional[Exception] = None
    ) -> FallbackResult:
        """
        실패 처리
        
        Args:
            failure_type: 실패 유형
            context: 실행 컨텍스트
            error: 발생한 오류 (선택적)
            
        Returns:
            FallbackResult: 처리 결과
        """
        # 컨텍스트에 오류 정보 추가
        if error:
            context["error"] = {
                "message": str(error),
                "type": type(error).__name__
            }
        
        # 등록된 전략 확인
        if failure_type not in self.strategies or not self.strategies[failure_type]:
            logger.warning(f"실패 유형 '{failure_type}'에 대한 전략이 없습니다.")
            return FallbackResult.failure(message=f"실패 유형 '{failure_type}'에 대한 복구 전략이 없습니다.")
        
        # 모든 전략 시도
        last_result = None
        for strategy in self.strategies[failure_type]:
            # 이전 전략이 성공 또는 대체 전략을 사용한 경우 중단
            if last_result and last_result.status in [FallbackStatus.SUCCESS, FallbackStatus.ALTERNATIVE]:
                break
            
            # 전략 실행
            result = await strategy.execute(context)
            last_result = result
            
            logger.info(f"Fallback 전략 '{strategy.name}' 결과: {result.status.value}")
            
            # 성공 또는 대체 전략 사용 시 종료
            if result.status in [FallbackStatus.SUCCESS, FallbackStatus.ALTERNATIVE]:
                return result
        
        # 모든 전략 실패
        if not last_result:
            return FallbackResult.failure(message=f"모든 전략 실행 실패 (유형: {failure_type})")
        
        return last_result
    
    # 기본 전략 핸들러들
    
    async def _simple_retry_handler(self, context: Dict[str, Any], attempt: int) -> FallbackResult:
        """단순 재시도 전략 핸들러"""
        # 예시 구현: 단순히 재시도 상태 반환
        if attempt < 3:
            return FallbackResult.retry(
                message=f"단순 재시도 중 ({attempt}/3)",
                attempt=attempt,
                metadata={"context_keys": list(context.keys())}
            )
        else:
            # 마지막 시도에서는 실패로 처리
            return FallbackResult.failure(
                message="최대 재시도 횟수 초과",
                metadata={"max_attempts": 3, "context_keys": list(context.keys())}
            )
    
    async def _find_alternative_agent_handler(self, context: Dict[str, Any], attempt: int) -> FallbackResult:
        """대체 에이전트 검색 전략 핸들러"""
        # 예시 구현: 컨텍스트에서 원하는 역할과 비슷한 다른 역할 찾기
        original_role = context.get("original_role", "")
        
        if not original_role:
            return FallbackResult.failure(message="원본 역할 정보가 없습니다.")
        
        # 실제 구현에서는 레지스트리에서 유사한 역할 검색
        alternative_roles = {
            "writer": ["content_creator", "reporter"],
            "web_search": ["search_engine", "researcher"],
            "calculator": ["math_solver", "formula_processor"]
        }
        
        alternatives = alternative_roles.get(original_role, [])
        
        if not alternatives:
            return FallbackResult.failure(message=f"역할 '{original_role}'에 대한 대체 에이전트가 없습니다.")
        
        # 대체 역할 반환
        alternative_role = alternatives[min(attempt - 1, len(alternatives) - 1)]
        
        return FallbackResult.alternative(
            result={"alternative_role": alternative_role},
            message=f"대체 역할 '{alternative_role}' 찾음",
            metadata={"original_role": original_role}
        )
    
    async def _param_fix_retry_handler(self, context: Dict[str, Any], attempt: int) -> FallbackResult:
        """파라미터 수정 후 재시도 전략 핸들러"""
        # 예시 구현: 문제가 있는 파라미터 식별 및 수정
        params = context.get("params", {})
        validation_errors = context.get("validation_errors", {})
        
        if not validation_errors:
            return FallbackResult.failure(message="유효성 검사 오류 정보가 없습니다.")
        
        # 기본 값 적용 또는 문제 파라미터 제거
        fixed_params = params.copy()
        
        for param_name, error in validation_errors.items():
            if param_name in fixed_params:
                # 간단한 기본값 적용 예시
                if isinstance(fixed_params[param_name], str) and not fixed_params[param_name]:
                    fixed_params[param_name] = f"default_value_{attempt}"
                elif isinstance(fixed_params[param_name], int) and fixed_params[param_name] < 0:
                    fixed_params[param_name] = 0
                else:
                    # 복잡한 유형은 제거
                    del fixed_params[param_name]
        
        return FallbackResult.alternative(
            result={"fixed_params": fixed_params},
            message=f"파라미터 수정됨 ({len(validation_errors)}개 항목)",
            metadata={"original_params": params, "validation_errors": validation_errors}
        ) 