from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
import json
from typing import Dict, List, Optional, Any
import time
import asyncio
import psutil
from datetime import datetime
import logging

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="Writer Agent")

# 상태 초기화
app.state.active_tasks = set()  # 활성 작업 추적을 위한 set

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # 기본값 20초

# 모델 정의
class WriterRequest(BaseModel):
    topic: str
    references: Optional[List[Dict[str, str]]] = None

class WriterResponse(BaseModel):
    content: str

# 초기 등록을 위한 변수들
AGENT_ID = "writer_agent_1"
AGENT_ROLE = "writer"
AGENT_DESCRIPTION = "주어진 주제와 참고 자료를 바탕으로 문서나 보고서를 작성합니다."

# 등록 태스크
async def register_agent():
    """레지스트리에 에이전트 등록"""
    try:
        # 컨테이너 외부에서 접근 가능한 엔드포인트 구성
        container_name = os.getenv("CONTAINER_NAME", "writer_agent")
        port = int(os.getenv("PORT", "8000"))
        
        # 포트가 기본 8000이 아닌 경우를 처리
        if port != 8000:
            service_endpoint = f"http://{container_name}:{port}/run"
        else:
            service_endpoint = f"http://{container_name}:8000/run"
        
        # 에이전트 데이터 준비
        agent_data = {
            "id": AGENT_ID,
            "role": AGENT_ROLE,
            "description": AGENT_DESCRIPTION,
            "endpoint": service_endpoint,  # 엔드포인트 추가
            "type": "function",
            "params": [
                {
                    "name": "topic",
                    "description": "작성할 주제",
                    "required": True,
                    "type": "string"
                },
                {
                    "name": "references",
                    "description": "참고할 자료 목록",
                    "required": False,
                    "type": "array"
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
            # 현재 메모리, CPU 사용량 측정
            memory_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent()
            
            # Heartbeat 데이터 형식
            heartbeat_data = {
                "status": "active",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "memory_usage": memory_usage,
                    "cpu_usage": cpu_usage,
                    "active_tasks": 0  # 현재는 단순히 0으로 설정
                },
                "version": "1.0.0"
            }
            
            # Registry에 heartbeat 전송
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

# 작성 API
@app.post("/write")
async def write(request: WriterRequest):
    try:
        # 실제로는 LLM을 호출해서 문서를 작성해야 함
        # 여기서는 간단한 응답 반환
        
        references_text = ""
        if request.references:
            references_text = " 참고 자료를 활용했습니다."
        
        content = f"""
# {request.topic} 보고서

## 개요
이 보고서는 {request.topic}에 대한 내용을 다룹니다.{references_text}

## 주요 내용
1. {request.topic}의 배경
2. 주요 개념 설명
3. 실제 적용 사례
4. 향후 전망

## 결론
{request.topic}은 매우 중요한 주제입니다. 더 많은 연구가 필요합니다.
"""
        
        return {"content": content}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Writing failed: {str(e)}")

# 작업 실행 API
@app.post("/run")
async def run_task(task: dict):
    """태스크 실행 엔드포인트"""
    try:
        # 태스크 ID 추출 및 로깅
        task_id = task.get("task_id", "unknown")
        logging.info(f"태스크 수신: {task_id}")
        
        # 전체 태스크 구조 상세 로깅
        logging.debug(f"태스크 전체 구조: {json.dumps(task, indent=2)}")
        
        # 태스크 데이터 추출
        params = task.get("params", {})
        topic = params.get("topic", "")
        
        # 의존성 결과 처리 - 더 상세한 로깅
        depends_results = task.get("depends_results", [])
        if "context" in task and isinstance(task["context"], dict):
            # context 필드를 통해 전달된 경우
            context_depends = task["context"].get("depends_results", [])
            if context_depends:
                logging.info(f"컨텍스트를 통해 의존성 데이터 수신: {len(context_depends)}개")
                depends_results = context_depends
        
        logging.info(f"의존성 데이터 수신: {len(depends_results)}개의 의존 태스크 결과")
        
        # 의존성 데이터 상세 로깅
        for i, dep_result in enumerate(depends_results):
            if isinstance(dep_result, dict):
                logging.info(f"의존성 데이터 {i+1} 구조: {list(dep_result.keys())}")
                if "result" in dep_result and isinstance(dep_result["result"], dict):
                    logging.info(f"  - result 필드 구조: {list(dep_result['result'].keys())}")
                logging.info(f"  - 역할: {dep_result.get('role', 'unknown')}")
            else:
                logging.info(f"의존성 데이터 {i+1} 타입: {type(dep_result)}")
        
        # 코드 생성 결과 추출 및 활용
        code_content = ""
        code_explanation = ""
        
        # 검색 결과 추출 및 활용
        search_results = []
        search_content = ""
        
        for dep_result in depends_results:
            if dep_result and isinstance(dep_result, dict):
                # 에이전트 역할 확인
                dep_role = dep_result.get("role", "unknown")
                
                # 코드 생성 에이전트의 결과인 경우
                if "code_files" in dep_result:
                    logging.info(f"코드 파일 발견: {list(dep_result['code_files'].keys())}")
                    for filename, code in dep_result["code_files"].items():
                        code_content += f"## {filename}\n```python\n{code}\n```\n\n"
                elif "result" in dep_result and isinstance(dep_result["result"], dict) and "code_files" in dep_result["result"]:
                    # 다른 구조로 중첩된 경우
                    logging.info(f"중첩된 구조에서 코드 파일 발견: {list(dep_result['result']['code_files'].keys())}")
                    for filename, code in dep_result["result"]["code_files"].items():
                        code_content += f"## {filename}\n```python\n{code}\n```\n\n"
                
                # 웹검색 결과 확인
                if dep_role == "web_search":
                    logging.info("웹검색 에이전트 결과 발견")
                    
                    # 직접 search_results 필드 확인
                    if "search_results" in dep_result:
                        search_results.extend(dep_result["search_results"])
                        logging.info(f"직접 search_results 발견: {len(dep_result['search_results'])}개")
                    
                    # result 필드 내부의 raw_results 확인
                    if "result" in dep_result and isinstance(dep_result["result"], dict):
                        if "raw_results" in dep_result["result"]:
                            search_results.extend(dep_result["result"]["raw_results"])
                            logging.info(f"result.raw_results 발견: {len(dep_result['result']['raw_results'])}개")
                        
                        # 포맷된 콘텐츠 확인
                        if "content" in dep_result["result"]:
                            search_content = dep_result["result"]["content"]
                            logging.info(f"검색 콘텐츠 발견: {len(search_content)} 문자")
                
                # 단순 텍스트 콘텐츠 처리
                if "content" in dep_result:
                    logging.info("텍스트 콘텐츠 발견, 길이: " + str(len(dep_result["content"])))
                    code_content += dep_result["content"] + "\n\n"
                elif "result" in dep_result and isinstance(dep_result["result"], dict) and "content" in dep_result["result"]:
                    # 중첩된 콘텐츠
                    logging.info("중첩된 텍스트 콘텐츠 발견, 길이: " + str(len(dep_result["result"]["content"])))
                    code_content += dep_result["result"]["content"] + "\n\n"
        
        # 검색 결과 및 코드 내용을 참조 텍스트로 결합
        reference_text = ""
        
        # 검색 결과 텍스트 추가
        if search_content:
            reference_text += f"## 웹 검색 결과\n{search_content}\n\n"
        elif search_results:
            reference_text += "## 웹 검색 결과\n"
            for idx, result in enumerate(search_results, 1):
                title = result.get("title", "제목 없음")
                snippet = result.get("snippet", "내용 없음")
                url = result.get("url", "")
                reference_text += f"### {idx}. {title}\n{snippet}\n"
                if url:
                    reference_text += f"[링크]({url})\n"
                reference_text += "\n"
        
        # 코드 콘텐츠 추가
        if code_content:
            reference_text += f"## 코드 및 분석\n{code_content}\n\n"
        
        if reference_text:
            logging.info(f"참조 텍스트가 프롬프트에 추가됨 (길이: {len(reference_text)})")
        
        # 프롬프트 구성
        if not topic:
            logging.warning(f"태스크 {task_id}: 주제가 비어 있습니다")
            return {
                "status": "error",
                "error": "주제가 제공되지 않았습니다",
                "result": {
                    "content": "작성할 주제를 지정해 주세요."
                }
            }
        
        # 프롬프트 내용 통합
        prompt = f"주제: {topic}\n\n"
        if reference_text:
            prompt += f"참고 자료:\n{reference_text}\n\n"
        prompt += "위 정보를 바탕으로 명확하고 구조화된 보고서를 작성해주세요."
        
        logging.info(f"최종 프롬프트 길이: {len(prompt)}")
        
        # LLM 호출 또는 모의 응답 생성
        result = None
        try:
            from common.llm_client import LLMClient
            llm = LLMClient()
            logging.info(f"LLM 클라이언트 호출 시작 (태스크: {task_id})")
            result = llm.ask(prompt)
            logging.info(f"LLM 응답 완료 (태스크: {task_id})")
        except Exception as e:
            logging.error(f"LLM 호출 오류: {str(e)}", exc_info=True)
            # 오류 발생 시 모의 응답으로 대체
            result = f"""
# {topic}

## 오류 알림
LLM 서비스 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.

## 참고 자료 요약
{reference_text[:500]}...
"""
        
        # 결과 반환
        logging.info(f"태스크 {task_id} 완료, 응답 길이: {len(result)}")
        return {
            "status": "success",
            "result": {
                "content": result
            }
        }
    except Exception as e:
        logging.exception(f"태스크 실행 중 오류 발생: {str(e)}")
        # 오류 발생 시에도 형식에 맞게 응답
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
    return {"status": "online", "service": "Writer Agent", "id": AGENT_ID, "role": AGENT_ROLE}

# 서버 상태 확인용 API
@app.get("/health")
async def health():
    return {"status": "healthy"}

# asyncio 임포트
import asyncio

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
