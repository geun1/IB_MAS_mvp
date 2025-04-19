import os
from typing import Dict, List, Optional, Any, Union
import logging
import asyncio
import time

# litellm 임포트
from litellm import completion, acompletion
from litellm.utils import Message

class LLMClient:
    """
    다양한 LLM 공급자(OpenAI, Anthropic 등)를 지원하는 통합 클라이언트
    litellm을 사용하여 모델 간 전환을 쉽게 합니다.
    """
    
    def __init__(
        self,
        default_model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 60.0,
        **kwargs
    ):
        """
        LLMClient 초기화
        
        Args:
            default_model: 기본 사용할 모델명 (예: "gpt-3.5-turbo", "claude-3-sonnet-20240229")
            api_key: API 키 (기본값은 환경변수에서 가져옴)
            temperature: 생성 랜덤성 (0에 가까울수록 결정적)
            max_tokens: 최대 생성 토큰 수
            max_retries: 오류 시 최대 재시도 횟수
            retry_delay: 재시도 간 지연 시간(초)
            timeout: 요청 타임아웃(초)
        """
        self.default_model = default_model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.extra_kwargs = kwargs
        
        # 로거 설정
        self.logger = logging.getLogger("llm_client")
        
    def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        동기식 텍스트 생성
        
        Args:
            messages: 메시지 목록 (시스템, 유저, 어시스턴트 역할 포함)
            model: 사용할 모델 (기본값은 인스턴스 생성 시 설정값)
            temperature: 생성 랜덤성
            max_tokens: 최대 생성 토큰 수
            
        Returns:
            응답 객체
        """
        _model = model or self.default_model
        _temperature = temperature if temperature is not None else self.temperature
        _max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        merged_kwargs = {**self.extra_kwargs, **kwargs}
        
        # 메시지 형식 검증
        validated_messages = self._validate_messages(messages)
        
        # 재시도 로직
        for attempt in range(self.max_retries):
            try:
                response = completion(
                    model=_model,
                    messages=validated_messages,
                    temperature=_temperature,
                    max_tokens=_max_tokens,
                    timeout=self.timeout,
                    **merged_kwargs
                )
                return response
            except Exception as e:
                self.logger.warning(f"LLM 호출 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # 지수 백오프
                else:
                    self.logger.error(f"최대 재시도 횟수 초과: {str(e)}")
                    raise
    
    async def acomplete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        비동기식 텍스트 생성
        
        Args:
            messages: 메시지 목록 (시스템, 유저, 어시스턴트 역할 포함)
            model: 사용할 모델 (기본값은 인스턴스 생성 시 설정값)
            temperature: 생성 랜덤성
            max_tokens: 최대 생성 토큰 수
            
        Returns:
            응답 객체
        """
        _model = model or self.default_model
        _temperature = temperature if temperature is not None else self.temperature
        _max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        merged_kwargs = {**self.extra_kwargs, **kwargs}
        
        # 메시지 형식 검증
        validated_messages = self._validate_messages(messages)
        
        # 재시도 로직
        for attempt in range(self.max_retries):
            try:
                response = await acompletion(
                    model=_model,
                    messages=validated_messages,
                    temperature=_temperature,
                    max_tokens=_max_tokens,
                    timeout=self.timeout,
                    **merged_kwargs
                )
                return response
            except Exception as e:
                self.logger.warning(f"비동기 LLM 호출 오류 (시도 {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # 지수 백오프
                else:
                    self.logger.error(f"최대 재시도 횟수 초과: {str(e)}")
                    raise
    
    def ask(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        단일 질문에 대한 응답을 생성하는 간편 메서드
        
        Args:
            prompt: 유저 질문
            system_prompt: 시스템 프롬프트 (선택 사항)
            
        Returns:
            생성된 텍스트 (문자열)
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.complete(messages=messages, **kwargs)
        return response["choices"][0]["message"]["content"]
    
    async def aask(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        단일 질문에 대한 응답을 비동기로 생성하는 간편 메서드
        
        Args:
            prompt: 유저 질문
            system_prompt: 시스템 프롬프트 (선택 사항)
            
        Returns:
            생성된 텍스트 (문자열)
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = await self.acomplete(messages=messages, **kwargs)
        return response["choices"][0]["message"]["content"]
    
    def _validate_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """메시지 형식 검증 및 변환"""
        validated = []
        for msg in messages:
            if "role" not in msg or "content" not in msg:
                raise ValueError(f"메시지 형식 오류. 'role'과 'content' 키가 필요합니다: {msg}")
            
            if msg["role"] not in ["system", "user", "assistant", "function"]:
                raise ValueError(f"잘못된 역할: {msg['role']}. 'system', 'user', 'assistant', 'function' 중 하나여야 합니다.")
            
            validated.append(msg)
        
        return validated

# 기본 인스턴스 생성 (편의를 위해)
default_client = LLMClient()
