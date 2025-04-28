import asyncio
import os
import logging
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from broker.registry_client import RegistryClient
from broker.task_router import TaskRouter
from broker.param_processor import ParamProcessor
from broker.agent_client import AgentClient
from broker.llm_client import BrokerLLMClient
from broker.queue_manager import QueueManager
from broker.registry_client import AgentParam
from broker.models import TaskStatus, TaskResult, TaskList
from broker.task_store import TaskStore

# 환경 변수 로드
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# API 모델
class TaskRequest(BaseModel):
    role: str
    params: Dict[str, Any]
    conversation_id: str
    agent_configs: Optional[Dict[str, Any]] = None
    exclude_agent: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    result: Optional[Dict[str, Any]] = None

class ExecuteTaskRequest(BaseModel):
    """태스크 직접 실행 요청 모델 (ReACT 에이전트용)"""
    task_id: str  # 태스크 식별자
    role: str     # 필요한 에이전트 역할
    params: Dict[str, Any]  # 태스크 파라미터
    exclude_agent: Optional[str] = None  # 제외할 에이전트 ID (보통 ReACT 에이전트 자신)

# FastAPI 앱 설정
app = FastAPI(
    title="Broker API",
    description="에이전트 선택 및 작업 라우팅을 담당하는 API 서비스",
    version="1.0.0",
    root_path=""
)

# 로깅 설정 강화
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 서비스 초기화
@app.on_event("startup")
async def startup_event():
    app.state.registry_client = RegistryClient(REGISTRY_URL)
    app.state.task_router = TaskRouter(app.state.registry_client)
    app.state.llm_client = BrokerLLMClient()
    app.state.param_processor = ParamProcessor(app.state.llm_client)
    app.state.agent_client = AgentClient()
    
    # 태스크 스토어 초기화
    app.state.task_store = TaskStore(REDIS_URL)
    
    # RabbitMQ URL 구성 확인 (로깅)
    rabbitmq_url = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
    logging.info(f"RabbitMQ 연결 URL: {rabbitmq_url}")
    
    # 큐 매니저 설정 - 로깅 강화
    app.state.queue_manager = QueueManager(rabbitmq_url)
    
    # 비동기 태스크로 RabbitMQ 연결 시도 (앱 시작을 블록하지 않음)
    asyncio.create_task(connect_rabbitmq(app.state.queue_manager))

# RabbitMQ 연결을 위한 별도 함수 추가
async def connect_rabbitmq(queue_manager):
    try:
        # RabbitMQ가 준비될 때까지 시간 제공
        logging.info("RabbitMQ 서비스가 준비될 때까지 15초 대기...")
        await asyncio.sleep(15)
        
        # 연결 시도
        await queue_manager.connect()
    except Exception as e:
        logging.error(f"RabbitMQ 연결 초기화 중 오류: {str(e)}")
        logging.warning("RabbitMQ 없이 제한된 기능으로 실행됩니다")

