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
            "requires_context": True,  # context가 필요함을 명시
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
        
        # 태스크 데이터 추출
        params = task.get("params", {})
        topic = params.get("topic", "")
        
        # 태스크가 없는 경우 오류 반환
        if not topic:
            logging.warning(f"태스크 {task_id}: 주제가 비어 있습니다")
            return {
                "status": "error",
                "error": "주제가 제공되지 않았습니다",
                "result": {
                    "content": "작성할 주제를 지정해 주세요."
                },
                "role": AGENT_ROLE,
                "task_id": task_id
            }
        
        # 컨텍스트 데이터 수집
        context_data = []
        references = []
        
        # 1. 파라미터에서 references 추출
        if "references" in params and params["references"]:
            references.extend(params["references"])
            logging.info(f"params에서 {len(params['references'])}개의 참조 자료 추출")
        
        # 2. context에서 depends_results 추출
        if "context" in task and isinstance(task["context"], dict):
            context = task["context"]
            logging.info(f"컨텍스트 키: {list(context.keys())}")
            
            if "depends_results" in context and isinstance(context["depends_results"], list):
                context_data.extend(context["depends_results"])
                logging.info(f"context에서 {len(context['depends_results'])}개의 의존성 결과 추출")
        
        # 3. 직접 의존성 데이터 처리
        if "depends_results" in task and isinstance(task["depends_results"], list):
            context_data.extend(task["depends_results"])
            logging.info(f"task에서 {len(task['depends_results'])}개의 의존성 결과 추출")
        
        # 4. previous_results 처리
        if "previous_results" in params and isinstance(params["previous_results"], list):
            context_data.extend(params["previous_results"])
            logging.info(f"previous_results에서 {len(params['previous_results'])}개의 결과 추출")
        
        logging.info(f"총 {len(context_data)}개의 컨텍스트 데이터 수집됨")
        
        # 컨텍스트 데이터를 JSON 형식으로 변환하여 프롬프트에 추가
        context_json = []
        for idx, data in enumerate(context_data):
            if not data:
                continue
                
            # 데이터 간소화: 중요 필드만 유지
            simplified_data = {}
            
            # role 필드 추출
            if isinstance(data, dict):
                # 직접 role 필드가 있는 경우
                if "role" in data:
                    simplified_data["role"] = data["role"]
                # params에 role이 있는 경우
                elif "params" in data and isinstance(data["params"], dict) and "role" in data["params"]:
                    simplified_data["role"] = data["params"]["role"]
                # 기본값
                else:
                    simplified_data["role"] = "unknown"
                
                # 결과 데이터 추출
                if "result" in data and data["result"]:
                    if isinstance(data["result"], dict):
                        # 결과가 딕셔너리인 경우 그대로 포함
                        simplified_data["result"] = data["result"]
                    else:
                        # 다른 타입인 경우 문자열로 변환
                        simplified_data["result"] = str(data["result"])
                        
                # 결과가 없을 경우 전체 데이터 포함
                else:
                    simplified_data = data
                    
            # 데이터가 딕셔너리가 아닌 경우 문자열로 변환
            else:
                simplified_data = {"data": str(data)}
            
            context_json.append(simplified_data)
        
        # 프롬프트 구성
        prompt = f"""# 작성 요청: {topic}

## 컨텍스트 정보
다음은 이 주제에 관련된 컨텍스트 정보입니다. 이 정보를 활용하여 보고서를 작성해주세요.

```json
{json.dumps(context_json, ensure_ascii=False, indent=2)}
```

## 요청 사항
위 컨텍스트 정보를 활용하여 주제 '{topic}'에 대한 구조화된 보고서를 작성해주세요.
- 보고서는 명확한 제목, 소개, 본문, 결론 등의 구조를 가져야 합니다.
- 컨텍스트 정보에 포함된 웹 검색 결과, 코드 등을 적절히 활용하세요.
- 정보가 부족한 부분은 일반적인 지식으로 보완하되, 출처가 명확한 정보를 우선적으로 사용하세요.
- 사실과 의견을 명확히 구분하고, 객관적인 내용 중심으로 작성하세요.
"""
        
        logging.info(f"최종 프롬프트 길이: {len(prompt)}")
        
        # LLM 호출
        result = None
        try:
            from common.llm_client import LLMClient
            llm = LLMClient()
            logging.info(f"LLM 클라이언트 호출 시작 (태스크: {task_id})")
            result = llm.ask(prompt)
            logging.info(f"LLM 응답 완료 (태스크: {task_id}, 길이: {len(result)})")
        except Exception as e:
            logging.error(f"LLM 호출 오류: {str(e)}", exc_info=True)
            # 오류 발생 시 간단한 응답 생성
            result = f"""
# {topic}

## 오류 알림
LLM 서비스 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.

## 컨텍스트 요약
컨텍스트 데이터 {len(context_json)}개 항목 수신됨.
"""
        
        # 결과 반환
        return {
            "status": "success",
            "result": {
                "content": result
            },
            "role": AGENT_ROLE,
            "task_id": task_id
        }
    except Exception as e:
        logging.exception(f"태스크 실행 중 오류 발생: {str(e)}")
        # 오류 발생 시에도 형식에 맞게 응답
        return {
            "status": "error",
            "error": str(e),
            "result": {
                "content": f"처리 중 오류가 발생했습니다: {str(e)}"
            },
            "role": AGENT_ROLE,
            "task_id": task_id
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
