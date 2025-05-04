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
app = FastAPI(title="Stock Data Agent")

# 상태 초기화
app.state.active_tasks = set()  # 활성 작업 추적을 위한 set

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # 기본값 20초
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")  # Alpha Vantage API 키
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# 모델 정의
class StockDataRequest(BaseModel):
    symbol: str
    function: str
    interval: Optional[str] = None
    series_type: Optional[str] = None
    time_period: Optional[int] = None
    datatype: Optional[str] = "json"
    output_size: Optional[str] = "compact"
    
class StockDataResponse(BaseModel):
    data: Dict[str, Any]

# 초기 등록을 위한 변수들
AGENT_ID = "stock_data_agent_1"
AGENT_ROLE = "stock_data"
AGENT_DESCRIPTION = "Alpha Vantage API를 사용하여 다양한 주식 및 금융 데이터를 제공합니다."

# 등록 태스크
async def register_agent():
    """레지스트리에 에이전트 등록"""
    try:
        # 컨테이너 외부에서 접근 가능한 엔드포인트 구성
        container_name = os.getenv("CONTAINER_NAME", "stock_data_agent")
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
                    "name": "symbol",
                    "description": "주식 심볼 (예: AAPL, MSFT, IBM)",
                    "required": True,
                    "type": "string"
                },
                {
                    "name": "function",
                    "description": "Alpha Vantage API 함수 (예: TIME_SERIES_DAILY, TIME_SERIES_INTRADAY, SMA, RSI 등)",
                    "required": True,
                    "type": "string"
                },
                {
                    "name": "interval",
                    "description": "데이터 간격 (예: 1min, 5min, 15min, 30min, 60min, daily, weekly, monthly)",
                    "required": False,
                    "type": "string"
                },
                {
                    "name": "series_type",
                    "description": "시리즈 타입 (예: close, open, high, low)",
                    "required": False,
                    "type": "string"
                },
                {
                    "name": "time_period",
                    "description": "기술 지표에 사용되는 기간 (예: SMA, EMA에 대한 시간 기간)",
                    "required": False,
                    "type": "integer"
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

# Alpha Vantage API 호출 함수
async def fetch_stock_data(params: Dict[str, str]):
    """Alpha Vantage API를 호출하여 주식 데이터 가져오기"""
    logging.info(f"Alpha Vantage API 호출: {params}")
    
    # API 키 추가
    params["apikey"] = ALPHA_VANTAGE_API_KEY
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # API 오류 확인
                if "Error Message" in data:
                    raise HTTPException(status_code=400, detail=data["Error Message"])
                
                # API 제한 확인
                if "Note" in data and "call frequency" in data["Note"]:
                    logging.warning(f"Alpha Vantage API 제한 도달: {data['Note']}")
                
                return data
            else:
                logging.error(f"Alpha Vantage API 오류: {response.status_code}, {response.text}")
                raise HTTPException(status_code=response.status_code, detail="API 호출 실패")
    
    except httpx.TimeoutException:
        logging.error("Alpha Vantage API 타임아웃")
        raise HTTPException(status_code=504, detail="API 타임아웃")
    except Exception as e:
        logging.error(f"Alpha Vantage API 호출 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API 호출 오류: {str(e)}")

# 주식 데이터 API
@app.post("/get_stock_data")
async def get_stock_data(request: StockDataRequest):
    try:
        # API 파라미터 구성
        params = {"function": request.function, "symbol": request.symbol}
        
        # 선택적 파라미터 추가
        if request.interval:
            params["interval"] = request.interval
        if request.series_type:
            params["series_type"] = request.series_type
        if request.time_period:
            params["time_period"] = str(request.time_period)
        if request.datatype:
            params["datatype"] = request.datatype
        if request.output_size:
            params["outputsize"] = request.output_size
        
        # Alpha Vantage API 호출
        data = await fetch_stock_data(params)
        
        return {"data": data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stock data fetch failed: {str(e)}")

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
        
        # 컨텍스트 데이터 확인 (다른 태스크에서 전달받은 데이터가 있는지)
        context = task.get("context", {})
        if context:
            logging.info(f"컨텍스트 데이터가 전달되었습니다: {list(context.keys())}")
        
        symbol = params.get("symbol", "")
        function = params.get("function", "")
        interval = params.get("interval", None)
        series_type = params.get("series_type", None)
        time_period = params.get("time_period", None)
        
        # 필수 파라미터 검증
        if not symbol or not function:
            logging.warning(f"태스크 {task_id}: 필수 파라미터 누락")
            return {
                "status": "error",
                "error": "필수 파라미터(symbol, function)가 제공되지 않았습니다",
                "result": {
                    "data": None
                }
            }
        
        # API 파라미터 구성
        api_params = {"function": function, "symbol": symbol}
        
        # 선택적 파라미터 추가
        if interval:
            api_params["interval"] = interval
        if series_type:
            api_params["series_type"] = series_type
        if time_period:
            api_params["time_period"] = str(time_period)
        
        # Alpha Vantage API 호출
        logging.info(f"Alpha Vantage API 호출 시작 (태스크: {task_id})")
        logging.info(f"API 호출 파라미터: {api_params}")
        stock_data = await fetch_stock_data(api_params)
        
        # 데이터 로깅
        logging.info(f"수신된 주식 데이터 구조: {list(stock_data.keys()) if isinstance(stock_data, dict) else type(stock_data)}")
        
        # 결과 반환 - 객체 형태로 직접 전달
        result = {
            "status": "success",
            "result": {
                "data": stock_data,
                "raw_data": stock_data  # 객체 형태로 직접 전달하는 필드 추가
            }
        }
        
        logging.info(f"태스크 {task_id} 처리 완료, 데이터 크기: {len(str(stock_data))} 바이트")
        return result
    
    except Exception as e:
        logging.error(f"태스크 실행 중 오류: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "result": {
                "data": None
            }
        }

# 건강 확인 API
@app.get("/health")
async def health():
    """Health check 엔드포인트"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agent_id": AGENT_ID,
        "agent_role": AGENT_ROLE
    }

# 루트 API
@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "agent": AGENT_ROLE,
        "description": AGENT_DESCRIPTION,
        "status": "running"
    }

# 종료 이벤트
@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 이벤트"""
    logging.info("애플리케이션 종료 중...")
    
    # 필요한 정리 작업 수행
    try:
        # 레지스트리에 상태 변경 알림 (선택사항)
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{REGISTRY_URL}/status/{AGENT_ROLE}/{AGENT_ID}",
                json={"status": "offline"}
            )
    except Exception as e:
        logging.error(f"종료 처리 중 오류: {str(e)}") 