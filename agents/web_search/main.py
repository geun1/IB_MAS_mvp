from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
import os
import json
from typing import Dict, List, Optional, Any
import time
import psutil
from datetime import datetime
import logging
import asyncio

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Web Search Agent API",
    description="웹 검색 기능을 제공하는 에이전트 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "syntaxHighlight": {"theme": "nord"},
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    }
)

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # 기본값 20초

# 설정 저장소 (설정이 제공되지 않았을 때를 대비한 기본값)
DEFAULT_CONFIG = {
    # "api_key": os.getenv("GOOGLE_SEARCH_API_KEY", ""),
    # "cx": os.getenv("GOOGLE_SEARCH_CX", "")
    "api_key": "AIzaSyCcEtvfrhIcJM7uCForostcjtMGlqabMXw",
    "cx": "b5349ca185e00462d"
}

# 모델 정의
class SearchRequest(BaseModel):
    query: str
    api_key: Optional[str] = None  # 선택적 API 키 매개변수
    cx: Optional[str] = None  # 선택적 Custom Search Engine ID 매개변수

class SearchResponse(BaseModel):
    results: List[Dict[str, str]]

# 초기 등록을 위한 변수들
AGENT_ID = "web_search_agent_1"
AGENT_ROLE = "web_search"
AGENT_DESCRIPTION = "웹에서 정보를 검색하고 관련 결과를 반환합니다."

# 상태 초기화
app.state.active_tasks = set()  # 활성 작업 추적을 위한 set

# 등록 태스크
async def register_agent():
    """레지스트리에 에이전트 등록"""
    try:
        # 컨테이너 외부에서 접근 가능한 엔드포인트 구성
        container_name = os.getenv("CONTAINER_NAME", "web_search_agent")
        port = int(os.getenv("PORT", "8000"))
        
        # 포트가 기본 8000이 아닌 경우를 처리
        if port != 8000:
            service_endpoint = f"http://{container_name}:{port}"
        else:
            service_endpoint = f"http://{container_name}:8000"
            
        # 에이전트 데이터 준비
        agent_data = {
            "id": AGENT_ID,
            "role": AGENT_ROLE,
            "description": AGENT_DESCRIPTION,
            "endpoint": service_endpoint,  # 엔드포인트 추가
            "type": "function",
            "params": [
                {
                    "name": "query",
                    "description": "검색할 쿼리 또는 키워드",
                    "required": True,
                    "type": "string"
                }
            ],
            "config_params": [  # 설정 파라미터 정의
                {
                    "name": "api_key",
                    "description": "Google Custom Search API Key",
                    "required": True,
                    "type": "string",
                    "is_secret": True  # 보안 민감 정보
                },
                {
                    "name": "cx",
                    "description": "Google Custom Search Engine ID",
                    "required": True,
                    "type": "string"
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{REGISTRY_URL}/register",
                json=agent_data
            )
            print(f"Agent registration response: {response.status_code}, {response.text}")
            
    except Exception as e:
        print(f"Failed to register agent: {str(e)}")

# 하트비트 보내기
async def send_heartbeat():
    """Registry에 하트비트 전송"""
    while True:
        try:
            heartbeat_data = {
                "status": "active",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "memory_usage": psutil.virtual_memory().percent,
                    "cpu_usage": psutil.cpu_percent(),
                    "active_tasks": 0  # 현재는 단순히 0으로 설정
                },
                "version": "1.0.0"
            }
            
            url = f"{REGISTRY_URL}/heartbeat/{AGENT_ROLE}/{AGENT_ID}"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=heartbeat_data, timeout=5)
                if response.status_code == 200:
                    logging.info("Heartbeat 전송 성공")
                else:
                    logging.warning(f"Heartbeat 전송 실패: {response.status_code}")
        
        except Exception as e:
            logging.error(f"Heartbeat 전송 중 오류: {str(e)}")
        
        await asyncio.sleep(HEARTBEAT_INTERVAL)

# 시작 시 등록
@app.on_event("startup")
async def startup_event():
    # 에이전트 등록
    await register_agent()
    
    # 하트비트 태스크 시작
    asyncio.create_task(send_heartbeat())

