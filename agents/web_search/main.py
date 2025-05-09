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
from bs4 import BeautifulSoup
import re

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
    "api_key": os.getenv("GOOGLE_SEARCH_API_KEY", ""),
    "cx": os.getenv("GOOGLE_SEARCH_CX", "")
}

# 모델 정의
class SearchRequest(BaseModel):
    query: str
    api_key: Optional[str] = None  # 선택적 API 키 매개변수
    cx: Optional[str] = None  # 선택적 Custom Search Engine ID 매개변수
    fetch_html: Optional[bool] = False  # HTML 내용 가져오기 옵션

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
                },
                {
                    "name": "fetch_html",
                    "description": "검색 결과의 웹페이지 HTML 내용을 가져올지 여부",
                    "required": False,
                    "type": "boolean",
                    "default": False
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

# HTML 태그 제거 함수
def strip_html_tags(html_content: str) -> str:
    """
    HTML 콘텐츠에서 불필요한 요소를 제거하고 의미 있는 텍스트만 추출합니다.
    CSS, 스크립트, 태그 이름 등을 제거하여 LLM에 적합한 형태로 정제합니다.
    
    Args:
        html_content: HTML 콘텐츠
        
    Returns:
        정제된 텍스트
    """
    if not html_content:
        return ""
        
    # BeautifulSoup 파서 생성
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. 불필요한 요소 제거 (스크립트, 스타일, 코드 블록 등)
    for element in soup(['script', 'style', 'code', 'noscript', 'svg', 'canvas', 'footer', 'nav']):
        element.decompose()
    
    # 2. 주석 제거
    for comment in soup.findAll(string=lambda text: isinstance(text, (str, bytes))):
        comment.extract()
    
    # 3. 일반적으로 의미 있는 콘텐츠를 담고 있는 태그와 그 내용을 보존하면서 텍스트 추출
    # 제목, 단락, 목록 등의 의미 있는 요소에는 개행을 추가하여 구조 보존
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']):
        tag.append('\n')
    
    # 4. 텍스트 추출 - 줄바꿈과 공백 유지를 위한 설정
    text = soup.get_text(separator=' ', strip=True)
    
    # 5. 정규식을 사용하여 텍스트 정제
    # HTML 엔티티 제거
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    
    # 특수 유니코드 문자와 제어 문자 제거
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    
    # URL, 이메일 주소 등을 정리하여 보존
    text = re.sub(r'https?://\S+', '[URL]', text)
    text = re.sub(r'\S+@\S+\.\S+', '[EMAIL]', text)
    
    # 여러 개의 연속된 공백, 탭, 줄바꿈 등을 하나의 공백으로 치환
    text = re.sub(r'\s+', ' ', text)
    
    # 문장 사이에 적절한 공백 추가
    text = re.sub(r'(\. |\.$)(?=[A-Z])', '.\n', text)
    
    # 최종 텍스트 다듬기 - 앞뒤 공백 제거
    text = text.strip()
    
    return text

# 웹페이지 HTML 가져오기
async def fetch_webpage_content(url: str) -> Dict[str, Any]:
    """
    주어진 URL에서 웹페이지의 HTML 내용을 가져옵니다.
    
    Args:
        url: 웹페이지 URL
        
    Returns:
        HTML 콘텐츠와 메타데이터를 포함하는 딕셔너리
    """
    try:
        # 일반적인 브라우저처럼 보이는 헤더 추가
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # 타임아웃 증가하고 리다이렉트 허용
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers=headers) as client:
            logging.info(f"URL 접속 시도: {url}")
            response = await client.get(url)
            
            if response.status_code != 200:
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "content": "",
                    "error": f"상태 코드 {response.status_code}",
                    "text_content": "",
                    "stripped_content": ""
                }
            
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 메타데이터 추출 (제목, 설명 등)
            title = soup.title.text.strip() if soup.title else ""
            description = ""
            if soup.find("meta", attrs={"name": "description"}):
                description = soup.find("meta", attrs={"name": "description"}).get("content", "")
            elif soup.find("meta", attrs={"property": "og:description"}):
                description = soup.find("meta", attrs={"property": "og:description"}).get("content", "")
            
            # 본문 내용 추출 강화 - 우선순위에 따라 주요 콘텐츠 포함 요소 찾기
            main_content_html = ""
            
            # 1. 주요 콘텐츠 영역을 포함할 가능성이 높은 태그들을 우선순위대로 검색
            potential_content_elements = []
            
            # 주요 콘텐츠 요소 후보들(우선순위 순)
            selectors = [
                'article', 'main', '#content', '.content', '.post-content', '.entry-content', 
                '.article-content', '.post', '.entry', '#main-content', 'section[role="main"]',
                '.main', '.body', '.story', '.story-content', '.page-content'
            ]
            
            # 선택자를 순회하며 요소 찾기
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    potential_content_elements.extend(elements)
            
            if potential_content_elements:
                # 가장 많은 텍스트를 포함한 요소를 선택 (단순 길이가 아닌 의미 있는 텍스트 양 기준)
                main_element = max(potential_content_elements, 
                                   key=lambda e: len(e.get_text(strip=True)))
                main_content_html = str(main_element)
            else:
                # 주요 콘텐츠 요소가 없으면 전체 body 사용
                body = soup.find('body')
                if body:
                    # 헤더, 푸터, 사이드바 등 제거
                    for element in body.select('header, footer, nav, aside, .sidebar, .comments, .advertisement, .ads, script, style'):
                        if element:
                            element.decompose()
                    main_content_html = str(body)
                else:
                    main_content_html = html_content
            
            # 간단한 텍스트 추출
            simple_text_content = soup.get_text(separator=' ', strip=True)
            
            # 개선된 strip_html_tags 함수로 내용 정제
            text_content = strip_html_tags(html_content)
            
            # 본문 영역만 집중적으로 정제한 텍스트
            main_content_text = strip_html_tags(main_content_html)
            
            # LLM에 최적화된 텍스트 생성
            # 제목과 설명을 앞에 추가하고, 본문 내용 포함
            llm_optimized_text = ""
            if title:
                llm_optimized_text += f"제목: {title}\n\n"
            if description:
                llm_optimized_text += f"설명: {description}\n\n"
            llm_optimized_text += f"본문 내용:\n{main_content_text}"
            
            return {
                "url": url,
                "status_code": response.status_code,
                "title": title,
                "description": description,
                "content": simple_text_content,
                "text_content": text_content,
                "stripped_content": llm_optimized_text
            }
            
    except Exception as e:
        logging.error(f"URL 접속 실패: {url}, 오류: {str(e)}")
        return {
            "url": url,
            "status_code": 500,
            "content": "",
            "error": str(e),
            "text_content": "",
            "stripped_content": ""
        }

