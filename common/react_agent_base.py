"""
ReACT (Reasoning + Acting) 에이전트 기본 클래스
추론-행동-관찰 루프를 관리하는 추상 클래스
"""
import logging
import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import HTTPException

# 필요한 공통 모듈 임포트
try:
    from common.base_agent import BaseAgent
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.append(project_root)
    from common.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ReACT 단계 상태 정의
class ReACTStepType(str, Enum):
    REASONING = "reasoning"
    ACTION = "action"
    OBSERVATION = "observation"
    NEXT_STEP = "next_step"
    COMPLETE = "complete"
    ERROR = "error"

# ReACT 단계 정보 모델
class ReACTStep(BaseModel):
    step_id: str = Field(..., description="단계 고유 ID")
    step_type: ReACTStepType = Field(..., description="단계 유형")
    content: Any = Field(..., description="단계 내용 (추론 결과, 행동 내용, 관찰 결과 등)")
    timestamp: float = Field(..., description="단계 시작 시간 (유닉스 타임스탬프)")
    duration: Optional[float] = Field(None, description="단계 실행 소요 시간 (초)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")

# ReACT 세션 상태 모델
class ReACTSession(BaseModel):
    session_id: str = Field(..., description="세션 고유 ID")
    task_id: str = Field(..., description="태스크 ID")
    steps: List[ReACTStep] = Field(default_factory=list, description="단계 기록")
    current_step: Optional[str] = Field(None, description="현재 단계 ID")
    status: str = Field("active", description="세션 상태 (active/completed/failed)")
    created_at: float = Field(..., description="세션 생성 시간 (유닉스 타임스탬프)")
    updated_at: float = Field(..., description="세션 마지막 업데이트 시간")
    max_steps: int = Field(10, description="최대 단계 수 (무한 루프 방지)")
    variables: Dict[str, Any] = Field(default_factory=dict, description="세션 변수 (컨텍스트)")
    fallback_attempts: Dict[str, int] = Field(default_factory=dict, description="단계별 fallback 시도 횟수")

