"""
오케스트레이터 메인 API 서비스
"""
import asyncio
import logging
import time
import uuid
import secrets
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from orchestrator.models import QueryRequest, QueryResponse
from orchestrator.llm_client import OrchestratorLLMClient
from .registry_client import RegistryClient
from .broker_client import BrokerClient
from .task_decomposer import TaskDecomposer
from .result_collector import ResultCollector
from .context_manager import ContextManager
from .config import REGISTRY_URL, BROKER_URL, REDIS_URL
from .websocket_manager import WebSocketManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Orchestrator API",
    description="사용자 요청을 분석하고 작업을 조율하는 API 서비스",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "syntaxHighlight": {"theme": "obsidian"},
        "deepLinking": True,
        "defaultModelsExpandDepth": 2,
        "displayRequestDuration": True,
        "filter": True,
    }
)

# 대화 상태 관리를 위한 클래스
class ConversationState:
    def __init__(self):
        self.user_id: str
        self.query: str
        self.tasks: List[Dict[str, Any]] = []
        self.completed_tasks: List[Dict[str, Any]] = []
        self.status: str = "pending"
        self.start_time: float
        self.update_time: float
        self.end_time: Optional[float] = None

# 앱 시작 이벤트
@app.on_event("startup")
async def startup_event():
    """앱 시작 시 클라이언트 초기화"""
    app.state.llm_client = OrchestratorLLMClient()
    app.state.registry_client = RegistryClient(REGISTRY_URL)
    app.state.broker_client = BrokerClient(BROKER_URL)
    app.state.websocket_manager = WebSocketManager()
    app.state.conversations = {}  # 대화 상태 저장소
    
    # 컨텍스트 매니저 초기화
    app.state.context_manager = ContextManager(redis_url=REDIS_URL)
    
    logger.info("오케스트레이터 서비스 시작")

