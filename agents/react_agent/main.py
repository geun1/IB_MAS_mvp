"""
ReACT (Reasoning + Acting) 에이전트
추론과 행동을 결합한 다단계 문제 해결 에이전트
"""
import os
import logging
import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple
from fastapi import FastAPI, Request, Body, HTTPException, Depends
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv("../../.env")

# 공통 모듈 임포트
try:
    from common.react_agent_base import ReACTAgentBase, ReACTSession, ReACTStepType, ReACTStep
    from common.fallback_manager import FallbackManager, FallbackStatus, FallbackResult
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    if project_root not in sys.path:
        sys.path.append(project_root)
    from common.react_agent_base import ReACTAgentBase, ReACTSession, ReACTStepType, ReACTStep
    from common.fallback_manager import FallbackManager, FallbackStatus, FallbackResult

# API 클라이언트 설정
import httpx

# 로깅 설정
logging.basicConfig(
    level=logging.getLevelName(os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("react_agent")

# LLM 클라이언트 (실제 구현은 필요에 따라 확장)
class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = httpx.AsyncClient(timeout=60.0)
        
    async def ask(self, prompt: str) -> str:
        """LLM에 질문하고 응답 받기"""
        logger.info("LLM 질의 시작")
        
        # 예시 응답 (실제 구현에서는 OpenAI 또는 Anthropic API 호출)
        # 실제 구현 시에는 아래 예시 코드 대신 실제 API 호출 코드로 변경해야 합니다.
        await asyncio.sleep(1)  # API 호출 시뮬레이션
        
        # LLM 응답 예시
        response = f"사고 과정:\n과제를 이해하고 분석했습니다. 정보를 요약하고 정리해야 합니다.\n\n다음 행동: web_search\n파라미터: {{'query': '최신 기술 트렌드'}}\n\n이유: 최신 정보를 수집하기 위해 검색이 필요합니다."
        
        logger.info("LLM 질의 완료")
        return response

# API 요청 모델
class ReACTAgentParams(BaseModel):
    query: str = Field(..., description="사용자 쿼리 또는 질문")
    context: Optional[str] = Field(None, description="추가 컨텍스트 정보")
    max_steps: Optional[int] = Field(10, description="최대 ReACT 단계 수")
    requires: Optional[List[str]] = Field(default_factory=list, description="필요한 도구 또는 에이전트")

# FastAPI 앱 초기화
app = FastAPI(title="ReACT Agent API")

# ReACT 에이전트 구현
class ReACTAgent(ReACTAgentBase):
    """
    ReACT (Reasoning + Acting) 에이전트 구현
    추론과 행동을 결합한 다단계 문제 해결 에이전트
    """
    
    def __init__(self, app: FastAPI):
        """ReACT 에이전트 초기화"""
        agent_id = "react_agent" 
        agent_role = "problem_solver"
        description = "여행과 관련된 추론과 행동을 결합한 다단계 문제 해결 에이전트"
        
        # 에이전트 파라미터 정의
        params = [
            {
                "name": "query",
                "type": "string",
                "description": "사용자 쿼리 또는 질문",
                "required": True
            },
            {
                "name": "context",
                "type": "string",
                "description": "추가 컨텍스트 정보",
                "required": False
            },
            {
                "name": "max_steps",
                "type": "integer",
                "description": "최대 ReACT 단계 수",
                "required": False,
                "default": 10
            },
            {
                "name": "requires",
                "type": "array",
                "description": "필요한 도구 또는 에이전트",
                "required": False,
                "default": []
            }
        ]
        
        # 레지스트리 URL과 컨테이너 정보
        registry_url = os.getenv("REGISTRY_URL", "http://registry:8000")
        container_name = os.getenv("CONTAINER_NAME", "react_agent")
        port = int(os.getenv("PORT", "8030"))
        
        # 브로커 URL 설정
        broker_url = os.getenv("BROKER_URL", "http://broker:8000")
        
        # 기본 클래스 초기화
        super().__init__(
            agent_id=agent_id,
            agent_role=agent_role,
            description=description,
            app=app,
            params=params,
            registry_url=registry_url,
            container_name=container_name,
            port=port,
            broker_url=broker_url,
            max_steps_per_session=10,
            fallback_max_retries=3
        )
        
        # LLM 클라이언트 초기화
        self.llm = LLMClient()
        
        # Fallback 매니저 초기화
        self.fallback_manager = FallbackManager()
        
        # API 엔드포인트 추가
        self.setup_additional_routes()
        
        logger.info(f"ReACT 에이전트 '{agent_role}' ({agent_id}) 초기화 완료")
    
    def setup_additional_routes(self):
        """추가 API 엔드포인트 설정"""
        # 세션 피드백 엔드포인트
        self.app.post("/react/feedback/{session_id}")(self.session_feedback)
    
    async def session_feedback(self, session_id: str, feedback: Dict[str, Any] = Body(...)):
        """
        ReACT 세션에 대한 피드백 처리
        이 피드백은 세션 개선과 학습에 사용될 수 있습니다.
        """
        if session_id not in self.active_sessions:
            raise HTTPException(status_code=404, detail=f"세션 '{session_id}'를 찾을 수 없습니다.")
        
        # 피드백 기록 (실제 구현에서는 저장 및 분석 로직 추가)
        logger.info(f"세션 '{session_id}'에 대한 피드백 수신: {feedback}")
        
        return {
            "status": "success",
            "message": f"세션 '{session_id}'에 대한 피드백이 접수되었습니다."
        }
    
    async def _execute_reasoning(
        self, 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        추론 단계 실행
        현재 상태를 바탕으로 다음에 취할 행동을 결정합니다.
        
        Args:
            session: 현재 세션
            context: 현재 컨텍스트
            
        Returns:
            추론 결과
        """
        start_time = time.time()
        
        # 현재 단계 설정
        step_id = f"{session.session_id}_reasoning_{len(session.steps)}"
        session.current_step = step_id
        
        try:
            # 추론을 위한 프롬프트 생성
            prompt = self._generate_reasoning_prompt(session, context)
            
            # LLM에 요청
            llm_response = await self.llm.ask(prompt)
            
            # 응답 파싱
            reasoning_result = self._parse_reasoning(llm_response)
            
            # 실행 시간 계산
            duration = time.time() - start_time
            
            # 추론 단계 기록
            reasoning_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.REASONING,
                content=reasoning_result,
                timestamp=start_time,
                duration=duration,
                metadata={
                    "prompt_tokens": len(prompt) // 4,
                    "response_tokens": len(llm_response) // 4
                }
            )
            session.steps.append(reasoning_step)
            
            # 로깅
            logger.info(f"추론 단계 완료: {step_id}, 행동: {reasoning_result.get('action', 'unknown')}")
            
            return reasoning_result
            
        except Exception as e:
            logger.error(f"추론 단계 오류: {str(e)}")
            
            # Fallback 처리
            fallback_result = await self._handle_fallback(
                session, 
                ReACTStepType.REASONING, 
                e, 
                context
            )
            
            # 오류 단계 기록
            error_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ERROR,
                content=str(e),
                timestamp=start_time,
                duration=time.time() - start_time,
                metadata={"fallback": fallback_result}
            )
            session.steps.append(error_step)
            
            # 기본 Fallback 결과 반환
            return fallback_result

    async def _execute_action(
        self, 
        session: ReACTSession, 
        reasoning_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        행동 단계 실행
        추론 결과를 바탕으로 실제 행동을 수행합니다.
        
        Args:
            session: 현재 세션
            reasoning_result: 추론 결과
            context: 현재 컨텍스트
            
        Returns:
            행동 결과
        """
        start_time = time.time()
        
        # 현재 단계 설정
        step_id = f"{session.session_id}_action_{len(session.steps)}"
        session.current_step = step_id
        
        try:
            # 추론 결과에서 행동 추출
            action = self._extract_action(reasoning_result)
            
            # 행동 수행
            action_result = await self._perform_action(action, session, context)
            
            # 실행 시간 계산
            duration = time.time() - start_time
            
            # 행동 단계 기록
            action_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ACTION,
                content=action_result,
                timestamp=start_time,
                duration=duration,
                metadata={
                    "action_type": action.get("type", "unknown"),
                    "action_target": action.get("target", "unknown")
                }
            )
            session.steps.append(action_step)
            
            # 로깅
            logger.info(f"행동 단계 완료: {step_id}, 유형: {action.get('type', 'unknown')}")
            
            return action_result
            
        except Exception as e:
            logger.error(f"행동 단계 오류: {str(e)}")
            
            # Fallback 처리
            fallback_result = await self._handle_fallback(
                session, 
                ReACTStepType.ACTION, 
                e, 
                context
            )
            
            # 오류 단계 기록
            error_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ERROR,
                content=str(e),
                timestamp=start_time,
                duration=time.time() - start_time,
                metadata={"fallback": fallback_result}
            )
            session.steps.append(error_step)
            
            # 기본 Fallback 결과 반환
            return fallback_result

    async def _execute_observation(
        self, 
        session: ReACTSession, 
        action_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        관찰 단계 실행
        행동의 결과를 분석하고 다음 단계를 위한 관찰을 수행합니다.
        
        Args:
            session: 현재 세션
            action_result: 행동 결과
            context: 현재 컨텍스트
            
        Returns:
            관찰 결과
        """
        start_time = time.time()
        
        # 현재 단계 설정
        step_id = f"{session.session_id}_observation_{len(session.steps)}"
        session.current_step = step_id
        
        try:
            # 행동 결과 분석
            observation_result = self._analyze_action_result(action_result, session, context)
            
            # 실행 시간 계산
            duration = time.time() - start_time
            
            # 관찰 단계 기록
            observation_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.OBSERVATION,
                content=observation_result,
                timestamp=start_time,
                duration=duration,
                metadata={
                    "observation_type": observation_result.get("type", "general"),
                    "content_length": len(json.dumps(observation_result))
                }
            )
            session.steps.append(observation_step)
            
            # 로깅
            logger.info(f"관찰 단계 완료: {step_id}")
            
            return observation_result
            
        except Exception as e:
            logger.error(f"관찰 단계 오류: {str(e)}")
            
            # Fallback 처리
            fallback_result = await self._handle_fallback(
                session, 
                ReACTStepType.OBSERVATION, 
                e, 
                context
            )
            
            # 오류 단계 기록
            error_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ERROR,
                content=str(e),
                timestamp=start_time,
                duration=time.time() - start_time,
                metadata={"fallback": fallback_result}
            )
            session.steps.append(error_step)
            
            # 기본 Fallback 결과 반환
            return fallback_result

    async def _generate_final_result(
        self, 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        최종 결과 생성
        전체 ReACT 루프의 결과를 종합하여 최종 결과를 생성합니다.
        
        Args:
            session: 현재 세션
            context: 현재 컨텍스트
            
        Returns:
            최종 결과
        """
        # 세션의 모든 단계 검토
        step_history = context.get("step_history", [])
        
        # 마지막 관찰 결과 검토
        final_observation = None
        if step_history:
            final_observation = step_history[-1].get("observation")
        
        # 결과 요약 생성
        # 실제 구현에서는 LLM을 사용하여 모든 단계를 요약할 수 있습니다.
        
        # 기본 결과 구성
        result = {
            "success": True,
            "steps_executed": len(session.steps),
            "final_result": final_observation or {"message": "태스크 완료"},
            "execution_time": session.updated_at - session.created_at
        }
        
        # 단계별 결과 요약 추가
        result["step_summary"] = []
        for step in session.steps:
            if step.step_type != ReACTStepType.ERROR:
                result["step_summary"].append({
                    "type": step.step_type,
                    "id": step.step_id,
                    "duration": step.duration
                })
        
        # 로깅
        logger.info(f"ReACT 세션 '{session.session_id}' 완료: {len(session.steps)} 단계 실행")
        
        return result

    async def _should_complete(
        self, 
        step_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> bool:
        """
        완료 여부 판단
        현재 단계 결과를 바탕으로 ReACT 루프를 종료할지 여부를 결정합니다.
        
        Args:
            step_result: 현재 단계 결과
            context: 현재 컨텍스트
            
        Returns:
            완료 여부
        """
        # 완료 플래그 확인
        if step_result.get("complete", False):
            return True
        
        # 특정 결과 상태 확인
        if step_result.get("status") == "complete":
            return True
        
        # 최종 결과 확인
        if step_result.get("final_result") is not None:
            return True
        
        return False
    
    def _generate_reasoning_prompt(self, session: ReACTSession, context: Dict[str, Any]) -> str:
        """추론을 위한 프롬프트 생성"""
        params = context.get("params", {})
        query = params.get("query", "")
        user_context = params.get("context", "")
        
        # 단계 기록
        step_history = context.get("step_history", [])
        history_text = ""
        
        for i, step in enumerate(step_history):
            reasoning = step.get("reasoning", {})
            action = step.get("action", {})
            observation = step.get("observation", {})
            
            history_text += f"\n단계 {i+1}:\n"
            history_text += f"사고 과정: {reasoning.get('thought', '')}\n"
            history_text += f"행동: {action.get('type', '')} - 파라미터: {json.dumps(action.get('params', {}), ensure_ascii=False)}\n"
            history_text += f"관찰: {json.dumps(observation, ensure_ascii=False)}\n"
        
        # 프롬프트 구성
        prompt = (
            f"# 요청\n{query}\n\n"
            f"# 컨텍스트\n{user_context or '없음'}\n\n"
            f"# 단계 기록\n{history_text or '이전 단계 없음'}\n\n"
            "# 지시사항\n"
            "1. 상황을 이해하고 다음에 수행할 최선의 행동을 결정하세요.\n"
            "2. 결과를 다음 형식으로 제공하세요:\n"
            "   - 사고 과정: (문제를 이해하고 분석하는 방법)\n"
            "   - 다음 행동: (행동 유형)\n"
            "   - 파라미터: (행동에 필요한 파라미터)\n"
            "   - 이유: (이 행동을 선택한 이유)\n"
            "3. 행동이 더 이상 필요 없으면 '다음 행동: complete'라고 표시하세요.\n\n"
            "이제 상황을 분석하고 다음 행동을 결정하세요."
        )
        
        return prompt
    
    def _parse_reasoning(self, llm_response: str) -> Dict[str, Any]:
        """LLM 응답에서 추론 결과 파싱"""
        # 간단한 파싱 예시 (실제 구현에서는 더 견고한 파싱 로직 필요)
        lines = llm_response.strip().split('\n')
        
        result = {
            "thought": "",
            "action": None,
            "params": {},
            "reason": ""
        }
        
        # 각 라인 분석
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("사고 과정:"):
                current_section = "thought"
                result["thought"] = line[len("사고 과정:"):].strip()
            elif line.startswith("다음 행동:"):
                current_section = "action"
                result["action"] = line[len("다음 행동:"):].strip()
            elif line.startswith("파라미터:"):
                current_section = "params"
                params_str = line[len("파라미터:"):].strip()
                try:
                    # JSON 형식 파싱
                    if params_str.startswith("{") and params_str.endswith("}"):
                        result["params"] = json.loads(params_str)
                except:
                    result["params"] = {"raw": params_str}
            elif line.startswith("이유:"):
                current_section = "reason"
                result["reason"] = line[len("이유:"):].strip()
            elif current_section:
                # 현재 섹션에 내용 추가
                result[current_section] += " " + line
        
        return result
    
    def _extract_action(self, reasoning_result: Dict[str, Any]) -> Dict[str, Any]:
        """추론 결과에서 수행할 행동 추출"""
        action_type = reasoning_result.get("action", "")
        params = reasoning_result.get("params", {})
        
        # 행동 유형 확인
        if action_type.lower() == "complete":
            return {
                "type": "complete",
                "params": {},
                "complete": True
            }
        
        # 에이전트 호출 (예: web_search, writer 등)
        if action_type:
            return {
                "type": action_type,
                "params": params,
                "target": "agent",
                "reason": reasoning_result.get("reason", "")
            }
        
        # 기본 행동
        return {
            "type": "unknown",
            "params": params,
            "reason": "명확한 행동이 지정되지 않았습니다."
        }
    
    async def _perform_action(
        self, 
        action: Dict[str, Any], 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """행동 수행"""
        action_type = action.get("type", "")
        
        # 완료 액션 처리
        if action_type == "complete":
            return {
                "status": "complete",
                "message": "태스크가 완료되었습니다.",
                "complete": True
            }
        
        # 다른 에이전트 호출
        if action.get("target") == "agent":
            role = action_type
            params = action.get("params", {})
            
            # 브로커를 통해 에이전트 호출
            agent_result = await self._call_agent_through_broker(role, params)
            return {
                "status": "success",
                "agent": role,
                "result": agent_result
            }
        
        # 알 수 없는 행동 처리
        return {
            "status": "error",
            "message": f"지원되지 않는 행동 유형: {action_type}"
        }
    
    async def _call_agent_through_broker(
        self, 
        role: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """브로커를 통해 다른 에이전트 호출"""
        try:
            # 브로커에 태스크 제출
            result = await self.submit_task_to_broker(
                role=role,
                params=params
            )
            
            if not result.get("success"):
                logger.error(f"브로커 태스크 실행 실패: {result.get('error')}")
                return {
                    "success": False,
                    "error": result.get("error", "알 수 없는 오류")
                }
            
            return result.get("result", {})
            
        except Exception as e:
            logger.error(f"에이전트 호출 오류: {str(e)}")
            return {
                "success": False,
                "error": f"에이전트 호출 오류: {str(e)}"
            }
    
    def _analyze_action_result(
        self, 
        action_result: Dict[str, Any], 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """행동 결과 분석"""
        # 완료 상태 확인
        if action_result.get("complete", False) or action_result.get("status") == "complete":
            return {
                "type": "final",
                "message": "태스크가 완료되었습니다.",
                "complete": True
            }
        
        # 에이전트 결과 분석
        if "agent" in action_result:
            agent = action_result.get("agent")
            result = action_result.get("result", {})
            
            return {
                "type": "agent_result",
                "agent": agent,
                "content": result,
                "summary": f"{agent} 에이전트의 결과가 성공적으로 수신되었습니다."
            }
        
        # 오류 분석
        if action_result.get("status") == "error":
            return {
                "type": "error",
                "message": action_result.get("message", "알 수 없는 오류"),
                "need_retry": True
            }
        
        # 기본 분석
        return {
            "type": "general",
            "content": action_result,
            "summary": "행동이 실행되었으나 구체적인 결과 유형이 감지되지 않았습니다."
        }

# 루트 엔드포인트
@app.get("/")
async def root():
    return {
        "name": "ReACT Agent",
        "description": "추론과 행동을 결합한 다단계 문제 해결 에이전트",
        "status": "active"
    }

# 에이전트 인스턴스 생성
react_agent = ReACTAgent(app) 