"""
여행 계획(Travel Planner) ReAct 에이전트
추론과 행동을 결합하여 여행 계획을 세우는 다단계 문제 해결 에이전트
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
import httpx
import litellm

load_dotenv("../../.env")

# 공통 모듈 임포트
try:
    from common.react_agent_base import ReACTAgentBase, ReACTSession, ReACTStepType, ReACTStep
    from common.fallback_manager import FallbackManager, FallbackStatus, FallbackResult
    from common.agent_types import AgentType
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    if project_root not in sys.path:
        sys.path.append(project_root)
    from common.react_agent_base import ReACTAgentBase, ReACTSession, ReACTStepType, ReACTStep
    from common.fallback_manager import FallbackManager, FallbackStatus, FallbackResult
    from common.agent_types import AgentType

# LLM 클라이언트 임포트
from common.llm_client import LLMClient

# 로깅 설정
logging.basicConfig(
    level=logging.getLevelName(os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("travel_planner_agent")

# 로깅 레벨 설정
log_level = os.getenv("LOG_LEVEL", "INFO")
logger.setLevel(logging.getLevelName(log_level))
logger.info(f"로깅 레벨 설정: {log_level}")

# API 요청 모델
class TravelPlannerParams(BaseModel):
    query: str = Field(..., description="여행 계획에 대한 요구사항")
    context: Optional[str] = Field(None, description="추가 컨텍스트 정보")
    max_steps: Optional[int] = Field(10, description="최대 ReACT 단계 수")

# FastAPI 앱 초기화
app = FastAPI(title="Travel Planner ReACT Agent API")

# LiteLLM 임포트 및 API 키 설정
litellm.api_key = os.getenv("OPENAI_API_KEY", "")

# 환경 변수
DEFAULT_MAX_STEPS = int(os.getenv("MAX_STEPS", "10"))
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "당신은 여행 계획을 세우는 전문가입니다. 사용자가 요청한 여행 계획을 최대한 구체적으로 작성해주세요.")

# 여행 계획 ReACT 에이전트 구현
class TravelPlannerAgent(ReACTAgentBase):
    """
    여행 계획 ReACT (Reasoning + Acting) 에이전트 구현
    추론과 행동을 결합한 다단계 여행 계획 에이전트
    """
    
    def __init__(self, app: FastAPI):
        """
        에이전트 초기화
        
        Args:
            app: FastAPI 앱
        """
        # 에이전트 ID와 역할 설정
        agent_id = os.getenv("AGENT_ID", f"travel_planner_agent_{uuid.uuid4().hex[:8]}")
        agent_role = "travel_planner"
        description = "사용자 요구사항에 맞는 여행 계획을 세우고 추천하는 ReACT 에이전트"
        
        # 에이전트 파라미터 정의
        params = [
            {
                "name": "query",
                "type": "string",
                "description": "여행 계획에 대한 요구사항",
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
                "default": DEFAULT_MAX_STEPS
            }
        ]
        
        # 환경 설정
        registry_url = os.getenv("REGISTRY_URL", "http://registry:8000")
        container_name = os.getenv("CONTAINER_NAME", "travel_planner_agent")
        port = int(os.getenv("PORT", "8050"))
        broker_url = os.getenv("BROKER_URL", "http://broker:8000")
        
        # 상위 클래스 초기화
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
            max_steps_per_session=DEFAULT_MAX_STEPS,
            fallback_max_retries=3
        )
        
        # 활성화된 세션 저장소
        self.active_sessions = {}
        
        # 추가 경로 설정
        self.setup_additional_routes()
        
        logger.info(f"여행 계획 ReAct 에이전트 초기화 완료 - ID: {agent_id}")
        logger.info(f"브로커 URL: {broker_url}")
        logger.info(f"기본 최대 단계 수: {DEFAULT_MAX_STEPS}")
        logger.info(f"LLM 모델: {LLM_MODEL}")
    
    def setup_additional_routes(self):
        """추가 API 엔드포인트 설정"""
        # 세션 세부 정보 조회 엔드포인트
        self.app.get("/travel/session/{session_id}")(self.get_session_details)
    
    async def get_session_details(self, session_id: str):
        """특정 세션의 세부 정보 조회"""
        if session_id not in self.active_sessions:
            raise HTTPException(status_code=404, detail=f"세션 '{session_id}'를 찾을 수 없습니다.")
        
        session = self.active_sessions[session_id]
        return {
            "session_id": session.session_id,
            "task_id": session.task_id,
            "status": session.status,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "steps_count": len(session.steps),
            "current_step": session.current_step
        }
    
    async def _execute_reasoning(
        self, 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        추론 단계 실행
        지금까지의 정보를 기반으로 다음 단계를 결정합니다.
        
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
            logger.info(f"추론 단계 시작: {step_id}")
            
            # 처음 추론인지 확인 (세션의 단계 수로 확인)
            is_first_reasoning = len([s for s in session.steps if s.step_type == ReACTStepType.REASONING]) == 0
            logger.info(f"첫 번째 추론 단계: {is_first_reasoning}")
            
            # 추론용 프롬프트 생성
            prompt = self._generate_reasoning_prompt(session, context)
            logger.info(f"추론 프롬프트 생성 완료: 길이={len(prompt)}")
            
            # 프롬프트를 사용하여 LLM 추론
            logger.info(f"LLM에 추론 요청")
            
            # 시스템 프롬프트 및 사용자 프롬프트 설정
            if is_first_reasoning:
                # 첫 번째 추론은 단순히 여행 요구사항을 분석하고 여행 정보를 찾기 위한 계획 수립
                system_prompt = """
                당신은 여행 계획 작성을 돕는 ReACT(Reasoning-Action-Observation) 에이전트입니다.
                여행 요구사항을 분석하고, 필요한 정보를 얻기 위한 단계적인 접근 방식을 취하세요.
                
                반드시 아래 형식을 따라 응답하세요:
                
                사고 과정: [요구사항 분석 및 필요한 정보 식별]
                다음 행동: [web_search/writer/data_analyzer 중 하나 선택]
                파라미터: {
                    "query": "검색어 또는 파라미터",
                    "추가 파라미터": "값"
                }
                이유: [이 행동을 선택한 이유]
                
                지원되는 행동:
                - web_search: 여행지 정보, 명소, 음식점, 숙소 등 정보 검색
                    파라미터: {"query": "검색어"}
                - writer: 여행 일정 작성
                    파라미터: {"content": "작성할 내용", "format": "format type"}
                - data_analyzer: 수집된 정보 분석
                    파라미터: {"data": "분석할 데이터", "task": "분석 작업"}
                
                절대로 처음부터 최종 여행 계획을 작성하지 마세요. 
                반드시 web_search로 여행지 정보를 수집한 후에 계획을 작성해야 합니다.
                """
            else:
                # 이후 추론은 정보 수집 및 계획 수립 과정 계속
                system_prompt = """
                당신은 여행 계획 작성을 돕는 ReACT(Reasoning-Action-Observation) 에이전트입니다.
                기존에 수집한 정보를 바탕으로 다음 단계를 결정하세요.
                
                반드시 아래 형식을 따라 응답하세요:
                
                사고 과정: [지금까지 수집한 정보 분석 및 필요한 추가 정보 식별]
                다음 행동: [web_search/writer/data_analyzer/COMPLETE 중 하나 선택]
                파라미터: {
                    "query": "검색어 또는 파라미터",
                    "추가 파라미터": "값"
                }
                이유: [이 행동을 선택한 이유]
                
                지원되는 행동:
                - web_search: 여행지 정보, 명소, 음식점, 숙소 등 정보 검색
                    파라미터: {"query": "검색어"}
                - writer: 여행 일정 작성
                    파라미터: {"content": "작성할 내용", "format": "format type"}
                - data_analyzer: 수집된 정보 분석
                    파라미터: {"data": "분석할 데이터", "task": "분석 작업"}
                - COMPLETE: 태스크 완료 선언 (충분한 정보가 수집되었을 때만 사용)
                
                충분한 정보가 수집되었다면 "writer" 행동을 선택하여 여행 계획을 작성하거나,
                모든 작업이 완료되었다면 "COMPLETE"를 반환하세요.
                """
            
            # LLM 호출하여 추론 결과 얻기
            llm_response = await self._call_llm_for_reasoning(system_prompt, prompt)
            logger.info(f"LLM 응답 수신: 길이={len(llm_response)}")
            
            # 추론 결과 파싱
            reasoning_result = self._parse_reasoning(llm_response)
            
            # 추론 결과 로깅
            next_action = reasoning_result.get("next_action", "")
            logger.info(f"추론 결과: 다음 행동={next_action}, 이유={reasoning_result.get('reason', '')[:100]}")
            
            duration = time.time() - start_time
            
            # 단계 정보 저장
            step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.REASONING,
                content=reasoning_result,
                timestamp=start_time,
                duration=duration
            )
            session.steps.append(step)
            
            logger.info(f"추론 단계 완료: {step_id}, 소요 시간: {duration:.2f}초")
            return reasoning_result
            
        except Exception as e:
            logger.error(f"추론 단계 오류: {str(e)}")
            raise
            
    async def _call_llm_for_reasoning(self, system_prompt: str, user_prompt: str) -> str:
        """
        추론을 위한 LLM 호출
        
        Args:
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            
        Returns:
            LLM 응답 텍스트
        """
        try:
            logger.info("LLM 모델 호출 시작")
            
            # OpenAI API 키 확인
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                logger.error("OpenAI API 키가 설정되지 않았습니다.")
                return "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다."
            
            # LiteLLM 클라이언트 설정
            os.environ["OPENAI_API_KEY"] = openai_api_key
            
            # 모델 호출
            response = await litellm.acompletion(
                model="gpt-4o",  # 더 강력한 모델 사용
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            
            # 응답 추출
            content = response.choices[0].message.content
            logger.info(f"LLM 모델 호출 완료: 응답 길이={len(content)}")
            
            return content
            
        except Exception as e:
            logger.error(f"LLM 호출 오류: {str(e)}")
            return f"LLM 호출 중 오류 발생: {str(e)}"

    def _generate_reasoning_prompt(self, session: ReACTSession, context: Dict[str, Any]) -> str:
        """
        현재 상태를 바탕으로 추론을 위한 프롬프트 생성
        
        Args:
            session: 현재 세션
            context: 현재 컨텍스트
            
        Returns:
            추론용 프롬프트
        """
        # 초기 쿼리/요구사항
        query = context.get("params", {}).get("query", "")
        
        # 이전 단계 정보 수집
        history = []
        previous_observations = []
        
        for step in session.steps:
            if step.step_type == ReACTStepType.REASONING:
                reasoning = step.content
                thought = reasoning.get("thought", "")
                next_action = reasoning.get("next_action", "")
                params = reasoning.get("params", {})
                reason = reasoning.get("reason", "")
                
                history.append(f"이전 사고 과정: {thought}")
                history.append(f"이전 행동: {next_action}")
                history.append(f"파라미터: {json.dumps(params, ensure_ascii=False)}")
                history.append(f"이유: {reason}")
                
            elif step.step_type == ReACTStepType.ACTION:
                action = step.content
                action_type = action.get("action_type", "")
                action_params = action.get("params", {})
                
                history.append(f"수행된 행동: {action_type}")
                history.append(f"파라미터: {json.dumps(action_params, ensure_ascii=False)}")
                
            elif step.step_type == ReACTStepType.OBSERVATION:
                observation = step.content
                result = observation.get("result", "")
                previous_observations.append(result)
                
                # 간결성을 위해 관찰 결과 요약
                if len(str(result)) > 500:
                    summarized = str(result)[:250] + "..." + str(result)[-250:]
                    history.append(f"관찰 결과: {summarized}")
                else:
                    history.append(f"관찰 결과: {result}")
        
        # 프롬프트 구성
        prompt = f"""여행 요구사항: {query}