# 공통 검색 함수
async def perform_google_search(query: str, api_key: str, cx: str, num_results: int = 1, fetch_html: bool = False):
    """
    Google Custom Search API를 사용하여 웹 검색을 수행합니다.
    
    Args:
        query: 검색어
        api_key: Google API 키
        cx: Custom Search Engine ID
        num_results: 반환할 결과 개수 (기본값: 5)
        fetch_html: 검색 결과의 웹페이지 HTML 내용을 가져올지 여부
        
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
            result_item = {
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", "")
            }
            search_results.append(result_item)
        
        # HTML 내용 가져오기 옵션이 활성화된 경우
        if fetch_html:
            logging.info(f"HTML 내용 가져오기 시작: {len(search_results)}개 URL")
            html_content_tasks = []
            
            # 각 URL에 대한 HTML 가져오기 태스크 생성
            for result in search_results:
                html_content_tasks.append(fetch_webpage_content(result["url"]))
            
            # 모든 태스크 실행 및 결과 대기
            html_results = await asyncio.gather(*html_content_tasks)
            
            # 검색 결과에 HTML 내용 추가
            for i, html_result in enumerate(html_results):
                if html_result["status_code"] == 200:
                    search_results[i]["html_content"] = html_result["content"]
                    search_results[i]["clean_content"] = html_result["text_content"]
                    search_results[i]["text_content"] = html_result["text_content"]
                    search_results[i]["stripped_content"] = html_result["stripped_content"]
                else:
                    search_results[i]["html_error"] = html_result["error"]
        
        # 마크다운 형식으로 결과 포맷팅
        formatted_result = f"## '{query}'에 대한 검색 결과\n\n"
        
        for idx, result in enumerate(search_results, 1):
            formatted_result += f"### {idx}. {result['title']}\n"
            formatted_result += f"{result['snippet']}\n"
            formatted_result += f"[링크]({result['url']})\n\n"
            
            # HTML 내용이 있는 경우 항상 텍스트 내용 추가
            if "text_content" in result and result["text_content"]:
                text_preview = result["text_content"][:500] + "..." if len(result["text_content"]) > 500 else result["text_content"]
                formatted_result += f"**페이지 내용 미리보기:**\n{text_preview}\n\n"
            elif "stripped_content" in result and result["stripped_content"]:
                text_preview = result["stripped_content"][:500] + "..." if len(result["stripped_content"]) > 500 else result["stripped_content"] 
                formatted_result += f"**페이지 내용 미리보기:**\n{text_preview}\n\n"
        
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
        service_type = "web_search"
        container_name = os.environ.get("MAS_WEB_SEARCH_SERVICE_NAME", "web_search_agent")
        service_endpoint = f"http://{container_name}:8000"
        
        # 검색 시작 시간
        start_time = time.time()
        
        # 로깅
        logging.info(f"검색 시작: {request.query}")
        
        # HTML 내용을 항상 가져오도록 설정
        fetch_html = True
        
        # Google 검색 수행
        search_results = await perform_google_search(request.query, request.api_key or DEFAULT_CONFIG["api_key"], request.cx or DEFAULT_CONFIG["cx"], fetch_html=fetch_html)
        
        # 검색 완료 시간 및 소요 시간 계산
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 응답 생성
        response = {
            "query": request.query,
            "results": search_results["search_results"],
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "elapsed_time": elapsed_time,
                "service_type": service_type,
                "service_endpoint": service_endpoint
            },
            "formatted_result": search_results["formatted_result"]
        }
        
        # 로깅
        logging.info(f"검색 완료: {request.query}, 결과 수: {len(search_results['search_results'])}, 소요 시간: {elapsed_time:.2f}초")
        
        return response
    except Exception as e:
        logging.error(f"검색 오류: {str(e)}")
        error_message = f"검색 중 오류 발생: {str(e)}"
        return {
            "query": request.query if hasattr(request, 'query') else "",
            "results": [],
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "elapsed_time": 0,
                "service_type": "web_search",
                "service_endpoint": f"http://{os.environ.get('MAS_WEB_SEARCH_SERVICE_NAME', 'web_search_agent')}:8000",
                "error": error_message
            },
            "formatted_result": f"## 검색 오류\n\n{error_message}"
        }

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
        
        # 검색 시작 시간
        start_time = time.time()
        
        # 태스크 데이터 추출
        params = task.get("params", {})
        query = params.get("query", "")
        fetch_html = True  # HTML 가져오기 옵션을 항상 True로 설정
        
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
                "query": query,
                "results": [],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_time": time.time() - start_time,
                    "service_type": "web_search",
                    "service_endpoint": f"http://{os.environ.get('MAS_WEB_SEARCH_SERVICE_NAME', 'web_search_agent')}:8000",
                    "task_id": task_id,
                    "error": "Google Custom Search API Key가 설정되지 않았습니다",
                    "message": "API Key를 설정 페이지에서 먼저 설정해주세요. 설정 > 에이전트 설정 메뉴에서 web_search 에이전트의 api_key를 입력해주세요."
                },
                "formatted_result": f"## API 키 오류\n\nGoogle Custom Search API Key가 설정되지 않았습니다. 설정 > 에이전트 설정 메뉴에서 web_search 에이전트의 api_key를 입력해주세요."
            }
        
        if not cx or cx.strip() == "":
            logging.warning(f"태스크 {task_id}: Custom Search Engine ID가 설정되지 않았습니다")
            return {
                "query": query,
                "results": [],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_time": time.time() - start_time,
                    "service_type": "web_search",
                    "service_endpoint": f"http://{os.environ.get('MAS_WEB_SEARCH_SERVICE_NAME', 'web_search_agent')}:8000",
                    "task_id": task_id,
                    "error": "Google Custom Search Engine ID가 설정되지 않았습니다",
                    "message": "Custom Search Engine ID(cx)를 설정 페이지에서 먼저 설정해주세요. 설정 > 에이전트 설정 메뉴에서 web_search 에이전트의 cx를 입력해주세요."
                },
                "formatted_result": f"## 검색 엔진 ID 오류\n\nGoogle Custom Search Engine ID(cx)가 설정되지 않았습니다. 설정 > 에이전트 설정 메뉴에서 web_search 에이전트의 cx를 입력해주세요."
            }
        
        if not query:
            logging.warning(f"태스크 {task_id}: 검색어가 비어 있습니다")
            return {
                "query": "",
                "results": [],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_time": time.time() - start_time,
                    "service_type": "web_search",
                    "service_endpoint": f"http://{os.environ.get('MAS_WEB_SEARCH_SERVICE_NAME', 'web_search_agent')}:8000",
                    "task_id": task_id,
                    "error": "검색어가 제공되지 않았습니다",
                    "message": "검색어를 지정해 주세요."
                },
                "formatted_result": f"## 검색어 오류\n\n검색어가 제공되지 않았습니다. 검색어를 지정해 주세요."
            }
        
        # 공통 검색 함수 사용 - HTML 가져오기 옵션 추가
        try:
            logging.info(f"태스크 {task_id}: '{query}' 검색 시작")
            search_result = await perform_google_search(query, api_key, cx, fetch_html=fetch_html)
            
            if search_result["status"] == "error":
                logging.error(f"태스크 {task_id}: 검색 오류 - {search_result['error']}")
                return {
                    "query": query,
                    "results": [],
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "elapsed_time": time.time() - start_time,
                        "service_type": "web_search",
                        "service_endpoint": f"http://{os.environ.get('MAS_WEB_SEARCH_SERVICE_NAME', 'web_search_agent')}:8000",
                        "task_id": task_id,
                        "error": search_result["error"],
                        "message": search_result.get("details", search_result["error"])
                    },
                    "formatted_result": f"## 검색 오류\n\n{search_result['error']}"
                }
            
            if not search_result["search_results"]:
                logging.info(f"태스크 {task_id}: '{query}'에 대한 검색 결과 없음")
                return {
                    "query": query,
                    "results": [],
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "elapsed_time": time.time() - start_time,
                        "service_type": "web_search",
                        "service_endpoint": f"http://{os.environ.get('MAS_WEB_SEARCH_SERVICE_NAME', 'web_search_agent')}:8000",
                        "task_id": task_id,
                        "message": f"'{query}'에 대한 검색 결과가 없습니다."
                    },
                    "formatted_result": f"## '{query}'에 대한 검색 결과\n\n검색 결과가 없습니다."
                }
            
            # 성공 응답 반환
            logging.info(f"태스크 {task_id}: 검색 성공 - {len(search_result['search_results'])}개의 결과")
            
            # 검색 완료 시간 및 소요 시간 계산
            end_time = time.time()
            elapsed_time = end_time - start_time if 'start_time' in locals() else 0
            
            # /search와 동일한 형식으로 응답 생성
            service_type = "web_search"
            container_name = os.environ.get("MAS_WEB_SEARCH_SERVICE_NAME", "web_search_agent")
            service_endpoint = f"http://{container_name}:8000"
            
            return {
                "query": query,
                "results": search_result["search_results"],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_time": elapsed_time,
                    "service_type": service_type,
                    "service_endpoint": service_endpoint,
                    "task_id": task_id
                },
                "formatted_result": search_result["formatted_result"]
            }
        except Exception as e:
            error_msg = f"검색 중 오류 발생: {str(e)}"
            logging.exception(f"태스크 {task_id}: {error_msg}")
            return {
                "query": query,
                "results": [],
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_time": time.time() - start_time,
                    "service_type": "web_search",
                    "service_endpoint": f"http://{os.environ.get('MAS_WEB_SEARCH_SERVICE_NAME', 'web_search_agent')}:8000",
                    "task_id": task_id,
                    "error": error_msg,
                    "message": f"검색 중 오류가 발생했습니다: {str(e)}"
                },
                "formatted_result": f"## 검색 오류\n\n검색 처리 중 오류가 발생했습니다: {str(e)}"
            }
            
    except Exception as e:
        logging.exception(f"태스크 실행 중 오류 발생: {str(e)}")
        return {
            "query": task.get("params", {}).get("query", ""),
            "results": [],
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "elapsed_time": time.time() - start_time if 'start_time' in locals() else 0,
                "service_type": "web_search",
                "service_endpoint": f"http://{os.environ.get('MAS_WEB_SEARCH_SERVICE_NAME', 'web_search_agent')}:8000",
                "task_id": task.get("task_id", "unknown"),
                "error": str(e),
                "message": f"처리 중 오류가 발생했습니다: {str(e)}"
            },
            "formatted_result": f"## 시스템 오류\n\n태스크 처리 중 오류가 발생했습니다: {str(e)}"
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