# 공통 검색 함수
async def perform_google_search(query: str, api_key: str, cx: str, num_results: int = 5):
    """
    Google Custom Search API를 사용하여 웹 검색을 수행합니다.
    
    Args:
        query: 검색어
        api_key: Google API 키
        cx: Custom Search Engine ID
        num_results: 반환할 결과 개수 (기본값: 5)
        
    Returns:
        검색 결과 딕셔너리 (raw_data, formatted_result, search_results 포함)
    """
    if not query:
        return {
            "status": "error",
            "error": "검색어가 제공되지 않았습니다"
        }
    
    if not api_key or not cx:
        return {
            "status": "error",
            "error": "Google Custom Search API 설정이 없습니다"
        }
    
    # Google Custom Search API 호출
    GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
    search_params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": num_results,
    }
    
    logging.info(f"Google Search API 호출: {query}")
    async with httpx.AsyncClient() as client:
        response = await client.get(GOOGLE_SEARCH_URL, params=search_params)
        
        if response.status_code != 200:
            error_msg = f"Google Search API 호출 실패: {response.status_code}, {response.text}"
            logging.error(error_msg)
            return {
                "status": "error",
                "error": "Google Search API 호출 실패",
                "details": error_msg
            }
        
        data = response.json()
        
        # 검색 결과가 없는 경우
        if "items" not in data or not data["items"]:
            return {
                "status": "success",
                "message": f"'{query}'에 대한 검색 결과가 없습니다.",
                "search_results": []
            }
        
        # 검색 결과 처리
        search_results = []
        for item in data.get("items", []):
            search_results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", "")
            })
        
        # 마크다운 형식으로 결과 포맷팅
        formatted_result = f"## '{query}'에 대한 검색 결과\n\n"
        
        for idx, result in enumerate(search_results, 1):
            formatted_result += f"### {idx}. {result['title']}\n"
            formatted_result += f"{result['snippet']}\n"
            formatted_result += f"[링크]({result['url']})\n\n"
        
        return {
            "status": "success",
            "raw_data": data,
            "formatted_result": formatted_result,
            "search_results": search_results
        }

# 검색 API
@app.post("/search")
async def search(request: SearchRequest):
    try:
        # 요청에서 API 키와 CX를 가져오거나 기본 설정 사용
        # api_key = request.api_key or DEFAULT_CONFIG["api_key"]
        # cx = request.cx or DEFAULT_CONFIG["cx"]
        api_key = DEFAULT_CONFIG["api_key"]
        cx = DEFAULT_CONFIG["cx"]
        if not api_key or not cx:
            raise HTTPException(
                status_code=400, 
                detail="Google Custom Search API 설정이 없습니다. API 키와 CX를 설정해주세요."
            )
            
        if not request.query:
            raise HTTPException(
                status_code=400,
                detail="검색어가 제공되지 않았습니다."
            )
        
        # 공통 검색 함수 사용
        result = await perform_google_search(request.query, api_key, cx)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        
        # API 응답 형식에 맞게 반환
        return {"results": result["search_results"]}
    
    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"검색 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")

# 루트 경로에도 동일한 핸들러 등록 (호환성 유지)
@app.post("/")
async def run_task_root(task: dict):
    """루트 경로 태스크 실행 (호환성용)"""
    return await run_task(task)