class ReACTAgentBase(BaseAgent):
    """
    ReACT (Reasoning + Acting) 에이전트 기본 클래스
    추론-행동-관찰 루프를 관리하는 추상 클래스
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_role: str,
        description: str,
        app,
        params: List[Dict[str, Any]] = None,
        registry_url: str = None,
        container_name: str = None,
        port: int = None,
        heartbeat_interval: int = 20,
        enable_heartbeat: bool = True,
        max_steps_per_session: int = 10,
        fallback_max_retries: int = 3,
        **kwargs
    ):
        """
        ReACT 에이전트 초기화
        
        추가 파라미터:
            max_steps_per_session: 세션당 최대 단계 수 (무한 루프 방지)
            fallback_max_retries: 단계별 최대 fallback 시도 횟수
        """
        super().__init__(
            agent_id=agent_id,
            agent_role=agent_role,
            description=description,
            app=app,
            params=params,
            registry_url=registry_url,
            container_name=container_name,
            port=port,
            heartbeat_interval=heartbeat_interval,
            enable_heartbeat=enable_heartbeat,
            **kwargs
        )
        
        # ReACT 에이전트 관련 설정
        self.max_steps_per_session = max_steps_per_session
        self.fallback_max_retries = fallback_max_retries
        
        # 활성 세션 저장소
        self.active_sessions = {}
        
        # 브로커 클라이언트 설정
        self.broker_url = kwargs.get("broker_url") or os.getenv("BROKER_URL", "http://broker:8000")
        
        logger.info(f"ReACT 에이전트 '{agent_role}' ({agent_id}) 초기화 완료")
    
    async def process_task(
        self, 
        task_id: str,
        params: Dict[str, Any], 
        dependencies: List[Dict[str, Any]],
        raw_task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        BaseAgent의 process_task 메서드 구현
        
        이 메서드는 ReACT 루프를 시작하고 최종 결과를 반환합니다.
        """
        import time
        
        # 세션 생성
        session_id = f"react_{task_id}_{int(time.time())}"
        session = self._create_session(session_id, task_id)
        
        # 세션 활성화
        self.active_sessions[session_id] = session
        
        try:
            # ReACT 루프 실행
            result = await self._run_react_loop(session, params, dependencies, raw_task_data)
            
            # 세션 상태 업데이트
            session.status = "completed"
            session.updated_at = time.time()
            
            # 결과 반환
            return result
            
        except Exception as e:
            # 오류 발생 시 세션 상태 업데이트
            session.status = "failed"
            session.updated_at = time.time()
            
            # 실패 단계 기록
            error_step = ReACTStep(
                step_id=f"{session_id}_error",
                step_type=ReACTStepType.ERROR,
                content=str(e),
                timestamp=time.time(),
                metadata={"error_type": type(e).__name__}
            )
            session.steps.append(error_step)
            
            logger.error(f"ReACT 세션 '{session_id}' 실행 중 오류 발생: {str(e)}")
            raise
        
        finally:
            # 세션 정리
            if session_id in self.active_sessions:
                # 실제 프로덕션에서는 세션을 바로 삭제하지 않고 캐싱/저장할 수 있음
                del self.active_sessions[session_id]
    
    def _create_session(self, session_id: str, task_id: str) -> ReACTSession:
        """새 ReACT 세션 생성"""
        import time
        now = time.time()
        
        return ReACTSession(
            session_id=session_id,
            task_id=task_id,
            created_at=now,
            updated_at=now,
            max_steps=self.max_steps_per_session
        )
    
    async def _run_react_loop(
        self, 
        session: ReACTSession,
        params: Dict[str, Any],
        dependencies: List[Dict[str, Any]],
        raw_task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ReACT 루프 실행 (추론 → 행동 → 관찰 → 반복)
        
        Args:
            session: 현재 세션
            params: 태스크 파라미터
            dependencies: 의존성 결과
            raw_task_data: 원본 태스크 데이터
            
        Returns:
            최종 결과
        """
        import time
        
        # 초기 컨텍스트 설정
        context = {
            "params": params,
            "dependencies": dependencies,
            "raw_task_data": raw_task_data,
            "session": session.dict(exclude={"steps"}),
            "step_history": []
        }
        
        # 세션 변수 초기화
        session.variables.update({
            "task_params": params,
            "initial_dependencies": dependencies
        })
        
        step_count = 0
        
        # 완료되거나 최대 단계 수에 도달할 때까지 루프 실행
        while step_count < session.max_steps:
            step_count += 1
            
            # 1. Reasoning 단계
            reasoning_result = await self._execute_reasoning(session, context)
            if self._should_complete(reasoning_result, context):
                break
                
            # 2. Action 단계
            action_result = await self._execute_action(session, reasoning_result, context)
            if self._should_complete(action_result, context):
                break
                
            # 3. Observation 단계
            observation_result = await self._execute_observation(session, action_result, context)
            
            # 4. 컨텍스트 업데이트 (다음 단계의 추론에 사용)
            context["step_history"].append({
                "reasoning": reasoning_result,
                "action": action_result,
                "observation": observation_result
            })
            
            # 완료 여부 확인
            if self._should_complete(observation_result, context):
                break
        
        # 최대 단계 수 도달 시 최종 결과 생성
        if step_count >= session.max_steps:
            logger.warning(f"ReACT 세션 '{session.session_id}'가 최대 단계 수({session.max_steps})에 도달했습니다.")
            
            # 최종 단계 기록
            final_step = ReACTStep(
                step_id=f"{session.session_id}_final",
                step_type=ReACTStepType.COMPLETE,
                content="최대 단계 수 도달로 인한 강제 종료",
                timestamp=time.time(),
                metadata={"forced": True}
            )
            session.steps.append(final_step)
        
        # 최종 결과 생성
        final_result = await self._generate_final_result(session, context)
        return final_result
    
    @abstractmethod
    async def _execute_reasoning(
        self, 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        추론 단계 실행 (구체적인 에이전트에서 구현)
        지금까지의 정보를 기반으로 다음 단계를 결정합니다.
        """
        raise NotImplementedError("_execute_reasoning 메서드를 구현해야 합니다.")
    
    @abstractmethod
    async def _execute_action(
        self, 
        session: ReACTSession, 
        reasoning_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        행동 단계 실행 (구체적인 에이전트에서 구현)
        추론 결과를 바탕으로 실제 행동(Task 실행)을 수행합니다.
        """
        raise NotImplementedError("_execute_action 메서드를 구현해야 합니다.")
    
    @abstractmethod
    async def _execute_observation(
        self, 
        session: ReACTSession, 
        action_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        관찰 단계 실행 (구체적인 에이전트에서 구현)
        행동의 결과를 관찰하고 다음 추론을 위한 정보를 수집합니다.
        """
        raise NotImplementedError("_execute_observation 메서드를 구현해야 합니다.")
    
    @abstractmethod
    async def _generate_final_result(
        self, 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        최종 결과 생성 (구체적인 에이전트에서 구현)
        전체 추론-행동-관찰 과정의 결과를 종합합니다.
        """
        raise NotImplementedError("_generate_final_result 메서드를 구현해야 합니다.")
    
    @abstractmethod
    async def _should_complete(
        self, 
        step_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> bool:
        """
        완료 여부 판단 (구체적인 에이전트에서 구현)
        현재 단계 결과를 바탕으로 ReACT 루프를 종료할지 여부를 결정합니다.
        """
        raise NotImplementedError("_should_complete 메서드를 구현해야 합니다.")
    
    async def _handle_fallback(
        self, 
        session: ReACTSession, 
        step_type: ReACTStepType, 
        error: Exception, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fallback 처리 (기본 구현, 필요시 오버라이드)
        
        Args:
            session: 현재 세션
            step_type: 실패한 단계 유형
            error: 발생한 오류
            context: 현재 컨텍스트
            
        Returns:
            Fallback 결과
        """
        step_id = session.current_step or f"{session.session_id}_{step_type.value}"
        
        # Fallback 시도 횟수 증가
        if step_id not in session.fallback_attempts:
            session.fallback_attempts[step_id] = 0
        session.fallback_attempts[step_id] += 1
        
        # 최대 재시도 횟수 초과 시 오류 발생
        if session.fallback_attempts[step_id] > self.fallback_max_retries:
            logger.error(f"Fallback 최대 재시도 횟수({self.fallback_max_retries}) 초과: {step_id}")
            raise HTTPException(
                status_code=500,
                detail=f"Fallback 최대 재시도 횟수 초과: {step_type.value} 단계에서 오류가 계속 발생합니다."
            )
        
        logger.warning(f"Fallback 시도({session.fallback_attempts[step_id]}/{self.fallback_max_retries}): {step_type.value} - {str(error)}")
        
        # 기본 Fallback 전략 - 단순 오류 메시지 반환 (실제 구현에서는 오버라이드하여 확장)
        fallback_result = {
            "fallback": True,
            "attempt": session.fallback_attempts[step_id],
            "error": str(error),
            "step_type": step_type.value
        }
        
        # 단계별로 다른 Fallback 전략 적용 가능 (구체적인 에이전트에서 구현)
        if step_type == ReACTStepType.REASONING:
            fallback_result["result"] = "추론 단계 실패로 인한 Fallback"
        elif step_type == ReACTStepType.ACTION:
            fallback_result["result"] = "행동 단계 실패로 인한 Fallback"
        elif step_type == ReACTStepType.OBSERVATION:
            fallback_result["result"] = "관찰 단계 실패로 인한 Fallback"
        
        return fallback_result
    
    async def submit_task_to_broker(
        self, 
        role: str, 
        params: Dict[str, Any],
        exclude_self: bool = True
    ) -> Dict[str, Any]:
        """
        브로커에 태스크 제출
        
        Args:
            role: 태스크를 수행할 에이전트 역할
            params: 태스크 파라미터
            exclude_self: 자기 자신(ReACT 에이전트)을 제외할지 여부
            
        Returns:
            태스크 실행 결과
        """
        task_id = str(uuid.uuid4())
        
        # 브로커에 전달할 태스크 데이터 구성
        task_data = {
            "task_id": task_id,
            "role": role,
            "params": params,
            "exclude_agent": self.agent_id if exclude_self else None
        }
        
        try:
            logger.info(f"브로커에 태스크 '{role}' 제출 (task_id: {task_id})")
            
            # 브로커에 태스크 제출
            async with self.http_client.post(
                f"{self.broker_url}/execute_task",
                json=task_data,
                timeout=60.0  # 타임아웃 설정 (필요에 따라 조정)
            ) as response:
                if response.status_code != 200:
                    error_message = await response.text()
                    logger.error(f"브로커 태스크 제출 실패: {error_message}")
                    return {
                        "success": False,
                        "error": f"브로커 오류 ({response.status_code}): {error_message}"
                    }
                
                result = await response.json()
                logger.info(f"브로커 태스크 '{role}' 실행 결과 수신 (task_id: {task_id})")
                return {
                    "success": True,
                    "task_id": task_id,
                    "result": result
                }
                
        except Exception as e:
            logger.error(f"브로커 태스크 제출 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": f"태스크 제출 오류: {str(e)}"
            }
    
    # 선택적 구현: 세션 관리 API 엔드포인트
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """세션 상태 조회 API"""
        if session_id not in self.active_sessions:
            raise HTTPException(status_code=404, detail=f"세션 '{session_id}'를 찾을 수 없습니다.")
        
        session = self.active_sessions[session_id]
        return {
            "session_id": session.session_id,
            "task_id": session.task_id,
            "status": session.status,
            "step_count": len(session.steps),
            "current_step": session.current_step,
            "created_at": session.created_at,
            "updated_at": session.updated_at
        } 