"""
LLM API 호출 관리를 위한 클라이언트
"""
import logging
import json
import os
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# 공통 LLM 클라이언트 임포트
from common.llm_client import LLMClient

from .config import LLM_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS
from .prompts.task_decomposition import create_task_decomposition_prompt
from .prompts.result_integration import create_result_integration_prompt

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrchestratorLLMClient:
    """오케스트레이터의 LLM 통신을 담당하는 클라이언트"""
    
    def __init__(self):
        """LLM 클라이언트 초기화"""
        # API 키 확인 및 로깅
        logger.info(f"LLM_API_KEY 설정 여부: {bool(LLM_API_KEY)}")
        
        # 환경 변수로 직접 설정 (LiteLLM이 이 환경 변수를 사용함)
        if LLM_API_KEY and LLM_API_KEY.strip():
            os.environ["OPENAI_API_KEY"] = LLM_API_KEY
            masked_key = f"{LLM_API_KEY[:4]}...{LLM_API_KEY[-4:]}" if len(LLM_API_KEY) > 8 else "***"
            logger.info(f"LLM API 키 설정됨: {masked_key}")
        else:
            logger.warning("LLM API 키가 설정되지 않았습니다!")
            logger.info("로컬 모델을 대체로 사용합니다.")
        
        # Ollama 연결 정보 설정
        os.environ["OLLAMA_HOST"] = "host.docker.internal:11434"
        logger.info(f"Ollama 호스트 설정됨: {os.environ.get('OLLAMA_HOST')}")
        
        # 공통 LLM 클라이언트 사용
        self.client = LLMClient()
        self.model = LLM_MODEL
        self.fallback_models = [
            "gpt-4o-mini", 
            "ollama/llama3:latest",
            "ollama/mistral:latest"
        ]  # 여러 대체 모델 설정
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS
        logger.info(f"LLM 클라이언트 초기화 완료 (기본 모델: {self.model}, temperature: {self.temperature}, max_tokens: {self.max_tokens})")
    
    def _format_conversation_context(self, messages: List[Dict[str, Any]]) -> str:
        """
        대화 메시지 목록을 컨텍스트 문자열로 변환
        
        Args:
            messages: 대화 메시지 목록
            
        Returns:
            포맷팅된 대화 컨텍스트 문자열
        """
        if not messages:
            return ""
            
        context = []
        for msg in messages:
            if "request" in msg and "response" in msg:
                context.append(f"사용자: {msg['request']}")
                context.append(f"시스템: {msg['response']}")
                
        return "\n".join(context)
    
    async def decompose_tasks(self, user_query: str, available_roles: str, agents_detail: str = None, conversation_context: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        사용자 요청을 여러 태스크로 분해
        
        Args:
            user_query: 사용자 질의
            available_roles: 사용 가능한 에이전트 역할 정보
            agents_detail: 에이전트 상세 정보 (선택적)
            conversation_context: 이전 대화 컨텍스트 (선택적)
            
        Returns:
            분해된 태스크 정보
        """
        try:
            # 대화 컨텍스트 포맷팅
            formatted_context = self._format_conversation_context(conversation_context) if conversation_context else None
            
            # LLM 호출 준비
            prompt = create_task_decomposition_prompt(
                user_query=user_query,
                available_roles=available_roles,
                agents_detail=agents_detail,
                conversation_context=formatted_context
            )
            
            logger.info(f"LLM 태스크 분해 프롬프트:\n{prompt}")
            logger.info(f"LLM 설정 - temperature: {self.temperature}, max_tokens: {self.max_tokens}")

            response_content = await self.client.aask(
                prompt=prompt,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            logger.info(f"LLM 태스크 분해 응답 원문:\n{response_content}") # 응답 원문 로깅 추가

            # JSON 파싱 시도
            try:
                # 응답 문자열에서 JSON 부분만 추출 시도 (마크다운 코드 블록 등 제거)
                import re
                json_match = re.search(r'```json\\s*([\\s\\S]*?)\\s*```', response_content)
                if json_match:
                    json_str = json_match.group(1).strip()
                    logger.info("마크다운 코드 블록에서 JSON 추출 완료")
                else:
                    # JSON 객체가 직접 반환된 경우 처리
                    json_str = response_content.strip()
                    # 추가 검증: 문자열이 '{'로 시작하고 '}'로 끝나는지 확인
                    if not (json_str.startswith('{') and json_str.endswith('}')):
                         logger.warning("응답이 JSON 객체 형식이 아닐 수 있습니다. 파싱을 시도합니다.")
                
                decomposition = json.loads(json_str)
                logger.info("LLM 응답 JSON 파싱 성공")
                return decomposition
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류: {e}")
                logger.error(f"파싱 실패한 내용: {json_str}") # 파싱 실패 내용 로깅
                # 실패 시 빈 딕셔너리 반환 또는 다른 오류 처리 로직
                return {"tasks": [], "error": f"JSON 파싱 실패: {e}"}

        except Exception as e:
            logger.error(f"LLM API 호출 중 오류 발생: {e}", exc_info=True)
            # LLM 호출 실패 시 빈 딕셔너리 반환 또는 다른 오류 처리 로직
            return {"tasks": [], "error": f"LLM API 호출 실패: {e}"}
    
    def _extract_json(self, text: str) -> str:
        """
        텍스트에서 JSON 부분만 추출
        
        Args:
            text: 원본 텍스트
            
        Returns:
            추출된 JSON 문자열
        """
        # JSON 블록 찾기
        start_idx = text.find('{')
        if start_idx == -1:
            raise ValueError("JSON을 찾을 수 없습니다")
        
        # 중괄호 개수를 세어 JSON 블록 끝 찾기
        open_braces = 0
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                open_braces += 1
            elif text[i] == '}':
                open_braces -= 1
                if open_braces == 0:
                    return text[start_idx:i+1]
        
        # JSON이 완전하지 않은 경우
        raise ValueError("유효한 JSON 구조를 찾을 수 없습니다")
    
    async def integrate_results(self, original_query: str, tasks_results: str) -> Union[Dict[str, Any], str]:
        """
        LLM을 사용하여 태스크 결과를 통합
        
        Args:
            original_query: 원본 사용자 질의
            tasks_results: 태스크 결과 텍스트
            
        Returns:
            통합된 결과 (딕셔너리 또는 문자열)
        """
        try:
            logger.info("LLM API 호출: 결과 통합")
            logger.info(f"LLM 설정 - temperature: {self.temperature}, max_tokens: {self.max_tokens}")
            
            # 결과 통합 프롬프트 생성
            prompt = create_result_integration_prompt(original_query, tasks_results)
            
            # OpenAI API 호환성 문제로 인해 fallback 모델 로직을 수동으로 구현
            try:
                logger.info(f"모델 시도 중: {self.model}")
                response = await self.client.aask(
                    prompt=prompt, 
                    model=self.model, 
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                logger.info(f"모델 {self.model} 성공!")
                
                # 결과를 딕셔너리 형식으로 반환
                return {
                    "message": response,
                    "status": "success"
                }
            except Exception as primary_error:
                logger.warning(f"주 모델 {self.model}로 결과 통합 실패: {str(primary_error)}")
                
                # 폴백 모델 순차적으로 시도
                for fallback_model in self.fallback_models:
                    try:
                        logger.info(f"폴백 모델 시도 중: {fallback_model}")
                        response = await self.client.aask(
                            prompt=prompt, 
                            model=fallback_model, 
                            temperature=self.temperature,
                            max_tokens=self.max_tokens
                        )
                        logger.info(f"폴백 모델 {fallback_model} 성공!")
                        
                        return {
                            "message": response,
                            "status": "success"
                        }
                    except Exception as fallback_error:
                        logger.warning(f"폴백 모델 {fallback_model}로 결과 통합 실패: {str(fallback_error)}")
                
                # 모든 모델이 실패한 경우
                raise Exception(f"모든 모델 시도 실패. 원본 오류: {str(primary_error)}")
                
        except Exception as e:
            logger.error(f"결과 통합 중 오류 발생: {str(e)}")
            raise

    async def test_connection(self):
        """LLM API 연결 테스트"""
        try:
            logger.info("LLM API 연결 테스트 중...")
            models = [self.model] + self.fallback_models
            results = {}
            
            for model in models:
                try:
                    start_time = __import__('time').time()
                    # 비동기 메서드 aask 사용
                    response = await self.client.aask(
                        "Hello, testing connection", 
                        model=model
                    )
                    end_time = __import__('time').time()
                    
                    results[model] = {
                        "status": "success",
                        "response": response[:100] + "...",
                        "time": round(end_time - start_time, 2)
                    }
                    logger.info(f"모델 {model} 연결 성공! 응답 시간: {results[model]['time']}초")
                except Exception as e:
                    results[model] = {
                        "status": "error",
                        "error": str(e)
                    }
                    logger.warning(f"모델 {model} 연결 실패: {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"연결 테스트 중 오류 발생: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def aask(self, prompt: str, model: str = None, temperature: float = None, max_tokens: int = None) -> str:
        """
        LLM에 비동기 요청을 보내고 응답을 받음
        
        Args:
            prompt: 프롬프트
            model: 사용할 모델 (기본값: self.model)
            temperature: 온도 설정 (기본값: self.temperature)
            max_tokens: 최대 토큰 수 (기본값: self.max_tokens)
            
        Returns:
            LLM 응답 문자열
        """
        try:
            # 기본값 설정
            model = model or self.model
            temperature = temperature if temperature is not None else self.temperature
            max_tokens = max_tokens if max_tokens is not None else self.max_tokens
            
            logger.info(f"LLM 요청 - 모델: {model}, temperature: {temperature}, max_tokens: {max_tokens}")
            
            # LLM 클라이언트 호출
            response = await self.client.aask(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            logger.info(f"LLM 응답 수신 (길이: {len(response)})")
            return response
            
        except Exception as e:
            logger.error(f"LLM 요청 중 오류 발생: {str(e)}")
            raise 