"""
새 에이전트 템플릿 (개선 버전 + 상세 주석)
이 파일을 복사하여 새 에이전트를 만드세요.

새 에이전트 생성 단계:
1. 이 파일을 `agents/your_agent_name/main.py` 로 복사합니다.
2. 에이전트별 설정 섹션(AGENT_TYPE, AGENT_ID_PREFIX 등)을 수정합니다.
3. Pydantic 모델(`NewAgentParams`)을 정의하여 에이전트가 받을 파라미터를 명시합니다.
4. `NewAgent` 클래스 이름을 에이전트에 맞게 변경합니다 (예: `YourAgent`).
5. `__init__` 메서드에서 에이전트 설명, 역할 이름 등을 설정하고 BaseAgent 초기화를 호출합니다.
6. `load_resources` 메서드에 필요한 리소스(모델, 설정 파일 등) 로딩 로직을 구현합니다.
7. `_validate_params` 메서드를 오버라이드하여 정의된 Pydantic 모델로 유효성 검사를 수행하도록 합니다.
8. `_process_dependencies` 메서드를 필요에 따라 오버라이드하여 의존성 결과를 처리/가공합니다.
9. `process_task` 메서드에 에이전트의 핵심 비즈니스 로직을 구현합니다.
10. 필요한 경우 추가 FastAPI 엔드포인트를 정의하고 등록합니다.
11. `agents/your_agent_name/requirements.txt` 파일을 생성하고 필요한 라이브러리를 추가합니다.
12. `agents/your_agent_name/Dockerfile` 파일을 생성합니다 (다른 에이전트 Dockerfile 참고).
13. `agents/docker-compose.yml` 파일에 새 에이전트 서비스를 추가합니다.
"""
import uuid
import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException
import httpx
from pydantic import BaseModel, Field, ValidationError # Pydantic 임포트

# 공통 모듈 임포트
# Docker 환경에서는 PYTHONPATH 환경 변수를 통해 /app 경로가 포함되어 common 모듈을 찾을 수 있습니다.
# 로컬 개발 시에는 Python 경로 설정을 확인하세요.
try:
    from common.base_agent import BaseAgent
    from common.agent_types import AgentType, AGENT_DESCRIPTIONS, AGENT_DEFAULT_PARAMS
except ImportError:
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir)) # templates -> project-root
    common_path = os.path.join(project_root, 'common')
    if common_path not in sys.path:
        sys.path.append(project_root)
    from common.base_agent import BaseAgent
    from common.agent_types import AgentType, AGENT_DESCRIPTIONS, AGENT_DEFAULT_PARAMS

# FastAPI 앱 인스턴스 생성
# 에이전트별로 고유한 title, description을 설정하는 것이 좋습니다.
app = FastAPI(
    title="새 에이전트 API (템플릿)",
    description="새로운 기능을 제공하는 에이전트 API (템플릿)",
    version="1.0.0",
    docs_url="/docs", # API 문서 경로
    redoc_url="/redoc" # 대체 API 문서 경로
)

# 로깅 설정
# 환경 변수 LOG_LEVEL을 통해 로그 레벨 제어 가능 (기본값 INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# 에이전트별 로거 이름 설정 권장
logger = logging.getLogger("new_agent_template")

# --- 에이전트별 설정 ---
# 1. 에이전트 유형 설정: common.agent_types.AgentType Enum 사용 권장
#    새로운 유형이 필요하면 AgentType Enum에 추가하세요.
AGENT_TYPE = AgentType.CUSTOM
# 2. 에이전트 역할 이름: 레지스트리에 등록될 고유한 역할 이름 (예: 'text_summarizer', 'image_enhancer')
AGENT_ROLE_NAME = "template_agent"
# 3. 에이전트 ID 접두사: 생성될 에이전트 인스턴스 ID의 접두사
AGENT_ID_PREFIX = f"{AGENT_ROLE_NAME}_agent"
# 4. 하트비트 활성화 여부: 레지스트리에 주기적으로 상태 보고 여부 결정
ENABLE_HEARTBEAT = True

# 5. Pydantic 모델 정의: 에이전트가 받을 파라미터의 구조, 타입, 유효성 규칙 정의
#    FastAPI의 자동 문서 생성 및 요청 유효성 검사에 활용됩니다.
class NewAgentParams(BaseModel):
    # Field를 사용하여 상세 설명, 기본값, 제약 조건 등을 추가할 수 있습니다.
    input_data: str = Field(..., description="처리할 핵심 입력 데이터 (필수)")
    mode: Optional[str] = Field("default", description="작업 처리 모드 (선택, 기본값 'default')")
    max_length: Optional[int] = Field(None, description="최대 처리 길이 (선택)")

    # 예시: 모델 유효성 검사기 추가
    # @validator('max_length')
    # def check_max_length(cls, v):
    #     if v is not None and v <= 0:
    #         raise ValueError('max_length는 0보다 커야 합니다.')
    #     return v