이전 단계 기록:
{chr(10).join(history)}

관찰 결과 요약:
{chr(10).join(str(obs) for obs in previous_observations[-3:]) if previous_observations else "아직 관찰 결과가 없습니다."}

지금까지의 정보를 바탕으로 다음 단계를 추론하세요. 더 많은 정보가 필요하면 적절한 행동을 취하고, 충분한 정보가 있다면 여행 계획을 완성하세요.
"""
        return prompt

    def _parse_reasoning(self, llm_response: str) -> Dict[str, Any]:
        """
        LLM 응답에서 추론 결과 파싱
        
        Args:
            llm_response: LLM 응답 텍스트
            
        Returns:
            파싱된 추론 결과
        """
        result = {
            "thought": "",
            "next_action": "",
            "params": {},
            "reason": ""
        }
        
        try:
            # 사고 과정 추출
            if "사고 과정:" in llm_response:
                thought_parts = llm_response.split("사고 과정:", 1)[1].split("다음 행동:", 1)
                result["thought"] = thought_parts[0].strip()
            elif "Thought:" in llm_response:
                thought_parts = llm_response.split("Thought:", 1)[1].split("Action:", 1)
                result["thought"] = thought_parts[0].strip()
            
            # 다음 행동 추출
            if "다음 행동:" in llm_response:
                action_parts = llm_response.split("다음 행동:", 1)[1].split("파라미터:", 1)
                result["next_action"] = action_parts[0].strip()
            elif "Action:" in llm_response:
                action_parts = llm_response.split("Action:", 1)[1].split("Parameters:", 1)
                result["next_action"] = action_parts[0].strip()
            
            # 파라미터 추출
            if "파라미터:" in llm_response:
                params_parts = llm_response.split("파라미터:", 1)[1].split("이유:", 1)
                params_str = params_parts[0].strip()
            elif "Parameters:" in llm_response:
                params_parts = llm_response.split("Parameters:", 1)[1].split("Reason:", 1)
                params_str = params_parts[0].strip()
            else:
                params_str = ""
            
            # JSON 형식으로 파싱
            try:
                # 중괄호 바깥의 내용 제거
                if "{" in params_str and "}" in params_str:
                    json_str = params_str[params_str.find("{"):params_str.rfind("}")+1]
                    result["params"] = json.loads(json_str)
                else:
                    # 중괄호가 없는 경우 파라미터 없음으로 처리
                    logger.warning("파라미터 JSON 형식이 아님, 빈 객체로 처리")
                    result["params"] = {}
            except json.JSONDecodeError:
                logger.warning(f"파라미터 JSON 파싱 실패: {params_str}")
                result["params"] = {}
            
            # 이유 추출
            if "이유:" in llm_response:
                result["reason"] = llm_response.split("이유:", 1)[1].strip()
            elif "Reason:" in llm_response:
                result["reason"] = llm_response.split("Reason:", 1)[1].strip()
            
            # COMPLETE 신호 확인
            if "COMPLETE" in llm_response or "완료" in llm_response:
                result["next_action"] = "COMPLETE"
            
            # 결과 유효성 확인 및 기본값 설정
            if not result["next_action"]:
                logger.warning("다음 행동이 감지되지 않음, 기본값으로 'web_search' 설정")
                result["next_action"] = "web_search"
                result["params"] = {"query": "여행 계획 추천"}
            
            return result
            
        except Exception as e:
            logger.error(f"추론 결과 파싱 오류: {str(e)}")
            return {
                "thought": "파싱 오류 발생",
                "next_action": "web_search",
                "params": {"query": "여행 계획 추천"},
                "reason": f"파싱 오류: {str(e)}"
            }

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
            행동 실행 결과
        """
        start_time = time.time()
        
        # 현재 단계 설정
        step_id = f"{session.session_id}_action_{len(session.steps)}"
        session.current_step = step_id
        
        try:
            logger.info(f"행동 단계 시작: {step_id}")
            
            # 행동 추출
            action_type = reasoning_result.get("next_action", "").strip().lower()
            params = reasoning_result.get("params", {})
            
            logger.info(f"선택된 행동: {action_type}, 파라미터: {params}")
            
            # 행동 정보 생성
            action = {
                "action_type": action_type,
                "params": params
            }
            
            # 행동이 COMPLETE인 경우 바로 완료 처리
            if action_type == "complete":
                logger.info("작업 완료 신호 감지")
                result = {"status": "success", "message": "태스크 완료 신호 수신"}
            else:
                # 브로커를 통해 행동 수행
                logger.info(f"브로커를 통해 행동 수행: {action_type}")
                result = await self._perform_action(action, session, context)
                logger.info(f"행동 수행 결과: 상태={result.get('status', 'unknown')}")
            
            duration = time.time() - start_time
            
            # 단계 정보 저장
            step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ACTION,
                content=action,
                timestamp=start_time,
                duration=duration,
                metadata={"result": result}
            )
            session.steps.append(step)
            
            logger.info(f"행동 단계 완료: {step_id}, 행동: {action_type}, 소요 시간: {duration:.2f}초")
            return action
            
        except Exception as e:
            logger.error(f"행동 단계 오류: {str(e)}")
            raise

    async def _perform_action(
        self, 
        action: Dict[str, Any], 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        실제 행동 수행 (브로커를 통한 에이전트 호출)
        
        Args:
            action: 수행할 행동 정보
            session: 현재 세션
            context: 현재 컨텍스트
            
        Returns:
            행동 수행 결과
        """
        action_type = action.get("action_type", "").lower()
        params = action.get("params", {})
        
        # 행동 유형에 따라 분기
        if action_type == "web_search":
            # 웹 검색 에이전트 호출
            return await self._call_agent_through_broker("web_search", params)
            
        elif action_type == "writer":
            # 작성 에이전트 호출
            return await self._call_agent_through_broker("writer", params)
            
        elif action_type == "data_analyzer":
            # 데이터 분석 에이전트 호출
            return await self._call_agent_through_broker("data_analyzer", params)
            
        else:
            # 지원하지 않는 행동
            return {
                "status": "error",
                "message": f"지원하지 않는 행동 타입: {action_type}"
            }

    async def _call_agent_through_broker(
        self, 
        role: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        브로커를 통해 다른 에이전트 호출
        
        Args:
            role: 호출할 에이전트 역할
            params: 에이전트 파라미터
            
        Returns:
            에이전트 실행 결과
        """
        try:
            # 브로커 URL 확인
            broker_url = os.getenv("BROKER_URL", "http://broker:8000")
            logger.info(f"브로커 연결 URL: {broker_url}")
            
            # 브로커에 태스크 제출
            logger.info(f"브로커에 태스크 제출 - 역할: {role}, 파라미터: {params}")
            
            # 임시 태스크 ID 생성
            task_id = f"temp_task_{role}_{uuid.uuid4().hex[:8]}"
            
            # httpx 클라이언트를 매번 새로 생성
            client = httpx.AsyncClient(timeout=60.0)
            
            try:
                # 브로커의 /execute_task 엔드포인트 직접 호출
                response = await client.post(
                    f"{broker_url}/execute_task",
                    json={
                        "task_id": task_id,
                        "role": role,
                        "params": params,
                        "exclude_agent": self.agent_id  # 자기 자신은 제외
                    }
                )
                
                try:
                    # 클라이언트 명시적 종료
                    await client.aclose()
                except Exception as close_err:
                    logger.error(f"클라이언트 종료 중 오류: {str(close_err)}")
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"브로커 API 호출 실패 - 상태 코드: {response.status_code}, 오류: {error_text}")
                    return {
                        "status": "error",
                        "message": f"브로커 API 오류: {error_text}",
                        "result": {
                            "error": f"브로커 API 호출 실패 (상태 코드: {response.status_code})",
                            "details": error_text
                        }
                    }
                
                # 응답 처리
                result = response.json()
                logger.info(f"브로커로부터 응답 수신 - 성공: {result.get('success', False)}")
                
                if result.get("success", False):
                    logger.info(f"브로커 태스크 성공 - 에이전트: {result.get('agent_id')}, 실행 시간: {result.get('execution_time', 0):.2f}초")
                    logger.info(f"결과 내용: {str(result.get('result', {}))[:200]}...")
                    return {
                        "status": "success",
                        "result": result.get("result", {})
                    }
                else:
                    logger.error(f"브로커 태스크 실패 - 오류: {result.get('error', '알 수 없는 오류')}")
                    return {
                        "status": "error",
                        "message": result.get("error", "알 수 없는 오류"),
                        "result": {
                            "error": result.get("error", "알 수 없는 오류"),
                            "agent_role": role
                        }
                    }
                    
            except httpx.RequestError as e:
                # 클라이언트 오류 처리
                try:
                    await client.aclose()
                except:
                    pass
                    
                logger.error(f"브로커 API 요청 오류: {str(e)}")
                return {
                    "status": "error",
                    "message": f"브로커 API 요청 오류: {str(e)}",
                    "result": {
                        "error": f"브로커 통신 오류: {str(e)}",
                        "agent_role": role,
                        "params": params
                    }
                }
        
        except Exception as e:
            logger.error(f"브로커를 통한 에이전트 호출 오류: {str(e)}")
            return {
                "status": "error",
                "message": f"에이전트 호출 오류: {str(e)}",
                "error_type": type(e).__name__,
                "result": {
                    "error": f"에이전트 '{role}' 호출 중 오류 발생: {str(e)}",
                    "action_type": role,
                    "params": params
                }
            }

    async def _execute_observation(
        self, 
        session: ReACTSession, 
        action_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        관찰 단계 실행
        행동 결과를 관찰하고 분석합니다.
        
        Args:
            session: 현재 세션
            action_result: 행동 실행 결과
            context: 현재 컨텍스트
            
        Returns:
            관찰 결과
        """
        start_time = time.time()
        
        # 현재 단계 설정
        step_id = f"{session.session_id}_observation_{len(session.steps)}"
        session.current_step = step_id
        
        try:
            logger.info(f"관찰 단계 시작: {step_id}")
            
            # 행동 결과 분석
            observation = self._analyze_action_result(action_result, session, context)
            
            logger.info(f"관찰 결과: 상태={observation.get('status', 'unknown')}")
            if 'result' in observation and isinstance(observation['result'], dict):
                logger.info(f"관찰 내용: {list(observation['result'].keys()) if observation['result'] else 'Empty'}")
            
            duration = time.time() - start_time
            
            # 단계 정보 저장
            step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.OBSERVATION,
                content=observation,
                timestamp=start_time,
                duration=duration
            )
            session.steps.append(step)
            
            logger.info(f"관찰 단계 완료: {step_id}, 소요 시간: {duration:.2f}초")
            return observation
            
        except Exception as e:
            logger.error(f"관찰 단계 오류: {str(e)}")
            raise

    def _analyze_action_result(
        self, 
        action_result: Dict[str, Any], 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        행동 결과 분석
        
        Args:
            action_result: 행동 실행 결과
            session: 현재 세션
            context: 현재 컨텍스트
            
        Returns:
            분석 결과
        """
        # 행동 정보 추출
        action_type = action_result.get("action_type", "").lower()
        
        # 마지막 행동 단계 찾기
        last_action_step = None
        for step in reversed(session.steps):
            if step.step_type == ReACTStepType.ACTION:
                last_action_step = step
                break
                
        # 행동 유형 및 메타데이터 추출
        if last_action_step:
            metadata = last_action_step.metadata or {}
            result = metadata.get("result", {})
            
            # 응답 내용이 비어있는지 확인
            if not result or (isinstance(result, dict) and not result.get("result")):
                logger.warning(f"브로커를 통한 에이전트 호출 결과가 비어 있습니다. Action: {action_type}")
                # 임의의 결과 생성 (디버깅용)
                result = {
                    "status": "success",
                    "result": {
                        "message": f"에이전트 {action_type} 호출했으나 결과가 비어있습니다. 다른 행동을 시도하세요."
                    }
                }
        else:
            logger.warning("행동 단계를 찾을 수 없습니다.")
            result = {}
            
        # 에이전트 결과 추출 시도
        agent_result = result.get("result", {})
        
        # 중첩된 결과 구조 처리
        if isinstance(agent_result, dict):
            if "result" in agent_result:
                content = agent_result.get("result", {})
            else:
                content = agent_result
        else:
            content = agent_result
            
        # 응답 포맷팅 및 로깅
        observation = {
            "status": result.get("status", "unknown"),
            "result": content
        }
        
        logger.info(f"관찰 결과 생성: action_type={action_type}, status={observation['status']}")
        logger.info(f"관찰 내용: {str(observation['result'])[:200]}...")
        
        return observation

    async def _generate_final_result(
        self, 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        최종 결과 생성
        모든 단계가 완료된 후 최종 결과를 생성합니다.
        
        Args:
            session: 현재 세션
            context: 현재 컨텍스트
            
        Returns:
            최종 결과
        """
        import time
        
        try:
            if not session.steps:
                logger.warning(f"세션 '{session.session_id}'에 단계가 없습니다.")
                return {
                    "travel_plan": "여행 계획을 생성할 수 없습니다.",
                    "steps_count": 0,
                    "query": context["params"].get("query", ""),
                    "session_id": session.session_id
                }
                
            # 마지막 추론 단계
            last_reasoning = None
            for step in reversed(session.steps):
                if step.step_type == ReACTStepType.REASONING:
                    last_reasoning = step
                    break
                
            # 마지막 행동 단계
            last_action = None
            for step in reversed(session.steps):
                if step.step_type == ReACTStepType.ACTION:
                    last_action = step
                    break
                
            logger.info(f"마지막 추론 단계: {last_reasoning.step_id if last_reasoning else 'None'}")
            logger.info(f"마지막 행동 단계: {last_action.step_id if last_action else 'None'}")
            
            # 마지막 추론 또는 행동에서 여행 계획 추출
            travel_plan = ""
            
            if last_action and last_action.content.get("action") == "COMPLETE":
                # 완료 행동이 있을 경우 해당 메시지 사용
                travel_plan = last_action.content.get("message", "")
            elif last_reasoning and "사고 과정" in last_reasoning.content:
                # 마지막 추론에서 추출
                travel_plan = last_reasoning.content.get("사고 과정", "")
            else:
                # 대안으로 모든 단계의 통합 결과 생성
                travel_plan = "오사카 여행 계획:\n\n"
                
                for step in session.steps:
                    if step.step_type == ReACTStepType.REASONING and "사고 과정" in step.content:
                        reasonings = step.content.get("사고 과정", "")
                        if "여행 일정" in reasonings or "여행 계획" in reasonings:
                            travel_plan = reasonings
                            break
            
            # 단계별 상세 정보 수집
            step_details = []
            for step in session.steps:
                step_detail = {
                    "type": step.step_type,
                    "timestamp": step.timestamp
                }
                
                # 단계 유형에 따라 내용 가공
                if step.step_type == ReACTStepType.REASONING:
                    # 추론 단계
                    if isinstance(step.content, dict) and "사고 과정" in step.content:
                        step_detail["content"] = step.content["사고 과정"]
                    else:
                        step_detail["content"] = str(step.content)
                        
                elif step.step_type == ReACTStepType.ACTION:
                    # 행동 단계
                    if isinstance(step.content, dict):
                        if "action" in step.content and "params" in step.content:
                            step_detail["content"] = f"행동: {step.content['action']}\n파라미터: {json.dumps(step.content['params'], indent=2, ensure_ascii=False)}"
                        elif "action" in step.content:
                            step_detail["content"] = f"행동: {step.content['action']}"
                        else:
                            step_detail["content"] = str(step.content)
                    else:
                        step_detail["content"] = str(step.content)
                        
                elif step.step_type == ReACTStepType.OBSERVATION:
                    # 관찰 단계 
                    if isinstance(step.content, dict) and "result" in step.content:
                        step_detail["content"] = json.dumps(step.content["result"], indent=2, ensure_ascii=False)
                    else:
                        step_detail["content"] = str(step.content)
                
                step_details.append(step_detail)
            
            # 최종 결과 구성
            result = {
                "query": context["params"].get("query", ""),
                "travel_plan": travel_plan,
                "steps_count": len(session.steps),
                "session_id": session.session_id,
                "step_details": step_details
            }
            
            logger.info(f"최종 여행 계획 생성 완료: {len(travel_plan)} 글자")
            logger.info(f"총 {len(session.steps)}개 단계 기록 ({len(step_details)}개 단계 세부정보)")
            
            return result
            
        except Exception as e:
            logger.error(f"최종 결과 생성 중 오류 발생: {str(e)}")
            return {
                "travel_plan": "여행 계획 생성 중 오류가 발생했습니다: " + str(e),
                "steps_count": len(session.steps),
                "query": context["params"].get("query", ""),
                "session_id": session.session_id
            }

    async def _should_complete(
        self, 
        step_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> bool:
        """
        ReACT 루프 종료 여부 결정
        
        Args:
            step_result: 현재 단계 결과
            context: 현재 컨텍스트
            
        Returns:
            True면 루프 종료, False면 계속 진행
        """
        # 최대 단계 수 확인
        session_id = context.get("session_id")
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            max_steps = session.max_steps
            current_steps = len(session.steps)
            
            # 현재 단계 수와 최대 단계 수 로깅
            logger.info(f"ReACT 루프 진행 상황: {current_steps}/{max_steps} 단계")
            
            # 최대 단계 수 초과 여부 검사
            if current_steps >= max_steps:
                logger.warning(f"최대 단계 수 ({max_steps}) 도달. 루프 종료.")
                return True
        
        # 마지막 추론 단계에서 COMPLETE 신호 확인
        if "reasoning" in context:
            reasoning = context.get("reasoning", {})
            next_action = reasoning.get("next_action", "").lower()
            
            if next_action == "complete":
                logger.info("COMPLETE 신호 감지. 루프 종료.")
                return True
            
            # 충분한 정보가 수집되었는지 확인
            if len([s for s in session.steps if s.step_type == ReACTStepType.OBSERVATION]) >= 3:
                # 최소 3번의 관찰 단계를 거쳤다면 여행 계획 완성 가능
                if next_action == "writer":
                    logger.info("충분한 정보 수집 후 writer 행동 감지. 마지막 단계로 판단.")
                    return False  # 마지막 writer 행동은 수행한 후 종료
        
        # 기본적으로 계속 진행
        return False

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
        
        # 사용자 파라미터에서 max_steps 추출 (값이 없으면 환경 변수 값 사용)
        max_steps = params.get("max_steps", int(os.getenv("MAX_STEPS", "10")))
        logger.info(f"태스크 처리 시작: {task_id}, max_steps={max_steps}")
        
        # 세션 생성
        session_id = f"react_{task_id}_{int(time.time())}"
        session = self._create_session(session_id, task_id)
        
        # 세션 최대 단계 수 설정
        session.max_steps = max_steps
        logger.info(f"ReACT 세션 생성: {session_id}, 최대 단계 수: {max_steps}")
        
        # 세션 활성화
        self.active_sessions[session_id] = session
        
        try:
            # ReACT 루프 실행 - 이 부분이 핵심
            logger.info(f"ReACT 루프 시작: {session_id}")
            
            # context 객체 준비
            context = {
                "session_id": session_id,
                "params": params,
                "dependencies": dependencies,
                "raw_task_data": raw_task_data
            }
            
            # ReACT 루프 초기화
            step_counter = 0
            should_complete = False
            final_result = None
            
            # 추론-행동-관찰 루프 실행
            while not should_complete and step_counter < max_steps:
                step_counter += 1
                logger.info(f"ReACT 루프 단계 {step_counter}/{max_steps} 시작")
                
                # 1. 추론 단계
                logger.info("추론 단계 실행")
                reasoning_result = await self._execute_reasoning(session, context)
                context["reasoning"] = reasoning_result
                
                # 완료 신호 확인
                if reasoning_result.get("next_action", "").lower() == "complete":
                    logger.info("추론 결과에서 COMPLETE 신호 감지됨. 루프 종료.")
                    should_complete = True
                    break
                
                # 2. 행동 단계
                logger.info("행동 단계 실행")
                action_result = await self._execute_action(session, reasoning_result, context)
                context["action"] = action_result
                
                # 3. 관찰 단계
                logger.info("관찰 단계 실행")
                observation_result = await self._execute_observation(session, action_result, context)
                context["observation"] = observation_result
                
                # 종료 조건 확인
                should_complete = await self._should_complete(
                    {"reasoning": reasoning_result, "action": action_result, "observation": observation_result},
                    context
                )
                
                logger.info(f"ReACT 루프 단계 {step_counter} 완료. 종료 신호: {should_complete}")
            
            # 최종 결과 생성
            logger.info("ReACT 루프 완료, 최종 결과 생성")
            final_result = await self._generate_final_result(session, context)
            
            logger.info(f"ReACT 루프 완료: {session_id}, 총 단계 수: {len(session.steps)}")
            
            # 세션 상태 업데이트
            session.status = "completed"
            session.updated_at = time.time()
            
            # 결과 반환
            return final_result
            
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
                logger.info(f"ReACT 세션 종료: {session_id}, 단계 수: {len(session.steps)}")
                del self.active_sessions[session_id]

# 에이전트 인스턴스 생성
agent = TravelPlannerAgent(app)

# FastAPI 라우트
@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "name": "Travel Planner ReACT Agent",
        "status": "online",
        "description": "여행 계획을 세우는 ReACT 에이전트",
        "agent_id": agent.agent_id,
        "agent_role": agent.agent_role
    }

# 서버 실행 (개발용)
if __name__ == "__main__":
    import uvicorn
    logger.info("Travel Planner ReACT Agent 개발 모드로 서버 시작...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8050,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    ) 