# 쿼리 처리 엔드포인트
@app.post("/query")
async def process_query(request: QueryRequest):
    """
    사용자 쿼리 처리 엔드포인트
    """
    try:
        # 대화 ID 생성
        conversation_id = request.conversation_id or str(uuid.uuid4())
        user_id = request.user_id or "익명"
        
        logger.info(f"새 쿼리 접수: '{request.query}' (대화: {conversation_id}, 사용자: {user_id})")
        
        # 대화 상태 초기화
        conversation = ConversationState()
        conversation.user_id = user_id
        conversation.query = request.query
        conversation.status = "processing"
        conversation.start_time = time.time()
        conversation.update_time = time.time()
        app.state.conversations[conversation_id] = conversation
        
        # 태스크 분해
        task_decomposer = TaskDecomposer(app.state.registry_client, app.state.llm_client)
        tasks, execution_levels = await task_decomposer.decompose_query(
            query=request.query,
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        # 태스크 저장
        conversation.tasks = tasks
        
        # 결과 수집
        result_collector = ResultCollector(app.state.broker_client, app.state.llm_client)
        result_collector.current_conversation_id = conversation_id  # 대화 ID 설정
        
        # 태스크 간 의존성 추적을 위한 변수
        completed_task_ids = {}  # 역할별 완료된 태스크 ID 저장
        
        # 각 실행 레벨별로 태스크 처리
        final_results = []
        for level, level_task_indices in enumerate(execution_levels, 1):
            logger.info(f"실행 레벨 {level} 처리 중 ({len(level_task_indices)}개 태스크)")
            level_results = []

            for task_idx in level_task_indices:
                task = tasks[task_idx]  # 태스크 인덱스로 실제 태스크 객체 가져오기
                role = task.get("role")
                description = task.get("description")
                logger.info(f"태스크 실행: '{description}' (역할: {role})")
                
                # 태스크에 대화 ID 추가
                task["conversation_id"] = conversation_id
                
                # 의존성 태스크 결과 추가
                if level > 1:
                    # 이전 레벨의 결과를 현재 태스크에 전달
                    prev_results = result_collector.get_all_results()
                    logger.info(f"이전 레벨 태스크 결과 {len(prev_results)}개를 현재 태스크에 전달")
                    logger.debug(f"이전 결과 상세: {prev_results}")
                    
                    # 태스크에 의존성 정보 추가
                    for task_idx in level_task_indices:
                        # 태스크 인덱스로 실제 태스크 객체에 접근
                        task = tasks[task_idx]
                        # 의존성 설정
                        task["depends_on"] = []
                        
                        # 이전 결과의 task_id 추출
                        for prev_result in prev_results:
                            task_id = prev_result.get("task_id")
                            if task_id and isinstance(task_id, str) and task_id.startswith("task_"):
                                logger.info(f"의존성 추가: {task_id} ({prev_result.get('role', 'unknown')})")
                                task["depends_on"].append(task_id)
                
                # 태스크 실행 및 결과 수집
                result = await result_collector.process_task(task)
                level_results.append(result)
                
                # 태스크 결과 및 상태 로깅
                status = result.get("status", "unknown")
                logger.info(f"태스크 '{description}' 완료: {status}")
            
            final_results.extend(level_results)
            
            # WebSocket으로 진행 상황 업데이트
            progress_update = {
                "type": "progress",
                "level": level,
                "total_levels": len(execution_levels),
                "completed_tasks": len(final_results),
                "total_tasks": len(tasks)
            }
            await app.state.websocket_manager.broadcast(conversation_id, progress_update)
        
        # 통합 결과 생성
        final_response = await result_collector.integrate_results(
            request.query, final_results, conversation_id
        )
        
        # 대화 상태 업데이트
        conversation.status = "completed"
        conversation.end_time = time.time()
        conversation.update_time = time.time()
        conversation.completed_tasks = final_results
        
        logger.info(f"대화 처리 완료: {conversation_id}")
        
        # WebSocket으로 완료 상태 전송
        completion_update = {
            "type": "completion",
            "conversation_id": conversation_id,
            "message": final_response.get("message", ""),
            "tasks_count": len(final_results)
        }
        await app.state.websocket_manager.broadcast(conversation_id, completion_update)

        # 최종 대화 상태를 Redis에 저장
        try:
            # 저장할 최종 응답 데이터 구성
            final_conversation_data = {
                "conversation_id": conversation_id,
                "status": "completed",
                "query": request.query,
                "user_id": user_id,
                "start_time": conversation.start_time,
                "end_time": time.time(),
                "result": final_response, # 최종 통합 결과
                "tasks": [
                    {
                        "id": task_id,
                        "status": "completed", 
                        "description": task.get("description", "")
                    } 
                    for task_id, task in zip(conversation.completed_tasks, tasks) 
                    if task_id is not None
                ]
            }
            await app.state.context_manager.save_response(conversation_id, final_conversation_data)
            logger.info(f"대화 ID {conversation_id}의 최종 상태를 Redis에 저장했습니다.")
        except Exception as e:
            logger.error(f"Redis에 대화 상태 저장 중 오류 발생: {str(e)}")

        return final_response

    except Exception as e:
        logger.exception(f"쿼리 처리 중 오류: {str(e)}")
        # 오류 발생 시에도 상태 업데이트 시도 (선택 사항)
        if 'conversation_id' in locals() and conversation_id in app.state.conversations:
             app.state.conversations[conversation_id].status = "failed"
             app.state.conversations[conversation_id].update_time = time.time()
             # 실패 상태도 저장할 수 있음 (필요시)
             # await app.state.context_manager.save_response(conversation_id, {"status": "failed", "error": str(e)})

        # HTTP 응답 반환
        raise HTTPException(
            status_code=500,
            detail=f"쿼리 처리 중 오류 발생: {str(e)}"
        )

@app.get("/conversation/{conversation_id}", tags=["conversation"])
async def get_conversation(conversation_id: str):
    """
    특정 대화 ID에 대한 통합 결과 조회
    
    Args:
        conversation_id: 대화 ID
        
    Returns:
        통합된 결과 및 상태 정보
    """
    try:
        # 컨텍스트 매니저에서 대화 정보 조회
        if app.state.context_manager:
            conversation_data = await app.state.context_manager.get_conversation(conversation_id)
            if not conversation_data:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": f"대화 ID {conversation_id}를 찾을 수 없습니다."}
                )
                
            # 태스크 상태 포함
            tasks = []
            for task_id in conversation_data.get("tasks", []):
                task_info = await app.state.broker_client.get_task(task_id)
                if task_info:
                    tasks.append({
                        "id": task_id,
                        "status": task_info.get("status", "unknown"),
                        "description": task_info.get("description", "")
                    })
            
            # 응답 구성
            response = {
                "conversation_id": conversation_id,
                "status": conversation_data.get("status", "unknown"),
                "message": conversation_data.get("result", {}).get("message", ""),
                "tasks": tasks
            }
            
            return JSONResponse(content=response)
        else:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "컨텍스트 매니저가 초기화되지 않았습니다."}
            )
    except Exception as e:
        logger.error(f"대화 조회 중 오류: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"대화 조회 중 오류: {str(e)}"}
        )

