"""
Example Agent - 입력 텍스트를 대문자로 변환하는 예시 에이전트
"""
import uuid
import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException
import httpx
from pydantic import BaseModel, Field, ValidationError

# 공통 모듈 임포트
# 'common' 디렉토리가 Python 경로에 포함되어 있어야 합니다.
# Docker 환경에서는 PYTHONPATH 환경 변수를 통해 설정됩니다.
try:
    from common.base_agent import BaseAgent
    from common.agent_types import AgentType, AGENT_DESCRIPTIONS, AGENT_DEFAULT_PARAMS
except ImportError:
    # 로컬 개발 환경 등에서 경로 문제가 발생할 경우를 대비한 처리
    import sys
    # 현재 파일의 상위 디렉토리(agents)의 상위 디렉토리(project-root)를 경로에 추가
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    common_path = os.path.join(project_root, 'common')
    if common_path not in sys.path:
        sys.path.append(project_root) # project-root 를 추가해야 common 을 찾을 수 있음
    from common.base_agent import BaseAgent
    from common.agent_types import AgentType, AGENT_DESCRIPTIONS, AGENT_DEFAULT_PARAMS


# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Example Agent API",
    description="텍스트를 대문자로 변환하는 예시 에이전트 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("example_agent")

# --- 에이전트별 설정 ---
# 1. 에이전트 유형 정의 (AgentType Enum 활용 권장)
AGENT_TYPE = AgentType.CUSTOM # 필요시 AgentType에 'EXAMPLE' 추가 가능
AGENT_ROLE_NAME = "example_transformer" # 레지스트리에 등록될 역할 이름
AGENT_ID_PREFIX = f"{AGENT_ROLE_NAME}_agent"
ENABLE_HEARTBEAT = True

# 2. Pydantic 모델 정의 (입력 파라미터 유효성 검사용)
class ExampleAgentParams(BaseModel):
    text_input: str = Field(..., description="대문자로 변환할 텍스트")
    add_prefix: bool = Field(False, description="결과 앞에 'Transformed:' 접두사 추가 여부")

