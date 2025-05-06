"""
오케스트레이터 메인 API 서비스
"""
import asyncio
import logging
import time
import uuid
import secrets
import json
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
        self.task_descriptions: List[str] = []
        self.message_id: str

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
        # 대화 ID 확인 또는 생성
        conversation_id = request.conversation_id
        if not conversation_id:
            # 새 대화 생성
            conversation_id = await app.state.context_manager.create_conversation(request.user_id)
        
        # 메시지 ID 확인 또는 생성
        message_id = request.message_id
        if message_id:
            # 클라이언트가 제공한 메시지 ID 사용
            logger.info(f"클라이언트에서 제공한 메시지 ID 사용: {message_id}")
            # 해당 ID로 메시지 생성
            await app.state.context_manager.create_message_with_id(
                message_id=message_id,
                conversation_id=conversation_id,
                query=request.query,
                user_id=request.user_id
            )
        else:
            # 새 메시지 생성
            message_id = await app.state.context_manager.create_message(
                conversation_id=conversation_id,
                query=request.query,
                user_id=request.user_id
            )
        
        user_id = request.user_id or "익명"
        
        logger.info(f"새 쿼리 접수: '{request.query}' (대화: {conversation_id}, 메시지: {message_id}, 사용자: {user_id})")
        
        # 비활성화된 에이전트 목록 로깅
        if request.disabled_agents:
            logger.info(f"비활성화된 에이전트: {', '.join(request.disabled_agents)}")
        
        # 대화 상태 초기화
        conversation = ConversationState()
        conversation.user_id = user_id
        conversation.query = request.query
        conversation.status = "processing"
        conversation.start_time = time.time()
        conversation.update_time = time.time()
        conversation.message_id = message_id  # 메시지 ID 저장
        app.state.conversations[conversation_id] = conversation
        
        # 태스크 분해
        task_decomposer = TaskDecomposer(app.state.registry_client, app.state.llm_client)
        tasks, execution_levels, natural_language_tasks = await task_decomposer.decompose_query(
            query=request.query,
            conversation_id=conversation_id,
            user_id=user_id,
            disabled_agents=request.disabled_agents
        )
        
        # 태스크 저장
        conversation.tasks = tasks
        
        # 자연어 태스크 설명 저장 (JSON 형태로)
        conversation.task_descriptions = natural_language_tasks
        
        # 태스크 분해 결과를 즉시 Redis에 저장
        try:
            decomposition_data = {
                "conversation_id": conversation_id,
                "message_id": message_id,  # 메시지 ID 명시적 추가
                "query": request.query,
                "status": "decomposing",
                "task_descriptions": natural_language_tasks,
                "execution_levels": execution_levels,
                "created_at": conversation.start_time,
                "updated_at": time.time()
            }
            await app.state.context_manager.save_response(conversation_id, decomposition_data)
            
            # 메시지에도 태스크 분해 결과 저장 (이 부분이 중요)
            message = await app.state.context_manager.get_message(message_id)
            if message:
                message["task_descriptions"] = natural_language_tasks
                message["execution_levels"] = execution_levels
                message["status"] = "processing"
                message["updated_at"] = time.time()
                
                # 메시지 업데이트
                msg_key = f"message:{message_id}"
                app.state.context_manager.redis.set(msg_key, json.dumps(message))
                app.state.context_manager.redis.expire(msg_key, app.state.context_manager.ttl)
                
                logger.info(f"메시지 ID {message_id}에 태스크 분해 결과를 저장했습니다.")
            else:
                logger.warning(f"태스크 분해 결과를 저장할 메시지 {message_id}를 찾을 수 없습니다.")
            
            logger.info(f"대화 ID {conversation_id}의 태스크 분해 결과를 Redis에 저장했습니다.")
        except Exception as e:
            logger.error(f"태스크 분해 결과 저장 중 오류: {str(e)}")
        
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
                
                # 비활성화된 에이전트에 대한 태스크인 경우 건너뛰기
                if request.disabled_agents and role in request.disabled_agents:
                    logger.warning(f"비활성화된 에이전트 '{role}'에 대한 태스크를 건너뜁니다: '{description}'")
                    # skipped 상태로 결과 추가하고 다음 태스크로 넘어감
                    level_results.append({
                        "task_id": f"task_skipped_{task_idx}",
                        "role": role,
                        "status": "skipped",
                        "error": f"해당 에이전트는 비활성화 상태입니다.",
                        "description": description,
                        "created_at": time.time(),
                        "updated_at": time.time()
                    })
                    continue # 다음 task_idx로 이동
                
                # 여기부터는 활성화된 에이전트의 태스크만 처리
                logger.info(f"태스크 실행: '{description}' (역할: {role})")
                
                # 태스크에 대화 ID 추가
                task["conversation_id"] = conversation_id
                
                # 의존성 태스크 결과 추가 (이전 레벨 결과 주입)
                if level > 1:
                    # 이전 레벨의 완료된 결과만 필터링 (skipped 제외)
                    prev_results = [res for res in result_collector.get_all_results() if res.get("status") == "completed"]
                    
                    if prev_results:
                        logger.info(f"이전 레벨의 완료된 태스크 결과 {len(prev_results)}개를 현재 태스크에 전달")
                        logger.debug(f"이전 결과 상세: {prev_results}")
                        
                        # 태스크에 의존성 정보 추가
                        # 현재 태스크가 의존하는 이전 태스크의 ID 목록 생성 (구현 필요시)
                        # task["depends_on"] = [prev_res["task_id"] for prev_res in prev_results if ... ]
                        
                        # 결과를 params에 병합 (예시: context 필드)
                        if "params" not in task:
                            task["params"] = {}
                        task["params"]["previous_results"] = prev_results # 이전 결과를 params에 추가

                
                # UI에서 전달된 에이전트 설정이 있는지 확인 및 적용
                # request.agent_configs는 전체 설정일 수 있으므로, 현재 태스크 역할에 맞는 설정만 필터링 필요
                agent_specific_config = None
                if request.agent_configs and role in request.agent_configs:
                    agent_specific_config = request.agent_configs[role]
                    if agent_specific_config:
                        # 태스크 파라미터에 에이전트 설정 병합 (기존 값 덮어쓰기 가능)
                        if "params" not in task:
                             task["params"] = {}
                        task["params"].update(agent_specific_config) 
                        logger.info(f"에이전트 '{role}' 설정 포함: {agent_specific_config}")
                
                # 태스크 실행 및 결과 수집
                result = await result_collector.process_task(task)
                level_results.append(result)
                
                # 태스크 결과 및 상태 로깅
                status = result.get("status", "unknown")
                logger.info(f"태스크 '{description}' 완료: {status}")
                
                # 각 태스크 결과 즉시 DB에 저장
                try:
                    # 현재까지의 태스크 결과만 포함하는 임시 데이터 구성
                    current_tasks_data = {
                        "conversation_id": conversation_id,
                        "message_id": message_id,  # 메시지 ID 추가
                        "status": "processing",
                        "tasks": final_results + level_results,  # 이전 레벨 + 현재 레벨 결과 누적
                        "created_at": conversation.start_time,
                        "updated_at": time.time()
                    }
                    
                    # Redis에 태스크 결과 즉시 저장
                    await app.state.context_manager.save_response(conversation_id, current_tasks_data)
                    
                    # 메시지에도 태스크 결과 저장
                    message = await app.state.context_manager.get_message(message_id)
                    if message:
                        message["tasks"] = final_results + level_results
                        message["status"] = "processing"
                        message["updated_at"] = time.time()
                        
                        # 메시지 업데이트
                        msg_key = f"message:{message_id}"
                        app.state.context_manager.redis.set(msg_key, json.dumps(message))
                        app.state.context_manager.redis.expire(msg_key, app.state.context_manager.ttl)
                    
                    logger.info(f"대화 ID {conversation_id}, 메시지 ID {message_id}의 태스크 결과 업데이트됨: {role} - {status}")
                except Exception as e:
                    logger.error(f"태스크 결과 저장 중 오류: {str(e)}")
            
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
            final_data = {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "query": request.query,
                "status": "completed",
                "tasks": final_results,
                "message": final_response.get("message", ""),
                "created_at": conversation.start_time,
                "updated_at": time.time(),
                "task_descriptions": natural_language_tasks,  # 자연어 태스크 설명 추가
                "execution_levels": execution_levels  # 실행 레벨 정보 추가
            }
            
            # 메시지 업데이트
            await app.state.context_manager.update_message(message_id, final_data)
            
            # Redis에 저장 (기존 호환성 유지)
            await app.state.context_manager.save_response(conversation_id, final_data)
            logger.info(f"대화 ID {conversation_id}, 메시지 ID {message_id}의 최종 상태를 Redis에 저장했습니다.")
        except Exception as e:
            logger.error(f"대화 상태 저장 중 오류: {str(e)}")
            
        # 최종 응답 반환
        return {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "status": "success",
            "message": "대화가 성공적으로 처리되었습니다."
        }

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
async def get_conversation_status(conversation_id: str):
    """
    대화 상태 조회 API
    
    Args:
        conversation_id: 대화 ID
        
    Returns:
        대화 상태 및 결과
    """
    try:
        # 대화 상태를 DB에서 조회
        conversation = await app.state.context_manager.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
        
        # 태스크 결과 가져오기
        tasks = await app.state.context_manager.get_tasks_by_conversation(conversation_id)
        
        # 태스크 및 상태 가공
        task_info = []
        for task in tasks:
            # task에 'id' 키가 없는 경우 'task_id'를 사용하거나 기본값 사용
            task_id = task.get("id") or task.get("task_id") or "unknown"
            
            task_info.append({
                "id": task_id,
                "status": task.get("status", "unknown"),
                "result": task.get("result", None)
            })
        
        # 태스크 결과에서 통합된 마크다운 응답 생성
        message = ""
        if tasks and any(task.get("status") == "completed" for task in tasks):
            # 완료된 태스크 중 최종 결과를 마크다운으로 포맷팅
            completed_tasks = [task for task in tasks if task.get("status") == "completed"]
            
            # 결과 추출 및 마크다운 포맷팅
            message = await format_conversation_result(completed_tasks)
        
        return {
            "conversation_id": conversation_id,
            "status": conversation.get("status", "unknown"),
            "tasks": task_info,
            "message": message
        }
    except Exception as e:
        logger.error(f"대화 상태 조회 오류: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"대화 상태 조회 중 오류가 발생했습니다: {str(e)}")

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
        if hasattr(app.state, "context_manager") and app.state.context_manager:
            # Redis에서 대화 데이터 가져오기
            conversation_data = await app.state.context_manager.get_conversation(conversation_id)
            
            if not conversation_data:
                raise HTTPException(status_code=404, detail=f"대화 ID {conversation_id}를 찾을 수 없습니다.")
            
            # 태스크 상태 포함
            tasks = []
            task_list = conversation_data.get("tasks", [])

            # task_list가 리스트가 아닌 경우 빈 리스트로 처리
            if not isinstance(task_list, list):
                logger.warning(f"tasks가 리스트 형식이 아님: {type(task_list)}")
                task_list = []

            for task_item in task_list:
                try:
                    # task_item이 문자열이면 그대로 사용, 객체면 ID 추출
                    task_id = task_item
                    if isinstance(task_item, dict) and 'id' in task_item:
                        task_id = task_item['id']
                    
                    # 태스크 상태 조회
                    task_info = await app.state.broker_client.get_task_status(task_id)
                    if task_info:
                        tasks.append({
                            "id": task_id,
                            "status": task_info.get("status", "unknown"),
                            "description": task_info.get("description", "")
                        })
                except Exception as task_err:
                    logger.error(f"태스크 정보 조회 중 오류: {str(task_err)}")
                    # 태스크 정보를 가져오지 못하더라도 기본 정보 추가
                    tasks.append({
                        "id": str(task_item),
                        "status": "unknown",
                        "description": "태스크 정보를 가져올 수 없습니다."
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

async def format_conversation_result(completed_tasks):
    """
    완료된 태스크 결과를 마크다운 형식으로 포맷팅
    
    Args:
        completed_tasks: 완료된 태스크 목록
        
    Returns:
        마크다운 형식의 결과 문자열
    """
    if not completed_tasks:
        return ""
    
    # 최종 결과를 가진 태스크 찾기 (일반적으로 가장 마지막에 완료된 태스크)
    final_task = completed_tasks[-1]  # 가장 최근에 완료된 태스크
    
    result = final_task.get("result", {})
    logger.info(f"최종 태스크 결과 구조: {type(result).__name__}")
    if isinstance(result, dict):
        logger.info(f"결과 키: {list(result.keys())}")
        
        # 중첩된 result 객체인 경우 내부 키도 로깅
        if "result" in result and isinstance(result["result"], dict):
            logger.info(f"내부 result 키: {list(result['result'].keys())}")
            
            # content 키가 있는지 확인
            if "content" in result["result"]:
                logger.info("content 키 발견! 값 유형: " + type(result["result"]["content"]).__name__)
                # 값이 너무 길면 일부만 로깅
                content_preview = str(result["result"]["content"])[:100] + "..." if len(str(result["result"]["content"])) > 100 else str(result["result"]["content"])
                logger.info(f"content 미리보기: {content_preview}")
    
    # 결과 추출 로직
    message = ""
    
    # 직접 content 필드 확인 (가장 일반적인 케이스)
    if isinstance(result, dict) and "result" in result and isinstance(result["result"], dict):
        inner_result = result["result"]
        if "content" in inner_result:
            logger.info("구조 감지: result.result.content")
            # 이 부분에서 content를 직접 반환
            return inner_result["content"]
    
    # 1. 직접적인 메시지 필드가 있는 경우
    if not message and isinstance(result, dict) and "message" in result:
        logger.info("구조 감지: result.message")
        message = result["message"]
    
    # 2. 중첩된 result 구조에서 message 필드 확인
    if not message and isinstance(result, dict) and "result" in result and isinstance(result["result"], dict):
        inner_result = result["result"]
        if "message" in inner_result:
            logger.info("구조 감지: result.result.message")
            message = inner_result["message"]
    
    # 3. 문자열 결과인 경우
    if not message and isinstance(result, str):
        logger.info("구조 감지: 직접 문자열")
        message = result
        
    # 4. 결과가 리스트인 경우 (여러 에이전트의 결과를 표현할 때)
    if not message and isinstance(result, list):
        logger.info("구조 감지: 결과 리스트")
        # 리스트 내용을 마크다운으로 변환
        message = "## 에이전트 결과 요약\n\n"
        for idx, item in enumerate(result):
            if isinstance(item, dict):
                agent_role = item.get("role", f"에이전트 {idx+1}")
                agent_result = item.get("result", "")
                if agent_result:
                    message += f"### {agent_role}\n\n{agent_result}\n\n"
    
    # 결과가 없는 경우 기본 메시지
    if not message:
        logger.warning("결과 메시지를 추출할 수 없습니다: 구조가 예상과 다름")
        try:
            # 결과를 JSON으로 변환하여 제공
            import json
            message = f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
        except:
            message = "처리가 완료되었으나 결과가 없습니다."
    
    return message

@app.get("/conversations/{conversation_id}", tags=["conversation"])
async def get_conversation_by_api(conversation_id: str):
    """
    대화 정보 조회 API
    
    Args:
        conversation_id: 대화 ID
        
    Returns:
        대화 정보
    """
    try:
        if not app.state.context_manager:
            return {"error": "컨텍스트 관리자가 초기화되지 않았습니다."}
            
        conversation = await app.state.context_manager.get_conversation(conversation_id)
        
        if not conversation:
            return {"error": f"대화 {conversation_id}를 찾을 수 없습니다."} 
        
        # 응답 데이터 구성
        final_tasks = []
        
        if "tasks" in conversation:
            final_tasks = conversation["tasks"]
            
        response = {
            "conversation_id": conversation_id,
            "status": conversation.get("status", "unknown"),
            "tasks": final_tasks,
            "message": conversation.get("message", ""),
            "taskDecomposition": {
                "original_query": conversation.get("query", ""),
                "tasks": []
            }
        }
        
        # 실행 레벨별 자연어 태스크 설명이 있으면 추가
        if "task_descriptions" in conversation and conversation["task_descriptions"]:
            response["taskDecomposition"]["tasks"] = []
            
            # 각 레벨별 태스크를 플랫하게 변환하여 추가
            task_index = 0
            for level_idx, level_tasks in enumerate(conversation["task_descriptions"]):
                for task_desc in level_tasks:
                    response["taskDecomposition"]["tasks"].append({
                        "description": task_desc,
                        "role": final_tasks[task_index]["role"] if task_index < len(final_tasks) else "unknown",
                        "index": task_index,
                        "level": level_idx
                    })
                    task_index += 1
                    
            # 실행 레벨 정보도 추가
            execution_levels = []
            for level_idx, level_tasks in enumerate(conversation["task_descriptions"]):
                level_indices = []
                task_offset = 0
                
                # 이전 레벨의 태스크 수를 계산하여 오프셋 구하기
                for i in range(level_idx):
                    task_offset += len(conversation["task_descriptions"][i])
                
                # 현재 레벨의 태스크 인덱스 추가
                for j in range(len(level_tasks)):
                    level_indices.append(task_offset + j)
                
                execution_levels.append(level_indices)
            
            response["execution_levels"] = execution_levels
        
        return response
    except Exception as e:
        logger.error(f"대화 정보 조회 중 오류: {str(e)}")
        return {"error": f"대화 정보 조회 중 오류: {str(e)}"}

# 새로운 API 엔드포인트: 태스크 분리 결과 조회
@app.get("/conversations/{conversation_id}/decomposition", tags=["conversation"])
async def get_task_decomposition(conversation_id: str, message_id: Optional[str] = None):
    """
    태스크 분해 결과 조회 API
    
    Args:
        conversation_id: 대화 ID
        message_id: 메시지 ID (선택 사항)
        
    Returns:
        태스크 분해 결과
    """
    try:
        if message_id:
            # 특정 메시지 정보 조회
            logger.info(f"메시지 ID {message_id}로 태스크 분해 결과 조회 시도")
            message = await app.state.context_manager.get_message(message_id)
            if not message:
                logger.warning(f"메시지 {message_id}를 찾을 수 없습니다.")
                return {"error": f"메시지 {message_id}를 찾을 수 없습니다."}
                
            # 메시지에서 태스크 분해 결과 추출
            if "task_descriptions" in message:
                logger.info(f"메시지 {message_id}에서 태스크 분해 결과 확인됨")
                return {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "task_descriptions": message.get("task_descriptions", []),
                    "execution_levels": message.get("execution_levels", [])
                }
            else:
                logger.warning(f"메시지 {message_id}에 태스크 분해 결과가 없습니다.")
        
        # 메시지 ID가 없거나 메시지에 태스크 분해 결과가 없는 경우 대화 정보에서 조회
        logger.info(f"대화 ID {conversation_id}로 태스크 분해 결과 조회 시도")
        conversation = await app.state.context_manager.get_conversation(conversation_id)
        if not conversation:
            logger.warning(f"대화 {conversation_id}를 찾을 수 없습니다.")
            return {"error": f"대화 {conversation_id}를 찾을 수 없습니다."}
            
        if "task_descriptions" in conversation:
            logger.info(f"대화 {conversation_id}에서 태스크 분해 결과 확인됨")
            return {
                "conversation_id": conversation_id,
                "task_descriptions": conversation.get("task_descriptions", []),
                "execution_levels": conversation.get("execution_levels", []),
                "original_query": conversation.get("query", "")
            }
        else:
            logger.warning(f"대화 {conversation_id}에 태스크 분해 결과가 없습니다.")
            return {
                "conversation_id": conversation_id,
                "task_descriptions": [],
                "execution_levels": [],
                "original_query": conversation.get("query", ""),
                "status": "pending"
            }
    except Exception as e:
        logger.error(f"태스크 분해 결과 조회 중 오류: {str(e)}")
        return {"error": f"태스크 분해 결과 조회 중 오류가 발생했습니다: {str(e)}"}

# 새로운 API 엔드포인트: 에이전트 태스크 결과 조회
@app.get("/conversations/{conversation_id}/tasks", tags=["conversation"])
async def get_agent_tasks(conversation_id: str, message_id: Optional[str] = None):
    """
    에이전트 태스크 결과 조회 API
    
    Args:
        conversation_id: 대화 ID
        message_id: 메시지 ID (선택 사항)
        
    Returns:
        에이전트 태스크 결과
    """
    try:
        if message_id:
            # 특정 메시지 정보 조회
            logger.info(f"메시지 ID {message_id}로 태스크 결과 조회 시도")
            message = await app.state.context_manager.get_message(message_id)
            if not message:
                logger.warning(f"메시지 {message_id}를 찾을 수 없습니다.")
                return {"error": f"메시지 {message_id}를 찾을 수 없습니다."}
                
            # 메시지에서 태스크 결과 추출
            if "tasks" in message:
                logger.info(f"메시지 {message_id}에서 태스크 결과 확인됨: {len(message['tasks'])}개")
                return {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "tasks": message.get("tasks", [])
                }
            else:
                logger.warning(f"메시지 {message_id}에 태스크 결과가 없습니다.")
                return {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "tasks": []
                }
        
        # 메시지 ID가 없거나 메시지에 태스크 결과가 없는 경우 대화 정보에서 조회
        logger.info(f"대화 ID {conversation_id}로 태스크 결과 조회 시도")
        tasks = await app.state.context_manager.get_tasks_by_conversation(conversation_id)
        return {
            "conversation_id": conversation_id,
            "tasks": tasks
        }
    except Exception as e:
        logger.error(f"에이전트 태스크 결과 조회 중 오류: {str(e)}")
        return {"error": f"에이전트 태스크 결과 조회 중 오류가 발생했습니다: {str(e)}"}

# 새로운 API 엔드포인트: 최종 통합 결과 조회
@app.get("/conversations/{conversation_id}/result", tags=["conversation"])
async def get_final_result(conversation_id: str, message_id: Optional[str] = None):
    """
    최종 결과 조회 API
    
    Args:
        conversation_id: 대화 ID
        message_id: 메시지 ID (선택 사항)
        
    Returns:
        최종 대화 결과
    """
    try:
        if message_id:
            # 특정 메시지 정보 조회
            message = await app.state.context_manager.get_message(message_id)
            if not message:
                return {"error": f"메시지 {message_id}를 찾을 수 없습니다."}
                
            # 메시지에서 응답 추출
            return {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "message": message.get("response", ""),
                "status": message.get("status", "pending")
            }
        
        # 메시지 ID가 없는 경우 대화 정보에서 조회
        conversation = await app.state.context_manager.get_conversation(conversation_id)
        if not conversation:
            return {"error": f"대화 {conversation_id}를 찾을 수 없습니다."}
            
        return {
            "conversation_id": conversation_id,
            "message": conversation.get("message", ""),
            "status": conversation.get("status", "unknown")
        }
    except Exception as e:
        logger.error(f"최종 결과 조회 중 오류: {str(e)}")
        return {"error": f"최종 결과 조회 중 오류가 발생했습니다: {str(e)}"}

@app.get("/conversations/{conversation_id}/messages", tags=["conversation"])
async def get_conversation_messages(conversation_id: str):
    """
    대화에 속한 메시지 목록 조회 API
    
    Args:
        conversation_id: 대화 ID
        
    Returns:
        메시지 목록
    """
    try:
        if not app.state.context_manager:
            return {"error": "컨텍스트 관리자가 초기화되지 않았습니다."}
            
        # 대화에 속한 메시지 목록 조회
        messages = await app.state.context_manager.get_conversation_messages(conversation_id)
        
        if not messages:
            return {
                "conversation_id": conversation_id,
                "messages": []
            }
            
        # 메시지 목록 반환
        return {
            "conversation_id": conversation_id,
            "messages": messages
        }
    except Exception as e:
        logger.error(f"대화 메시지 목록 조회 중 오류: {str(e)}")
        return {"error": f"대화 메시지 목록 조회 중 오류: {str(e)}"}

# 서버 실행 (직접 실행 시)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
