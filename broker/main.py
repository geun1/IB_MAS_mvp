import asyncio
import os
import logging
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
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# API 모델
class TaskRequest(BaseModel):
    role: str
    params: Dict[str, Any]
    conversation_id: str

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    result: Optional[Dict[str, Any]] = None

# FastAPI 앱 설정
app = FastAPI(
    title="Broker API",
    description="에이전트 선택 및 작업 라우팅을 담당하는 API 서비스",
    version="1.0.0",
    root_path=""
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
    
    # 큐 매니저 설정
    app.state.queue_manager = QueueManager(RABBITMQ_URL)
    await app.state.queue_manager.connect()

# API 엔드포인트
@app.post("/tasks", response_model=TaskResponse)
async def process_task(task: TaskRequest, background_tasks: BackgroundTasks):
    try:
        # 태스크 ID 생성
        task_id = f"task_{task.role}_{task.conversation_id}_{hash(str(task.params))}"
        
        # 태스크 생성 및 저장
        await app.state.task_store.create_task(task_id, task.role, task.params)
        
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
        
        # 1. 적절한 에이전트 선택
        agent = await app.state.task_router.select_agent(task.role)
        if not agent:
            logging.error(f"역할 '{task.role}'에 맞는 에이전트를 찾을 수 없습니다.")
            await app.state.task_store.update_task_status(
                task_id, 
                TaskStatus.FAILED, 
                error=f"역할 '{task.role}'에 맞는 에이전트를 찾을 수 없습니다."
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
        
        # 3. 에이전트 호출
        result = await app.state.agent_client.execute_task(
            agent.endpoint, 
            {"params": enhanced_params, "task_id": task_id}
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
@app.post("/test/infer-params")
async def test_infer_params(
    request: Dict[str, Any]
):
    """파라미터 추론 테스트 API"""
    try:
        # 필수 필드 검증
        if "task_description" not in request:
            raise HTTPException(status_code=400, detail="태스크 설명(task_description)이 필요합니다")
        if "param_schemas" not in request:
            raise HTTPException(status_code=400, detail="파라미터 스키마(param_schemas)가 필요합니다")
            
        task_description = request["task_description"]
        param_schemas = [AgentParam(**schema) for schema in request["param_schemas"]]
        existing_params = request.get("existing_params", {})
        
        # 전체 파라미터 스키마 중 필수이지만 전달되지 않은 파라미터 선별
        missing_params = []
        for schema in param_schemas:
            if schema.required and schema.name not in existing_params:
                missing_params.append(schema)
        
        # 추론 결과
        result = {}
        
        if missing_params:
            # LLM으로 파라미터 추론
            inferred_params = await app.state.llm_client.infer_missing_params(
                task_description,
                [p.dict() for p in missing_params],
                existing_params
            )
            
            # 추론된 파라미터 검증
            for schema in missing_params:
                if schema.name in inferred_params:
                    # 단일 파라미터에 대한 검증을 위한 임시 딕셔너리
                    temp = {schema.name: inferred_params[schema.name]}
                    validated = app.state.param_processor.validate_params(temp, [schema])
                    result[schema.name] = validated[schema.name]
        
        return {
            "task_description": task_description,
            "existing_params": existing_params,
            "missing_params": [p.dict() for p in missing_params],
            "inferred_params": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
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

# 서비스 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
