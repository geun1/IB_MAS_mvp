from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
import json
from typing import Dict, List, Optional, Any
import time
import asyncio

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="Writer Agent")

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")

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
    try:
        agent_data = {
            "id": AGENT_ID,
            "role": AGENT_ROLE,
            "description": AGENT_DESCRIPTION,
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
            ],
            "type": "function"
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
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{REGISTRY_URL}/heartbeat/{AGENT_ROLE}/{AGENT_ID}"
                )
                print(f"Heartbeat response: {response.status_code}")
        except Exception as e:
            print(f"Failed to send heartbeat: {str(e)}")
        
        # 20초마다 하트비트 전송
        await asyncio.sleep(20)

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
async def run_task(task: Dict[str, Any]):
    try:
        params = task.get("params", {})
        topic = params.get("topic")
        references = params.get("references", [])
        
        if not topic:
            raise HTTPException(status_code=400, detail="Topic parameter is required")
            
        # 작성 실행
        writer_request = WriterRequest(topic=topic, references=references)
        result = await write(writer_request)
        
        return {
            "status": "success",
            "result": result
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")

# 서버 상태 확인용 API
@app.get("/")
async def root():
    return {"status": "online", "service": "Writer Agent", "id": AGENT_ID, "role": AGENT_ROLE}

# 서버 상태 확인용 API
@app.get("/health")
async def health():
    return {"status": "healthy"}