@app.post("/run")
async def run_task(task: dict):
    """태스크 실행 엔드포인트"""
    try:
        # 태스크 ID 로깅 추가
        task_id = task.get("task_id", "unknown")
        logging.info(f"태스크 수신: {task_id}")
        
        # 태스크 데이터 추출
        params = task.get("params", {})
        query = params.get("query", "")
        
        # 설정 파라미터 추출 (우선순위: task params > agent_configs > 환경변수 기본값)
        # api_key = params.get("api_key", "")
        # cx = params.get("cx", "")
        api_key = DEFAULT_CONFIG["api_key"]
        cx = DEFAULT_CONFIG["cx"]
        
        # agent_configs에서 설정 가져오기 (UI에서 전송된 경우)
        agent_configs = task.get("agent_configs", {})
        web_search_config = agent_configs.get("web_search", {})
        
        if not api_key and web_search_config:
            api_key = web_search_config.get("api_key", DEFAULT_CONFIG["api_key"])
            logging.info(f"태스크 {task_id}: agent_configs에서 API 키 설정 사용")
            
        if not cx and web_search_config:
            cx = web_search_config.get("cx", DEFAULT_CONFIG["cx"])
            logging.info(f"태스크 {task_id}: agent_configs에서 CX 설정 사용")

        # 설정 유효성 검사
        if not api_key or api_key.strip() == "":
            logging.warning(f"태스크 {task_id}: API Key가 설정되지 않았습니다")
            return {
                "status": "error",
                "error": "Google Custom Search API Key가 설정되지 않았습니다",
                "result": {
                    "content": "API Key를 설정 페이지에서 먼저 설정해주세요. 설정 > 에이전트 설정 메뉴에서 web_search 에이전트의 api_key를 입력해주세요."
                }
            }
        
        if not cx or cx.strip() == "":
            logging.warning(f"태스크 {task_id}: Custom Search Engine ID가 설정되지 않았습니다")
            return {
                "status": "error",
                "error": "Google Custom Search Engine ID가 설정되지 않았습니다",
                "result": {
                    "content": "Custom Search Engine ID(cx)를 설정 페이지에서 먼저 설정해주세요. 설정 > 에이전트 설정 메뉴에서 web_search 에이전트의 cx를 입력해주세요."
                }
            }
        
        if not query:
            logging.warning(f"태스크 {task_id}: 검색어가 비어 있습니다")
            return {
                "status": "error",
                "error": "검색어가 제공되지 않았습니다",
                "result": {
                    "content": "검색어를 지정해 주세요."
                }
            }
        
        # 공통 검색 함수 사용
        try:
            logging.info(f"태스크 {task_id}: '{query}' 검색 시작")
            search_result = await perform_google_search(query, api_key, cx)
            
            if search_result["status"] == "error":
                logging.error(f"태스크 {task_id}: 검색 오류 - {search_result['error']}")
                return {
                    "status": "error",
                    "error": search_result["error"],
                    "result": {
                        "content": search_result.get("details", search_result["error"])
                    }
                }
            
            if not search_result["search_results"]:
                logging.info(f"태스크 {task_id}: '{query}'에 대한 검색 결과 없음")
                return {
                    "status": "success",
                    "result": {
                        "content": f"'{query}'에 대한 검색 결과가 없습니다."
                    }
                }
            
            # 성공 응답 반환
            logging.info(f"태스크 {task_id}: 검색 성공 - {len(search_result['search_results'])}개의 결과")
            return {
                "status": "success",
                "result": {
                    "content": search_result["formatted_result"],
                    "raw_results": search_result["search_results"]
                }
            }
        except Exception as e:
            error_msg = f"검색 중 오류 발생: {str(e)}"
            logging.exception(f"태스크 {task_id}: {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "result": {
                    "content": f"검색 중 오류가 발생했습니다: {str(e)}"
                }
            }
            
    except Exception as e:
        logging.exception(f"태스크 실행 중 오류 발생: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "result": {
                "content": f"처리 중 오류가 발생했습니다: {str(e)}"
            }
        }

# 서버 상태 확인용 API
@app.get("/")
async def root():
    return {"status": "online", "service": "Web Search Agent", "id": AGENT_ID, "role": AGENT_ROLE}

# 서버 상태 확인용 API
@app.get("/health")
async def health():
    return {"status": "healthy"}

# 종료 이벤트 핸들러 추가
@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 처리"""
    try:
        # 일반 unregister 엔드포인트 시도
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{REGISTRY_URL}/unregister",
                    params={"role": AGENT_ROLE, "agent_id": AGENT_ID}
                )
                logging.info(f"에이전트 등록 해제 응답: {response.status_code}")
                
                # 실패 시 백업 메서드 사용
                if response.status_code != 200:
                    backup_response = await client.post(
                        f"{REGISTRY_URL}/unregister_direct",
                        params={"role": AGENT_ROLE, "agent_id": AGENT_ID}
                    )
                    logging.info(f"백업 등록 해제 응답: {backup_response.status_code}")
            except Exception as req_error:
                logging.error(f"등록 해제 요청 중 오류: {str(req_error)}")
                
    except Exception as e:
        logging.error(f"에이전트 등록 해제 중 오류: {str(e)}")