# API 엔드포인트
@app.post("/tasks", response_model=TaskResponse)
async def process_task(task: TaskRequest, background_tasks: BackgroundTasks):
    try:
        # 태스크 ID 생성
        task_id = f"task_{task.role}_{task.conversation_id}_{hash(str(task.params))}"
        
        # 태스크 생성 및 저장
        await app.state.task_store.create_task(
            task_id, 
            task.role, 
            task.params, 
            agent_configs=task.agent_configs,
            exclude_agent=task.exclude_agent
        )
        
        # 백그라운드에서 태스크 처리
        background_tasks.add_task(_execute_task, task, task_id)
        
        return {
            "task_id": task_id,
            "status": "accepted",
            "message": f"태스크가 {task.role} 역할의 에이전트로 전송 중입니다."
        }
    except Exception as e:
        logging.error(f"태스크 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"태스크 처리 오류: {str(e)}")

# 내부 태스크 처리 함수
async def _execute_task(task: TaskRequest, task_id: str):
    try:
        # 태스크 상태를 처리 중으로 업데이트
        await app.state.task_store.update_task_status(task_id, TaskStatus.PROCESSING)
        
        # 1. 적절한 에이전트 선택 (제외할 에이전트 ID 전달)
        agent = await app.state.task_router.select_agent(task.role, task.exclude_agent)
        if not agent:
            error_message = f"역할 '{task.role}'에 맞는 에이전트를 찾을 수 없습니다."
            if task.exclude_agent:
                error_message += f" (에이전트 '{task.exclude_agent}' 제외)"
            
            logging.error(error_message)
            await app.state.task_store.update_task_status(
                task_id, 
                TaskStatus.FAILED, 
                error=error_message
            )
            return
        
        # 에이전트 ID 기록
        await app.state.task_store.update_task_status(
            task_id, 
            TaskStatus.PROCESSING, 
            agent_id=agent.id
        )
        
        # 2. 파라미터 검증 및 보완
        param_schemas = agent.params
        
        # 기본 파라미터 검증
        validated_params = app.state.param_processor.validate_params(
            task.params, param_schemas
        )
        
        # 부족한 파라미터 LLM으로 추론하여 보완
        if any(schema.required and schema.name not in validated_params for schema in param_schemas):
            enhanced_params = await app.state.param_processor.fill_missing_params(
                validated_params, param_schemas, f"Task for {task.role}: {agent.description}"
            )
        else:
            enhanced_params = validated_params
        
        # 요청 데이터 구성
        request_data = {
            "params": enhanced_params,
            "task_id": task_id
        }
        
        # agent_configs가 있으면 요청에 추가
        if hasattr(task, 'agent_configs') and task.agent_configs:
            request_data["agent_configs"] = task.agent_configs
            logging.info(f"에이전트 설정 포함: {task.agent_configs}")
        
        # 3. 에이전트 호출
        result = await app.state.agent_client.execute_task(
            agent.endpoint, 
            request_data
        )
        
        # 4. 결과 처리
        if result:
            logging.info(f"태스크 {task_id} 완료: {result}")
            task = await app.state.task_store.update_task_status(
                task_id, 
                TaskStatus.COMPLETED, 
                result=result
            )
            
            # 에이전트 통계 업데이트
            if agent.id and task and task.execution_time:
                await app.state.registry_client.update_agent_task_stats(
                    agent.id, "completed", task.execution_time
                )
        else:
            logging.error(f"태스크 {task_id} 실패")
            task = await app.state.task_store.update_task_status(
                task_id, 
                TaskStatus.FAILED, 
                error="에이전트 응답 없음"
            )
            
            # 에이전트 통계 업데이트
            if agent.id:
                await app.state.registry_client.update_agent_task_stats(
                    agent.id, "failed"
                )
            
    except Exception as e:
        logging.error(f"태스크 실행 오류: {str(e)}")
        await app.state.task_store.update_task_status(
            task_id, 
            TaskStatus.FAILED, 
            error=str(e)
        )

# 건강 체크 API 엔드포인트 추가
@app.get("/health")
async def health_check():
    """서비스 상태 확인"""
    try:
        # 레지스트리 상태 확인
        registry_status = {"status": "unknown"}
        try:
            registry_status = await app.state.registry_client.check_health()
        except Exception as e:
            registry_status = {"detail": f"Registry 서비스 오류: {str(e)}"}
        
        return {
            "status": "healthy",
            "registry": registry_status
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "detail": str(e)
        }

# 파라미터 추론 테스트용 API
@app.post("/test/infer-params", tags=["테스트"])
async def test_infer_params(request: dict):
    """파라미터 추론 테스트 엔드포인트"""
    try:
        logging.info(f"파라미터 추론 테스트 요청 수신: {request}")
        
        task_description = request.get("task_description")
        param_schemas = request.get("param_schemas", [])
        existing_params = request.get("existing_params", {})
        
        # 쉼표로 구분된 AgentParam 객체 리스트로 변환
        agent_params = [AgentParam(**schema) for schema in param_schemas]
        
        # ParamProcessor를 사용해 추론 실행 - 메서드 이름 수정
        logging.info("파라미터 추론 시작...")
        inferred_params = await app.state.param_processor.fill_missing_params(
            agent_params, existing_params
        )
        logging.info(f"추론 완료: {inferred_params}")
        
        return {
            "inferred_params": inferred_params,
            "original_params": existing_params
        }
    except Exception as e:
        logging.error(f"파라미터 추론 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"파라미터 추론 오류: {str(e)}")

# 태스크 조회 API
@app.get("/tasks/{task_id}", response_model=TaskResult)
async def get_task(task_id: str):
    """특정 태스크 상태 및 결과 조회"""
    task = await app.state.task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다")
    return task

# 태스크 목록 조회 API
@app.get("/tasks", response_model=TaskList)
async def list_tasks(
    status: Optional[str] = None,
    role: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """태스크 목록 조회"""
    tasks, total = await app.state.task_store.list_tasks(
        status=status, 
        role=role, 
        page=page, 
        page_size=page_size
    )
    
    return {
        "tasks": tasks,
        "total": total,
        "page": page,
        "page_size": page_size
    }

# 태스크 상태 변경 API
@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """태스크 취소"""
    task = await app.state.task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다")
        
    # 대기 중이거나 처리 중인 태스크만 취소 가능
    if task.status not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        raise HTTPException(status_code=400, detail=f"현재 상태({task.status})에서는 취소할 수 없습니다")
        
    # 태스크 상태 업데이트
    await app.state.task_store.update_task_status(
        task_id, 
        TaskStatus.CANCELLED, 
        error="사용자에 의해 취소됨"
    )
    
    return {"status": "success", "message": "태스크가 취소되었습니다"}

# 파라미터 추론 테스트용 API
@app.post("/test/infer-simple", tags=["테스트"])
async def test_infer_simple(request: dict):
    """간소화된 파라미터 추론 테스트 엔드포인트"""
    try:
        task_description = request.get("task_description", "")
        param_schemas = request.get("param_schemas", [])
        existing_params = request.get("existing_params", {})
        
        # 간단한 응답 생성 (실제 추론 없이)
        inferred = {}
        for schema in param_schemas:
            name = schema.get("name", "")
            if name and name not in existing_params and schema.get("required", False):
                if name == "tone":
                    inferred[name] = "formal"  # 기본값 설정
                elif name == "length":
                    inferred[name] = 500  # 기본값 설정
        
        return {
            "inferred_params": inferred,
            "original_params": existing_params
        }
    except Exception as e:
        logging.error(f"테스트 추론 중 오류: {str(e)}")
        return {
            "inferred_params": {},
            "original_params": existing_params,
            "error": str(e)
        }

# 대화 ID로 관련 태스크 조회 API
@app.get("/tasks/by-conversation/{conversation_id}")
async def get_tasks_by_conversation(
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """대화 ID로 관련 태스크 조회"""
    try:
        # 특정 대화 ID에 해당하는 태스크 조회
        tasks, total = await app.state.task_store.get_tasks_by_conversation(
            conversation_id, page, page_size
        )
        
        return {
            "tasks": tasks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "conversation_id": conversation_id
        }
    except Exception as e:
        logging.error(f"대화 ID로 태스크 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 서비스 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.post("/execute_task", response_model=Dict[str, Any])
async def execute_task(task: ExecuteTaskRequest):
    """
    ReACT 에이전트가 직접 호출하는 태스크 실행 엔드포인트
    다른 에이전트에게 태스크를 위임하고 결과를 반환합니다.
    """
    try:
        logging.info(f"다이렉트 태스크 실행 요청: {task.role} (task_id: {task.task_id})")
        
        # 1. 적절한 에이전트 선택 (제외할 에이전트 ID 전달)
        agent = await app.state.task_router.select_agent(task.role, task.exclude_agent)
        if not agent:
            error_message = f"역할 '{task.role}'에 맞는 에이전트를 찾을 수 없습니다."
            if task.exclude_agent:
                error_message += f" (에이전트 '{task.exclude_agent}' 제외)"
            
            logging.error(error_message)
            return {
                "success": False,
                "error": error_message
            }
        
        logging.info(f"에이전트 선택됨: {agent.id} (역할: {agent.role})")
        
        # 2. 파라미터 검증 및 보완
        param_schemas = agent.params
        
        # 기본 파라미터 검증
        validated_params = app.state.param_processor.validate_params(
            task.params, param_schemas
        )
        
        # 부족한 파라미터 LLM으로 추론하여 보완
        if any(schema.required and schema.name not in validated_params for schema in param_schemas):
            enhanced_params = await app.state.param_processor.fill_missing_params(
                validated_params, param_schemas, f"Task for {task.role}: {agent.description}"
            )
        else:
            enhanced_params = validated_params
        
        # 요청 데이터 구성
        request_data = {
            "params": enhanced_params,
            "task_id": task.task_id
        }
        
        logging.info(f"에이전트 호출: {agent.endpoint}")
        
        # 3. 에이전트 호출
        start_time = time.time()
        result = await app.state.agent_client.execute_task(
            agent.endpoint, 
            request_data
        )
        execution_time = time.time() - start_time
        
        # 4. 결과 처리
        if result:
            logging.info(f"태스크 {task.task_id} 완료: 실행 시간 {execution_time:.2f}초")
            
            # 에이전트 통계 업데이트
            await app.state.registry_client.update_agent_task_stats(
                agent.id, "completed", execution_time
            )
            
            return {
                "success": True,
                "task_id": task.task_id,
                "result": result,
                "execution_time": execution_time,
                "agent_id": agent.id
            }
        else:
            logging.error(f"태스크 {task.task_id} 실패")
            
            # 에이전트 통계 업데이트
            await app.state.registry_client.update_agent_task_stats(
                agent.id, "failed"
            )
            
            return {
                "success": False,
                "error": "에이전트 응답 없음",
                "task_id": task.task_id
            }
            
    except Exception as e:
        logging.error(f"다이렉트 태스크 실행 오류: {str(e)}")
        return {
            "success": False,
            "error": f"태스크 실행 오류: {str(e)}",
            "task_id": task.task_id
        }
