"""
기본 에이전트 클래스 - 모든 에이전트가 상속받는 추상 클래스 (개선 버전)
"""
import asyncio
import logging
import os
import httpx
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import psutil
from fastapi import FastAPI, Request, HTTPException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import uuid

# 공통 LLM 모듈 추가
from common.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 재시도 설정
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 2

class BaseAgent(ABC):
    """
    모든 에이전트의 기본 기능을 제공하는 추상 클래스 (개선 버전)
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_role: str,
        description: str,
        app: FastAPI,
        params: List[Dict[str, Any]] = None,
        registry_url: str = None,
        container_name: str = None,
        port: int = None,
        heartbeat_interval: int = 20,
        enable_heartbeat: bool = True, # 하트비트 활성화 플래그 추가
        **kwargs: Any # 추가 설정 로드를 위한 kwargs
    ):
        """
        에이전트 초기화
        
        Args:
            agent_id: 에이전트 고유 ID
            agent_role: 에이전트 역할 (예: web_search, writer 등)
            description: 에이전트 기능 설명
            app: FastAPI 애플리케이션 인스턴스
            params: API 파라미터 정의 (이름, 타입, 설명 등)
            registry_url: 레지스트리 서버 URL
            container_name: 도커 컨테이너 이름
            port: API 서버 포트
            heartbeat_interval: 하트비트 전송 간격(초)
            enable_heartbeat: 하트비트 전송 활성화 여부
            **kwargs: 추가적인 에이전트별 설정
        """
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.description = description
        self.app = app
        self.params = params or []
        
        # 환경 변수 또는 기본값 설정
        self.registry_url = registry_url or os.getenv("REGISTRY_URL", "http://registry:8000")
        self.container_name = container_name or os.getenv("CONTAINER_NAME", agent_role)
        self.port = port or int(os.getenv("PORT", "8000"))
        self.heartbeat_interval = heartbeat_interval
        self.enable_heartbeat = enable_heartbeat
        
        # 에이전트별 추가 설정 로드
        self.config = self._load_config(**kwargs)
        
        # 상태 관리
        self.app.state.active_tasks = set()
        
        # HTTP 클라이언트 초기화 (재사용)
        self.http_client = httpx.AsyncClient(timeout=30.0) # 타임아웃 설정
        
        # LLM 클라이언트 초기화 (기본 모델)
        self.llm_client = LLMClient(default_model=os.getenv("LLM_MODEL", "gpt-4o-mini"))
        
        # 기본 라우트 설정
        self._setup_routes()
        
        # 시작/종료 이벤트 설정
        self._setup_events()
        
        logger.info(f"{self.agent_role} 에이전트 ({self.agent_id}) 초기화 완료")

    def _load_config(self, **kwargs) -> Dict[str, Any]:
        """
        에이전트별 설정을 로드합니다. 서브클래스에서 오버라이드하여 사용할 수 있습니다.
        기본적으로 kwargs를 반환합니다.
        """
        config = {}
        # 예: 환경 변수에서 API 키 로드
        # config['api_key'] = os.getenv(f"{self.agent_role.upper()}_API_KEY")
        config.update(kwargs)
        logger.debug(f"에이전트 설정 로드: {config}")
        return config

    def _setup_routes(self):
        """기본 API 라우트 설정"""
        self.app.get("/")(self.root)
        self.app.get("/health")(self.health)
        self.app.post("/run")(self.run)
        
        # LLM 설정 관련 엔드포인트 추가
        self.app.post("/api/settings/llm-config")(self.update_llm_config)
        self.app.get("/api/settings/llm-status")(self.get_llm_status)
        self.app.get("/api/settings/test-llm-connection/{model_name}")(self.test_llm_connection)
    
    def _setup_events(self):
        """애플리케이션 시작/종료 이벤트 설정"""
        self.app.on_event("startup")(self.startup_event)
        self.app.on_event("shutdown")(self.shutdown_event)
    
    async def startup_event(self):
        """애플리케이션 시작 시 호출되는 이벤트 핸들러"""
        await self.register_agent_with_retry()
        if self.enable_heartbeat:
            asyncio.create_task(self.send_heartbeat_with_retry())
        logger.info(f"{self.agent_role} 에이전트 ({self.agent_id}) 시작됨")
    
    async def shutdown_event(self):
        """애플리케이션 종료 시 호출되는 이벤트 핸들러"""
        await self.unregister_agent_with_retry()
        await self.http_client.aclose() # HTTP 클라이언트 종료
        logger.info(f"{self.agent_role} 에이전트 ({self.agent_id}) 종료됨")

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_fixed(RETRY_WAIT_SECONDS),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True # 재시도 실패 시 예외 다시 발생
    )
    async def register_agent_with_retry(self):
        """레지스트리에 에이전트 등록 (재시도 포함)"""
        try:
            service_endpoint = f"http://{self.container_name}:{self.port}/run"
            agent_data = {
                "id": self.agent_id,
                "role": self.agent_role,
                "description": self.description,
                "endpoint": service_endpoint,
                "type": "function",
                "params": self.params
            }
            
            response = await self.http_client.post(
                f"{self.registry_url}/register",
                json=agent_data
            )
            response.raise_for_status() # 2xx 외 상태 코드 시 예외 발생
            
            logger.info(f"에이전트 등록 성공: {self.agent_id}")
            return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"에이전트 등록 실패 (HTTP 상태 오류): {e.response.status_code}, {e.response.text}")
            # 특정 상태 코드에 따라 다른 처리 가능
            if e.response.status_code == 409: # 이미 등록된 경우
                 logger.warning(f"에이전트 {self.agent_id}는 이미 등록되어 있습니다.")
                 return True # 성공으로 간주
            raise # 다른 HTTP 오류는 재시도 또는 최종 실패 처리
        except httpx.RequestError as e:
            logger.error(f"에이전트 등록 중 통신 오류 (재시도 {e.attempt_number if hasattr(e, 'attempt_number') else '1'}): {str(e)}")
            raise # 재시도 로직을 위해 예외 다시 발생
        except Exception as e:
            logger.exception(f"에이전트 등록 중 예상치 못한 오류: {str(e)}")
            return False # 최종 실패

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_fixed(RETRY_WAIT_SECONDS),
        retry=retry_if_exception_type(httpx.RequestError),
    )
    async def unregister_agent_with_retry(self):
        """레지스트리에서 에이전트 등록 해제 (재시도 포함)"""
        try:
            response = await self.http_client.post(
                f"{self.registry_url}/unregister",
                params={"role": self.agent_role, "agent_id": self.agent_id}
            )
            logger.info(f"에이전트 등록 해제 응답: {response.status_code}")
            
            if response.status_code != 200:
                # 백업 메서드 시도
                backup_response = await self.http_client.post(
                    f"{self.registry_url}/unregister_direct",
                    params={"role": self.agent_role, "agent_id": self.agent_id}
                )
                logger.info(f"백업 등록 해제 응답: {backup_response.status_code}")
                backup_response.raise_for_status()
            else:
                response.raise_for_status()

        except httpx.RequestError as e:
            logger.error(f"등록 해제 요청 중 통신 오류 (재시도 {e.attempt_number if hasattr(e, 'attempt_number') else '1'}): {str(e)}")
            raise # 재시도
        except Exception as e:
            logger.error(f"에이전트 등록 해제 중 오류: {str(e)}")

    async def send_heartbeat_with_retry(self):
        """Registry에 하트비트 전송 (재시도 포함, 주기적 실행)"""
        while True:
            try:
                await self._send_single_heartbeat()
            except Exception as e:
                # 하트비트 실패는 로깅만 하고 계속 시도 (에이전트 중단 방지)
                logger.error(f"하트비트 전송 실패 후 재시도 대기: {str(e)}")
            
            await asyncio.sleep(self.heartbeat_interval)

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_fixed(RETRY_WAIT_SECONDS),
        retry=retry_if_exception_type(httpx.RequestError),
    )
    async def _send_single_heartbeat(self):
        """단일 하트비트 전송 로직"""
        try:
            memory_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent()
            active_tasks_count = len(self.app.state.active_tasks)
            
            heartbeat_data = {
                "status": "active",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "memory_usage": memory_usage,
                    "cpu_usage": cpu_usage,
                    "active_tasks": active_tasks_count
                },
                "version": "1.0.0" # 버전 정보 추가 가능
            }
            
            url = f"{self.registry_url}/heartbeat/{self.agent_role}/{self.agent_id}"
            response = await self.http_client.post(url, json=heartbeat_data)
            response.raise_for_status()
            logger.debug("Heartbeat 전송 성공")

        except httpx.RequestError as e:
            logger.warning(f"Heartbeat 전송 중 통신 오류 (재시도 {e.attempt_number if hasattr(e, 'attempt_number') else '1'}): {str(e)}")
            raise # 재시도
        except Exception as e:
            logger.error(f"Heartbeat 전송 중 예상치 못한 오류: {str(e)}")
            # 예상치 못한 오류는 재시도하지 않음 (필요시 수정)

    async def root(self):
        """루트 경로 핸들러"""
        return {
            "status": "online", 
            "service": f"{self.agent_role.capitalize()} Agent", 
            "id": self.agent_id, 
            "role": self.agent_role
        }
    
    async def health(self):
        """상태 확인 핸들러"""
        # TODO: 더 상세한 상태 확인 로직 추가 가능 (예: 의존 서비스 연결 상태)
        return {"status": "healthy"}
    
    async def run(self, request: Request):
        """태스크 실행 핸들러"""
        task_data = None
        task_id = "unknown"
        try:
            task_data = await request.json()
            task_id = task_data.get("task_id", f"no_id_{uuid.uuid4().hex[:6]}")
            logger.info(f"태스크 수신: {task_id} (Role: {self.agent_role})")
            logger.debug(f"수신된 태스크 데이터 ({task_id}): {json.dumps(task_data, indent=2)}")
            
            self.app.state.active_tasks.add(task_id)

            # 1. 파라미터 유효성 검사
            validated_params = self._validate_params(task_data.get("params", {}))
            
            # 2. 의존성 결과 처리
            processed_dependencies = self._process_dependencies(task_data.get("context", {}))

            # 3. 핵심 태스크 처리 로직 호출
            result = await self.process_task(
                task_id=task_id,
                params=validated_params,
                dependencies=processed_dependencies,
                raw_task_data=task_data # 원본 데이터도 필요시 전달
            )
            
            response = {
                "status": "success",
                "task_id": task_id,
                "result": result
            }
            logger.info(f"태스크 완료: {task_id}")
            logger.debug(f"태스크 결과 ({task_id}): {json.dumps(response, indent=2, default=str)}") # 결과 로깅
            return response
            
        except HTTPException as e:
            logger.warning(f"태스크 처리 중 HTTP 예외 ({task_id}): {e.status_code} - {e.detail}")
            return {
                "status": "error",
                "task_id": task_id,
                "error": f"HTTP Error {e.status_code}: {e.detail}",
                "result": {"error_message": e.detail}
            }
        except json.JSONDecodeError:
            logger.error(f"잘못된 JSON 형식의 태스크 데이터 수신 ({task_id})")
            return {
                "status": "error",
                "task_id": task_id,
                "error": "Invalid JSON format",
                "result": {"error_message": "요청 형식이 잘못되었습니다."}
            }
        except Exception as e:
            logger.exception(f"태스크 실행 중 심각한 오류 ({task_id}): {str(e)}")
            return {
                "status": "error",
                "task_id": task_id,
                "error": f"Internal Server Error: {str(e)}",
                "result": {"error_message": f"처리 중 내부 오류가 발생했습니다."}
            }
        finally:
            if task_id in self.app.state.active_tasks:
                self.app.state.active_tasks.remove(task_id)

    def _validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        입력 파라미터 유효성 검사. 필요시 서브클래스에서 오버라이드.
        기본 구현은 받은 파라미터를 그대로 반환.
        """
        # 예시: 필수 파라미터 확인
        # required_params = [p['name'] for p in self.params if p.get('required')]
        # for req_param in required_params:
        #     if req_param not in params:
        #         raise HTTPException(status_code=400, detail=f"필수 파라미터 누락: {req_param}")
        
        # 예시: 타입 검사 (Pydantic 모델 사용 권장)
        # try:
        #     MyParamModel(**params) # Pydantic 모델로 유효성 검사
        # except ValidationError as e:
        #     raise HTTPException(status_code=400, detail=f"파라미터 유효성 검사 실패: {e}")
            
        logger.debug(f"파라미터 유효성 검사 통과: {params}")
        return params

    def _process_dependencies(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        의존성 결과 처리. 필요시 서브클래스에서 오버라이드.
        기본 구현은 'depends_results' 키의 값을 반환.
        """
        depends_results = context.get("depends_results", [])
        logger.debug(f"처리된 의존성 결과 수: {len(depends_results)}")
        # 여기에 필요한 추가 처리 로직 구현 가능
        # 예: 특정 에이전트의 결과만 필터링, 결과 형식 변환 등
        return depends_results

    @abstractmethod
    async def process_task(
        self, 
        task_id: str,
        params: Dict[str, Any], 
        dependencies: List[Dict[str, Any]],
        raw_task_data: Dict[str, Any] # 원본 데이터 추가
    ) -> Dict[str, Any]:
        """
        핵심 태스크 처리 로직 - 서브클래스에서 반드시 구현해야 함
        
        Args:
            task_id: 현재 태스크의 고유 ID
            params: 유효성 검사를 거친 파라미터
            dependencies: 처리된 의존성 결과 목록
            raw_task_data: 브로커로부터 받은 원본 태스크 데이터
            
        Returns:
            처리 결과 (JSON 직렬화 가능해야 함)
            
        Raises:
            HTTPException: 처리 중 예상된 오류 발생 시 (예: 잘못된 입력)
            Exception: 처리 중 예상치 못한 오류 발생 시
        """
        pass 

    # LLM 설정 업데이트 엔드포인트
    async def update_llm_config(self, request: Request):
        """에이전트 LLM 설정 업데이트"""
        try:
            data = await request.json()
            config = data.get("config", {})
            
            # LLM 설정 정보 추출
            model_name = config.get("modelName")
            temperature = config.get("temperature", 0.7)
            max_tokens = config.get("maxTokens", 1024)
            
            if not model_name:
                return {
                    "success": False,
                    "message": "모델 이름은 필수 항목입니다."
                }
            
            # LLM 클라이언트 설정 업데이트
            self.llm_client = LLMClient(
                default_model=model_name,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 로깅
            logger.info(f"{self.agent_role} 에이전트의 LLM 설정 업데이트: 모델={model_name}, 온도={temperature}, 최대토큰={max_tokens}")
            
            return {
                "success": True,
                "message": f"{self.agent_role} LLM 설정이 업데이트되었습니다."
            }
        except Exception as e:
            logger.error(f"LLM 설정 업데이트 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "message": f"LLM 설정 업데이트 실패: {str(e)}"
            }
    
    # LLM 상태 조회 엔드포인트
    async def get_llm_status(self):
        """현재 LLM 설정 및 상태 조회"""
        try:
            if not hasattr(self, 'llm_client') or not self.llm_client:
                return {
                    "success": True,
                    "initialized": False,
                    "message": "LLM 클라이언트가 초기화되지 않았습니다."
                }
            
            # 현재 LLM 클라이언트 설정 조회
            return {
                "success": True,
                "initialized": True,
                "model": self.llm_client.default_model,
                "temperature": self.llm_client.temperature,
                "max_tokens": self.llm_client.max_tokens
            }
        except Exception as e:
            logger.error(f"LLM 상태 조회 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "message": f"LLM 상태 조회 실패: {str(e)}"
            }
            
    # LLM 모델 연결 테스트 엔드포인트
    async def test_llm_connection(self, model_name: str):
        """특정 LLM 모델의 연결 테스트 수행"""
        try:
            logger.info(f"LLM 모델 '{model_name}' 연결 테스트 시작")
            
            # 테스트 프롬프트
            test_prompt = "간단한 테스트입니다. '테스트 성공'이라고 응답해주세요."
            
            # 임시 LLM 클라이언트 생성
            test_client = LLMClient(default_model=model_name)
            
            # 비동기 호출
            start_time = datetime.now().timestamp()
            try:
                response = await test_client.aask(test_prompt)
                execution_time = datetime.now().timestamp() - start_time
                
                logger.info(f"LLM 모델 '{model_name}' 테스트 성공! 응답 시간: {execution_time:.2f}초")
                return {
                    "success": True,
                    "model": model_name,
                    "response": response,
                    "execution_time": execution_time,
                    "message": f"LLM 모델 '{model_name}' 연결 테스트 성공"
                }
            except Exception as e:
                execution_time = datetime.now().timestamp() - start_time
                logger.error(f"LLM 모델 '{model_name}' 연결 테스트 실패: {str(e)}")
                return {
                    "success": False,
                    "model": model_name,
                    "error": str(e),
                    "execution_time": execution_time,
                    "message": f"LLM 모델 '{model_name}' 연결 테스트 실패: {str(e)}"
                }
        except Exception as e:
            logger.error(f"LLM 모델 테스트 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "message": f"LLM 모델 테스트 중 오류 발생: {str(e)}"
            } 