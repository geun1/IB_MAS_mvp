"""
시스템 성능 지표 수집 모듈
"""
import logging
import time
from typing import Dict, Any, List
import prometheus_client as prom

logger = logging.getLogger(__name__)

# 프로메테우스 지표 정의
TASK_COUNTER = prom.Counter(
    'orchestrator_tasks_total', 
    'Total number of tasks created',
    ['role', 'status']
)

TASK_DURATION = prom.Histogram(
    'orchestrator_task_duration_seconds',
    'Task execution duration in seconds',
    ['role']
)

QUERY_COUNTER = prom.Counter(
    'orchestrator_queries_total',
    'Total number of user queries processed'
)

QUERY_DURATION = prom.Histogram(
    'orchestrator_query_duration_seconds',
    'Query processing duration in seconds'
)

# LLM 호출 지표
LLM_CALLS = prom.Counter(
    'orchestrator_llm_calls_total',
    'Total number of LLM API calls',
    ['operation']
)

LLM_TOKENS = prom.Counter(
    'orchestrator_llm_tokens_total',
    'Total number of tokens used in LLM calls',
    ['operation']
)

class MetricsCollector:
    """지표 수집 클래스"""
    
    @staticmethod
    def start_query_timer() -> float:
        """
        쿼리 처리 타이머 시작
        
        Returns:
            시작 시간
        """
        return time.time()
    
    @staticmethod
    def record_query_completion(start_time: float) -> None:
        """
        쿼리 처리 완료 기록
        
        Args:
            start_time: 시작 시간
        """
        duration = time.time() - start_time
        QUERY_COUNTER.inc()
        QUERY_DURATION.observe(duration)
    
    @staticmethod
    def record_task(role: str, status: str) -> None:
        """
        태스크 생성 기록
        
        Args:
            role: 에이전트 역할
            status: 태스크 상태
        """
        TASK_COUNTER.labels(role=role, status=status).inc()
    
    @staticmethod
    def start_task_timer(role: str) -> Dict[str, Any]:
        """
        태스크 실행 타이머 시작
        
        Args:
            role: 에이전트 역할
            
        Returns:
            타이머 컨텍스트
        """
        return {
            'role': role,
            'start_time': time.time()
        }
    
    @staticmethod
    def record_task_completion(timer_context: Dict[str, Any]) -> None:
        """
        태스크 실행 완료 기록
        
        Args:
            timer_context: 타이머 컨텍스트
        """
        role = timer_context['role']
        duration = time.time() - timer_context['start_time']
        TASK_DURATION.labels(role=role).observe(duration)
    
    @staticmethod
    def record_llm_call(operation: str, tokens: int = 0) -> None:
        """
        LLM API 호출 기록
        
        Args:
            operation: 작업 유형 (예: 'decompose', 'integrate')
            tokens: 사용된 토큰 수
        """
        LLM_CALLS.labels(operation=operation).inc()
        if tokens > 0:
            LLM_TOKENS.labels(operation=operation).inc(tokens) 