class ExampleAgent(BaseAgent):
    """텍스트 변환 예시 에이전트 클래스"""

    def __init__(self, app: FastAPI):
        """
        에이전트 초기화
        """
        agent_id = f"{AGENT_ID_PREFIX}_{uuid.uuid4().hex[:8]}"
        description = "입력된 텍스트를 대문자로 변환하고 선택적으로 접두사를 추가합니다."

        # 3. 레지스트리 등록용 파라미터 정보 생성 (Pydantic 모델 스키마 활용)
        params_schema = ExampleAgentParams.schema()
        registry_params = []
        required_fields = params_schema.get('required', [])
        for name, prop in params_schema.get('properties', {}).items():
             registry_params.append({
                 "name": name,
                 "description": prop.get("description", ""),
                 "required": name in required_fields,
                 "type": prop.get("type", "string"),
                 "default": prop.get("default")
             })

        # 4. BaseAgent 초기화 호출
        super().__init__(
            agent_id=agent_id,
            agent_role=AGENT_ROLE_NAME, # 역할 이름 사용
            description=description,
            app=app,
            params=registry_params,
            enable_heartbeat=ENABLE_HEARTBEAT,
            # 필요한 추가 설정값 전달 가능 (예: 외부 API 엔드포인트)
            # transformation_mode="uppercase"
        )

        # 5. 에이전트별 리소스 로딩
        self.load_resources()

    def load_resources(self):
        """에이전트가 사용하는 리소스 로드"""
        logger.info(f"({self.agent_id}) 리소스 로딩 시작...")
        # 이 예제에서는 특별히 로드할 리소스가 없음
        # self.transformation_mode = self.config.get('transformation_mode', 'uppercase')
        logger.info(f"({self.agent_id}) 리소스 로딩 완료.")

    # 6. 파라미터 유효성 검사 메서드 오버라이드 (Pydantic 모델 사용)
    def _validate_params(self, params: Dict[str, Any]) -> ExampleAgentParams:
        """Pydantic을 사용하여 파라미터 유효성 검사"""
        try:
            validated_params = ExampleAgentParams(**params)
            logger.debug(f"({self.agent_id}) 파라미터 유효성 검사 통과: {validated_params.dict()}")
            return validated_params
        except ValidationError as e:
            logger.warning(f"({self.agent_id}) 파라미터 유효성 검사 실패: {e}")
            error_details = e.errors()
            raise HTTPException(status_code=400, detail=f"파라미터 유효성 검사 실패: {error_details}")

    # 7. 의존성 처리 메서드 오버라이드 (필요한 경우)
    def _process_dependencies(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """의존성 결과 처리 (이 예제에서는 기본 동작 사용)"""
        depends_results = super()._process_dependencies(context)
        logger.info(f"({self.agent_id}) 수신된 의존성 결과 수: {len(depends_results)}")
        # 필요시 의존성 결과 가공 로직 추가
        return depends_results

    # 8. 핵심 태스크 처리 로직 구현
    async def process_task(
        self,
        task_id: str,
        params: ExampleAgentParams, # 유효성 검사된 Pydantic 모델 사용
        dependencies: List[Dict[str, Any]],
        raw_task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        텍스트를 대문자로 변환하는 핵심 로직
        """
        logger.info(f"({self.agent_id}) 태스크 처리 시작: {task_id}")
        logger.debug(f"처리 파라미터 ({task_id}): {params.dict()}")

        # 파라미터에서 값 추출
        text_to_transform = params.text_input
        add_prefix = params.add_prefix

        # 핵심 로직 수행: 대문자 변환
        transformed_text = text_to_transform.upper()

        # 접두사 추가 (선택 사항)
        if add_prefix:
            final_output = f"Transformed: {transformed_text}"
        else:
            final_output = transformed_text

        # 의존성 결과 활용 예시 (여기서는 단순히 로깅)
        if dependencies:
            logger.info(f"({task_id}) 처리 중 참고한 의존성 결과 수: {len(dependencies)}")
            # 예: 첫 번째 의존성 결과의 메시지를 로깅
            # first_dep_result = dependencies[0].get('result', {}).get('message', 'N/A')
            # logger.debug(f"첫 번째 의존성 메시지: {first_dep_result}")

        # 결과 반환
        result = {
            "original_text": text_to_transform,
            "transformed_text": final_output,
            "prefix_added": add_prefix,
            "message": f"텍스트가 성공적으로 변환되었습니다 (Task ID: {task_id})."
        }

        logger.info(f"({self.agent_id}) 태스크 처리 완료: {task_id}")
        return result

# 9. 에이전트 인스턴스 생성
agent = ExampleAgent(app)

# --- FastAPI 이벤트 핸들러 ---
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행되는 이벤트 핸들러"""
    logger.info(f"Example Agent 시작 중: {agent.agent_id}")
    try:
        # 레지스트리에 에이전트 등록
        await agent.register()
        logger.info(f"레지스트리 등록 완료: {agent.agent_id}")
        
        # 하트비트 활성화된 경우, 하트비트 시작
        if agent.enable_heartbeat:
            await agent._start_heartbeat()
            logger.info(f"하트비트 시작됨 (간격: {agent.heartbeat_interval}초)")
    except Exception as e:
        logger.error(f"에이전트 시작 중 오류: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 실행되는 이벤트 핸들러"""
    logger.info(f"Example Agent 종료 중: {agent.agent_id}")
    try:
        # 레지스트리에서 에이전트 등록 해제
        await agent.unregister()
        logger.info(f"레지스트리 등록 해제 완료: {agent.agent_id}")
        
        # HTTP 클라이언트 종료
        if agent.http_client:
            await agent.http_client.aclose()
            logger.info("HTTP 클라이언트 종료됨")
    except Exception as e:
        logger.error(f"에이전트 종료 중 오류: {str(e)}")

# 기본 상태 확인 엔드포인트 추가
@app.get("/health")
async def health_check():
    """에이전트 상태 확인 엔드포인트"""
    return {
        "status": "healthy",
        "agent_id": agent.agent_id,
        "role": agent.agent_role,
        "active_tasks": len(app.state.active_tasks) if hasattr(app.state, "active_tasks") else 0
    }

# 개발/테스트용 서버 실행
if __name__ == "__main__":
    import uvicorn
    logger.info("Example Agent 개발 모드로 서버 시작...")
    uvicorn.run(
        "main:app", # 현재 파일명:FastAPI 앱 인스턴스명
        host="0.0.0.0",
        port=8013, # 다른 에이전트와 겹치지 않는 포트 사용
        reload=True,
        log_level=LOG_LEVEL.lower()
    ) 