# 6. BaseAgent 상속 클래스 정의: 에이전트의 실제 로직 구현
class NewAgent(BaseAgent):
    """새로운 기능을 수행하는 에이전트 클래스 (템플릿)"""

    def __init__(self, app: FastAPI):
        """
        에이전트 초기화 메서드
        - 에이전트 ID, 설명, 파라미터 정보 등을 설정하고 BaseAgent 초기화
        - 필요한 리소스 로딩 호출
        """
        # 고유 에이전트 ID 생성
        agent_id = f"{AGENT_ID_PREFIX}_{uuid.uuid4().hex[:8]}"
        # 에이전트 기능 설명 (명확하고 상세하게 작성 권장)
        description = AGENT_DESCRIPTIONS.get(AGENT_TYPE, "템플릿 기반의 새로운 기능을 수행합니다.")

        # 레지스트리 등록용 파라미터 정보 생성 (Pydantic 모델 스키마 활용)
        params_schema = NewAgentParams.schema()
        registry_params = []
        required_fields = params_schema.get('required', [])
        for name, prop in params_schema.get('properties', {}).items():
             registry_params.append({
                 "name": name,
                 "description": prop.get("description", ""),
                 "required": name in required_fields,
                 # 타입 매핑: Pydantic 타입과 JSON Schema 타입 간 변환 필요 시 조정
                 "type": prop.get("type", "string"),
                 "default": prop.get("default")
             })

        # BaseAgent 초기화 호출: 필수 정보 및 추가 설정 전달
        super().__init__(
            agent_id=agent_id,
            agent_role=AGENT_ROLE_NAME, # 정의된 역할 이름 사용
            description=description,
            app=app,
            params=registry_params, # 생성된 파라미터 정보 전달
            enable_heartbeat=ENABLE_HEARTBEAT,
            # **kwargs를 통해 BaseAgent에 추가 설정 전달 가능
            # 예: 외부 API 엔드포인트, 모델 경로 등
            # external_api_endpoint=os.getenv("MY_API_ENDPOINT")
        )

        # 에이전트별 리소스 로딩 메서드 호출
        self.load_resources()

    def load_resources(self):
        """
        에이전트가 시작될 때 필요한 리소스(모델, 설정 파일, DB 연결 등)를 로드합니다.
        BaseAgent의 self.config를 통해 __init__에서 전달된 추가 설정값에 접근 가능합니다.
        """
        logger.info(f"({self.agent_id}) 리소스 로딩 시작...")
        # 예시: 설정 파일 로드
        # config_path = self.config.get('config_file_path', 'default_config.json')
        # try:
        #     with open(config_path, 'r') as f:
        #         self.agent_specific_config = json.load(f)
        # except FileNotFoundError:
        #     logger.warning(f"설정 파일을 찾을 수 없습니다: {config_path}")
        #     self.agent_specific_config = {}

        # 예시: 머신러닝 모델 로드
        # model_path = self.config.get('model_path')
        # if model_path:
        #     self.model = load_my_model(model_path)
        # else:
        #     self.model = None
        #     logger.warning("모델 경로가 설정되지 않아 모델을 로드하지 않았습니다.")

        logger.info(f"({self.agent_id}) 리소스 로딩 완료.")

    # 7. 파라미터 유효성 검사 메서드 오버라이드: Pydantic 모델 활용
    def _validate_params(self, params: Dict[str, Any]) -> NewAgentParams:
        """
        /run 엔드포인트로 들어온 요청의 파라미터를 유효성 검사합니다.
        정의된 Pydantic 모델을 사용하여 타입을 검사하고 필수 필드를 확인합니다.
        유효성 검사 실패 시 HTTPException을 발생시켜 적절한 오류 응답을 반환합니다.
        """
        try:
            # Pydantic 모델 인스턴스 생성 시 자동으로 유효성 검사 수행
            validated_params = NewAgentParams(**params)
            logger.debug(f"({self.agent_id}) 파라미터 유효성 검사 통과: {validated_params.dict()}")
            # 유효성 검사를 통과한 Pydantic 모델 객체 반환
            return validated_params
        except ValidationError as e:
            # 유효성 검사 실패 시 상세 오류 로깅
            logger.warning(f"({self.agent_id}) 파라미터 유효성 검사 실패: {e}")
            # FastAPI가 처리할 수 있도록 HTTPException 발생 (400 Bad Request)
            error_details = e.errors() # Pydantic 오류 상세 정보
            raise HTTPException(status_code=400, detail=f"파라미터 유효성 검사 실패: {error_details}")

    # 8. 의존성 처리 메서드 오버라이드 (선택 사항)
    def _process_dependencies(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        태스크 실행 전, 이전 단계(의존성)의 결과를 처리하거나 가공합니다.
        기본 구현은 context에서 'depends_results' 리스트를 그대로 반환합니다.
        필요에 따라 특정 에이전트의 결과만 필터링하거나, 결과를 요약하는 등의 로직을 추가할 수 있습니다.
        """
        # BaseAgent의 기본 의존성 처리 로직 호출
        depends_results = super()._process_dependencies(context)
        logger.info(f"({self.agent_id}) 수신된 의존성 결과 수: {len(depends_results)}")

        # 예시: 성공한 결과만 필터링
        # successful_results = [
        #     res for res in depends_results if res.get('status') == 'success'
        # ]
        # logger.debug(f"성공한 의존성 결과 수: {len(successful_results)}")
        # return successful_results

        # 기본적으로는 가공 없이 그대로 반환
        return depends_results

    # 9. 핵심 태스크 처리 로직 구현: process_task 메서드 오버라이드 (필수)
    async def process_task(
        self,
        task_id: str,
        params: NewAgentParams, # 유효성 검사를 통과한 Pydantic 모델 객체
        dependencies: List[Dict[str, Any]], # 처리된 의존성 결과 리스트
        raw_task_data: Dict[str, Any] # 브로커로부터 받은 원본 태스크 데이터
    ) -> Dict[str, Any]:
        """
        에이전트의 핵심 비즈니스 로직을 구현하는 메서드입니다.
        유효성 검사를 통과한 파라미터와 처리된 의존성 결과를 사용하여 작업을 수행합니다.
        결과는 JSON으로 직렬화 가능한 딕셔너리 형태로 반환해야 합니다.
        처리 중 예상되는 오류(예: 잘못된 입력값 조건)는 HTTPException을 발생시켜 처리하고,
        예상치 못한 오류는 일반 Exception으로 처리되어 BaseAgent에서 오류 응답을 생성합니다.
        """
        logger.info(f"({self.agent_id}) 태스크 처리 시작: {task_id}")
        # Pydantic 모델의 .dict() 메서드로 파라미터를 딕셔너리로 로깅 가능
        logger.debug(f"처리 파라미터 ({task_id}): {params.dict()}")
        logger.debug(f"처리 의존성 ({task_id}): {dependencies}")

        # --- 여기에 에이전트의 실제 처리 로직 구현 ---

        # 예시: 파라미터 값 사용
        input_text = params.input_data
        mode = params.mode
        max_len = params.max_length

        # 예시: 간단한 텍스트 처리
        processed_text = f"모드 '{mode}'로 처리된 텍스트: {input_text}"
        if max_len is not None and len(processed_text) > max_len:
            processed_text = processed_text[:max_len] + "..."

        # 예시: 의존성 결과 활용 (예: Writer Agent가 Web Search Agent 결과 참고)
        reference_summary = "없음"
        if dependencies:
            # 첫 번째 성공한 의존성 결과의 내용을 요약에 추가 (결과 구조는 에이전트마다 다름)
            first_success_result = next((res['result'] for res in dependencies if res.get('status') == 'success' and 'result' in res), None)
            if first_success_result:
                 # 결과 내용 추출 (다양한 키를 고려)
                 content = first_success_result.get('content') or first_success_result.get('output') or first_success_result.get('message')
                 if content and isinstance(content, str):
                     reference_summary = f"참고: {content[:50]}..."

        # 예시: 외부 API 호출 (BaseAgent의 공유 http_client 사용)
        # try:
        #     api_url = self.config.get("external_api_endpoint", "https://api.example.com/default")
        #     payload = {"text": input_text, "mode": mode}
        #     response = await self.http_client.post(api_url, json=payload)
        #     response.raise_for_status() # 오류 발생 시 예외 발생
        #     api_data = response.json()
        #     processed_text += f"\nAPI 결과: {api_data.get('result', 'N/A')}"
        # except httpx.HTTPStatusError as e:
        #     logger.error(f"({task_id}) 외부 API 호출 실패 ({e.response.status_code}): {e.response.text}")
        #     # 서비스 일시 장애 등 예상 가능한 오류는 HTTPException으로 처리하여 사용자에게 안내
        #     raise HTTPException(status_code=503, detail=f"외부 서비스({api_url}) 호출에 실패했습니다.")
        # except Exception as e:
        #     logger.exception(f"({task_id}) 외부 API 호출 중 예상치 못한 오류: {str(e)}")
        #     # 예상치 못한 오류는 BaseAgent에서 500 Internal Server Error로 처리됨
        #     raise # 예외를 다시 발생시켜 BaseAgent에서 처리하도록 함

        # --- 처리 결과 반환 ---
        # 결과는 반드시 JSON 직렬화 가능한 딕셔너리 형태여야 합니다.
        final_result = {
            "status_message": f"태스크 ({task_id}) 성공적으로 처리됨.",
            "processed_output": processed_text,
            "input_length": len(input_text),
            "mode_used": mode,
            "reference_summary": reference_summary
            # 필요한 다른 결과 필드 추가
        }

        logger.info(f"({self.agent_id}) 태스크 처리 완료: {task_id}")
        return final_result

# 10. 에이전트 인스턴스 생성: FastAPI 앱과 함께 에이전트 클래스 인스턴스화
agent = NewAgent(app)

# --- FastAPI 이벤트 핸들러 ---
# 모든 에이전트에 반드시 필요한 이벤트 핸들러:
# 1. startup: 서버 시작 시 에이전트를 레지스트리에 등록하고 하트비트 시작
# 2. shutdown: 서버 종료 시 에이전트를 레지스트리에서 해제

@app.on_event("startup")
async def startup_event():
    """
    애플리케이션 시작 시 필요한 설정 수행
    - 레지스트리에 에이전트 등록
    - 하트비트 시작
    """
    logger.info(f"에이전트 시작 중: {agent.agent_id} ({agent.agent_role})")
    try:
        # 레지스트리에 에이전트 등록
        await agent.register()
        logger.info(f"레지스트리 등록 완료: {agent.agent_id}")
        
        # 하트비트 활성화된 경우, 하트비트 시작
        if agent.enable_heartbeat:
            await agent._start_heartbeat()
            logger.info(f"하트비트 시작됨 (간격: {agent.heartbeat_interval}초)")
        else:
            logger.info("하트비트 비활성화됨")
    except Exception as e:
        logger.error(f"에이전트 시작 중 오류: {str(e)}")
        # 심각한 오류인 경우 서버 종료 고려
        # import sys
        # sys.exit(1)

@app.on_event("shutdown")
async def shutdown_event():
    """
    애플리케이션 종료 시 처리
    - 레지스트리에서 에이전트 등록 해제
    - 열린 자원 정리
    """
    logger.info(f"에이전트 종료 중: {agent.agent_id}")
    try:
        # 레지스트리에서 에이전트 등록 해제
        await agent.unregister()
        logger.info(f"레지스트리 등록 해제 완료: {agent.agent_id}")
        
        # HTTP 클라이언트 종료
        if agent.http_client:
            await agent.http_client.aclose()
            logger.info("HTTP 클라이언트 종료됨")
        
        # 기타 자원 정리 (필요시 추가)
    except Exception as e:
        logger.error(f"에이전트 종료 중 오류: {str(e)}")
    finally:
        logger.info(f"에이전트 종료 완료: {agent.agent_id}")

# 11. 추가 API 엔드포인트 등록 (선택 사항)
# 에이전트의 특정 상태를 조회하거나 관리 기능을 위한 엔드포인트를 추가할 수 있습니다.
@app.get("/health")
async def health_check():
    """
    에이전트 상태 확인 엔드포인트
    - 로드 밸런서, 모니터링 시스템 등에서 활용
    """
    return {
        "status": "healthy", 
        "agent_id": agent.agent_id, 
        "role": agent.agent_role,
        "active_tasks": len(app.state.active_tasks) if hasattr(app.state, "active_tasks") else 0
    }

# 12. 개발/테스트용 서버 실행 코드
# 이 스크립트 파일을 직접 실행할 때(예: python main.py) uvicorn 서버를 실행합니다.
# Docker 환경에서는 일반적으로 docker-compose.yml의 command를 통해 실행됩니다.
if __name__ == "__main__":
    import uvicorn
    logger.info("템플릿 에이전트 개발 모드로 서버 시작...")
    # uvicorn.run()의 첫 번째 인자는 "파이썬_파일_이름:FastAPI_앱_인스턴스_변수명" 형식입니다.
    uvicorn.run(
        "new_agent_template:app", # 현재 파일명:app 변수
        host="0.0.0.0", # 모든 인터페이스에서 접속 허용
        port=8000, # 기본 포트 (docker-compose에서 매핑 변경 가능)
        reload=True, # 코드 변경 시 서버 자동 재시작 (개발 시 유용)
        log_level=LOG_LEVEL.lower() # 환경 변수에 따른 로그 레벨 적용
    ) 