"""
오케스트레이터 메인 API 서비스
"""
import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from orchestrator.models import QueryRequest, QueryResponse
from orchestrator.llm_client import OrchestratorLLMClient
from .registry_client import RegistryClient
from .broker_client import BrokerClient
from .task_decomposer import TaskDecomposer
from .result_collector import ResultCollector
from .config import REGISTRY_URL, BROKER_URL
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

# 앱 시작 이벤트
@app.on_event("startup")
async def startup_event():
    """앱 시작 시 클라이언트 초기화"""
    app.state.llm_client = OrchestratorLLMClient()
    app.state.registry_client = RegistryClient(REGISTRY_URL)
    app.state.broker_client = BrokerClient(BROKER_URL)
    
    # 태스크 분해기 및 결과 수집기 초기화
    app.state.task_decomposer = TaskDecomposer(
        app.state.llm_client, 
        app.state.registry_client
    )
    app.state.result_collector = ResultCollector(
        app.state.broker_client,
        app.state.llm_client
    )
    
    # 진행 중인 대화 및 태스크 저장소
    app.state.conversations = {}
    app.state.tasks_results = {}
    
    app.state.websocket_manager = WebSocketManager()
    
    logger.info("오케스트레이터 서비스 시작 완료")

# 진행 중인 대화 상태 관리
class ConversationState:
    """대화 상태 관리 클래스"""
    def __init__(self, conversation_id: str, user_id: Optional[str] = None):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.tasks = []
        self.results = {}
        self.status = "pending"
        self.start_time = time.time()
        self.update_time = time.time()
        
    def update(self, status: str, tasks: Optional[List[Dict[str, Any]]] = None):
        """상태 업데이트"""
        self.status = status
        if tasks:
            self.tasks = tasks
        self.update_time = time.time()
        
    def add_result(self, task_id: str, result: Dict[str, Any]):
        """태스크 결과 추가"""
        self.results[task_id] = result
        self.update_time = time.time()
        
    def is_complete(self) -> bool:
        """모든 태스크가 완료되었는지 확인"""
        if not self.tasks:
            return False
        return all(task_id in self.results for task_id in self.tasks)

# 비동기 태스크 처리 함수
async def process_query_tasks(
    app,  # app 객체 직접 받음
    conversation_id: str,
    tasks: List[Dict[str, Any]],  # tasks만 받음
    decomposition_result: Dict[str, Any]  # 전체 결과 받음
):
    """
    백그라운드에서 태스크 실행 및 결과 수집
    """
    try:
        # 대화 객체 가져오기
        if conversation_id not in app.state.conversations:
            logger.error(f"대화를 찾을 수 없음: {conversation_id}")
            return
            
        conversation = app.state.conversations[conversation_id]
        
        # Task 객체로 변환 (dict에서 Task 모델로)
        task_objects = []
        for task_dict in tasks:
            # Task 모델로 변환 (depends_on이 없으면 빈 리스트 기본값 사용)
            if "depends_on" not in task_dict:
                task_dict["depends_on"] = []
            task_objects.append(task_dict)
        
        # 결과 수집기에 태스크 처리 요청
        original_query = decomposition_result.get("original_query", "")
        if not original_query:  # original_query가 없으면 request.query 사용
            original_query = conversation.query if hasattr(conversation, "query") else ""
        
        results = await app.state.result_collector.process_tasks(task_objects)
        
        # 통합된 결과 생성
        final_result = await app.state.result_collector.integrate_results(original_query, results)
        
        # 결과 저장
        app.state.tasks_results[conversation_id] = {
            "results": results,
            "final_result": final_result
        }
        
        # 대화 상태 업데이트
        conversation.status = "completed"
        conversation.update_time = time.time()
        
        # WebSocket을 통해 클라이언트에 알림
        if hasattr(app.state, "websocket_manager"):
            await app.state.websocket_manager.broadcast(
                conversation_id,
                {
                    "type": "completion",
                    "conversation_id": conversation_id,
                    "final_result": final_result
                }
            )
            
        logger.info(f"대화 처리 완료: {conversation_id}")
        
    except Exception as e:
        logger.error(f"태스크 처리 및 결과 수집 중 오류: {str(e)}")
        
        # 대화 상태를 실패로 업데이트
        if conversation_id in app.state.conversations:
            app.state.conversations[conversation_id].status = "failed"
            app.state.conversations[conversation_id].update_time = time.time()

# API 엔드포인트
@app.post("/query")
async def process_query(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    사용자 쿼리 처리
    """
    try:
        # 태스크 분해
        decomposition_result = await app.state.task_decomposer.decompose_query(
            request.query,
            request.user_id
        )
        
        # 대화 상태 초기화
        conversation_id = decomposition_result["conversation_id"]
        app.state.conversations[conversation_id] = ConversationState(
            conversation_id=conversation_id,
            user_id=request.user_id
        )
        
        # 백그라운드에서 태스크 처리
        background_tasks.add_task(
            process_query_tasks,
            app,  # app 객체 전달 (self 참조 오류 방지)
            conversation_id,
            decomposition_result["tasks"],  # tasks 배열만 전달
            decomposition_result  # 전체 decomposition_result 전달
        )
        
        return {
            "conversation_id": conversation_id,
            "status": "processing",
            "message": "쿼리 처리가 시작되었습니다."
        }
        
    except Exception as e:
        logger.error(f"쿼리 처리 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversation/{conversation_id}")
async def get_conversation_status(conversation_id: str):
    """
    대화 처리 상태 조회
    """
    if conversation_id not in app.state.conversations:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    
    conversation = app.state.conversations[conversation_id]
    tasks_results = app.state.tasks_results.get(conversation_id, {})
    
    # 응답 구성
    return {
        "conversation_id": conversation_id,
        "status": conversation.status,
        "tasks": conversation.tasks,
        "results": tasks_results.get("results", []),
        "start_time": conversation.start_time,
        "update_time": conversation.update_time
    }

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

# 서버 실행 (직접 실행 시)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