@app.get("/conversations", tags=["conversation"])
async def list_conversations():
    """
    모든 대화 목록 조회
    
    Returns:
        대화 ID 및 기본 정보 목록
    """
    try:
        if app.state.context_manager:
            conversations = await app.state.context_manager.list_conversations()
            return JSONResponse(content={"conversations": conversations})
        else:
            return JSONResponse(
                status_code=500, 
                content={"status": "error", "message": "컨텍스트 매니저가 초기화되지 않았습니다."}
            )
    except Exception as e:
        logger.error(f"대화 목록 조회 중 오류: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"대화 목록 조회 중 오류: {str(e)}"}
        )

@app.get("/conversations/{conversation_id}/detail", tags=["conversation"])
async def get_conversation_detail(conversation_id: str):
    """
    대화 상세 정보 조회
    """
    try:
        # 컨텍스트 매니저가 초기화되어 있는지 확인
        if hasattr(app.state, "context_manager"):
            # Redis에서 대화 데이터 가져오기
            conversation_data = await app.state.context_manager.get_conversation(conversation_id)
            
            if not conversation_data:
                raise HTTPException(status_code=404, detail=f"대화 ID {conversation_id}를 찾을 수 없습니다.")
            
            # 태스크 상태 포함 - BrokerClient.get_task_status 사용
            tasks = []
            for task_id in conversation_data.get("tasks", []):
                try:
                    # get_task 대신 get_task_status 메서드 사용 (또는 BrokerClient에 존재하는 적절한 메서드)
                    task_info = await app.state.broker_client.get_task_status(task_id)
                    if task_info:
                        tasks.append({
                            "id": task_id,
                            "status": task_info.get("status", "unknown"),
                            "description": task_info.get("description", "")
                        })
                except Exception as task_err:
                    logger.error(f"태스크 정보 조회 중 오류 (ID: {task_id}): {str(task_err)}")
                    # 태스크 정보를 가져오지 못하더라도 기본 정보 추가
                    tasks.append({
                        "id": task_id,
                        "status": "unknown",
                        "description": "태스크 정보를 가져올 수 없습니다."
                    })
            
            # 응답 구성
            response = {
                "conversation_id": conversation_id,
                "status": conversation_data.get("status", "unknown"),
                "message": conversation_data.get("result", {}).get("message", ""),
                "tasks": tasks,
                "created_at": conversation_data.get("start_time"),
                "completed_at": conversation_data.get("end_time")
            }
            
            return JSONResponse(content=response)
        else:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "컨텍스트 매니저가 초기화되지 않았습니다."}
            )
    except Exception as e:
        logger.error(f"대화 상세 조회 중 오류: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"대화 상세 조회 중 오류: {str(e)}"}
        )

@app.get("/health")
async def health():
    """
    서비스 상태 확인
    """
    try:
        # 레지스트리 및 브로커 상태 확인
        registry_health = await app.state.registry_client.check_health()
        broker_health = await app.state.broker_client.check_health()
        
        return {
            "status": "healthy",
            "registry": registry_health,
            "broker": broker_health,
            "conversations": len(app.state.conversations),
            "active_conversations": sum(1 for c in app.state.conversations.values() if c.status == "processing")
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# WebSocket 엔드포인트 추가
@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """
    WebSocket 연결 처리
    """
    await app.state.websocket_manager.connect(websocket, conversation_id)
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            # 여기서는 수신된 메시지를 무시하고, 상태 업데이트만 전송
    except WebSocketDisconnect:
        app.state.websocket_manager.disconnect(websocket, conversation_id)

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    대화 상태 조회
    """
    try:
        conversation = await app.state.context_manager.get_conversation(conversation_id)
        if not conversation:
            # ContextManager에서 None을 반환하면 404 발생
            raise HTTPException(status_code=404, detail=f"대화 ID {conversation_id}를 찾을 수 없습니다.")

        return conversation
    except HTTPException as http_exc:
        # 이미 HTTPException이면 그대로 다시 발생시킴 (404 유지)
        raise http_exc
    except Exception as e:
        logger.error(f"대화 상태 조회 중 오류: {str(e)}")
        # 그 외 예외는 500 오류로 처리
        raise HTTPException(status_code=500, detail=f"대화 상태 조회 중 서버 오류 발생: {str(e)}")

# 서버 실행 (직접 실행 시)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
