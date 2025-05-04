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
import pandas as pd
import numpy as np
from common.llm_client import LLMClient  # LLM 클라이언트 추가

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="Stock Analysis Agent")

# 상태 초기화
app.state.active_tasks = set()  # 활성 작업 추적을 위한 set

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # 기본값 20초

# 모델 정의
class StockAnalysisRequest(BaseModel):
    stock_data: Dict[str, Any]  # JSON 형태의 주식 데이터
    analysis_type: str = "general"  # 분석 유형 (general, technical, fundamental 등)
    timeframe: Optional[str] = None  # 분석 기간 (daily, weekly, monthly 등)
    indicators: Optional[List[str]] = None  # 분석에 사용할 지표 (예: MACD, RSI, EMA 등)

class StockAnalysisResponse(BaseModel):
    analysis: str
    charts: Optional[Dict[str, Any]] = None

# 초기 등록을 위한 변수들
AGENT_ID = "stock_analysis_agent_1"
AGENT_ROLE = "stock_analysis"
AGENT_DESCRIPTION = "주어진 주식 데이터를 분석하고 인사이트를 추출하여 제공합니다. 데이터에만 기반하여 객관적이고 정확한 분석을 수행합니다."

# 등록 태스크
async def register_agent():
    """레지스트리에 에이전트 등록"""
    try:
        # 컨테이너 외부에서 접근 가능한 엔드포인트 구성
        container_name = os.getenv("CONTAINER_NAME", "stock_analysis_agent")
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
                    "name": "stock_data",
                    "description": "분석할 주식 데이터 (JSON 형식)",
                    "required": True,
                    "type": "object"
                },
                {
                    "name": "analysis_type",
                    "description": "수행할 분석 유형 (general, technical, fundamental 등)",
                    "required": False,
                    "type": "string"
                },
                {
                    "name": "timeframe",
                    "description": "분석 기간 (daily, weekly, monthly 등)",
                    "required": False,
                    "type": "string"
                },
                {
                    "name": "indicators",
                    "description": "분석에 사용할 기술적 지표 목록",
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
                    "active_tasks": len(app.state.active_tasks)
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

# 주식 데이터 분석 헬퍼 함수
def analyze_stock_data(stock_data: Dict[str, Any], analysis_type: str = "general", 
                      timeframe: Optional[str] = None, indicators: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    주식 데이터 분석 수행
    
    Args:
        stock_data: 분석할 주식 데이터
        analysis_type: 분석 유형 (general, technical, fundamental)
        timeframe: 분석 기간 (daily, weekly, monthly)
        indicators: 분석에 사용할 기술적 지표 목록
        
    Returns:
        분석 결과 딕셔너리
    """
    try:
        # 문자열로 들어온 경우 처리
        if isinstance(stock_data, str):
            logging.warning(f"문자열 형태의 stock_data 수신됨: {stock_data}")
            return {"error": "주식 데이터가 문자열 형태로 제공되었습니다. 유효한 JSON 데이터가 필요합니다."}
        
        # 데이터가 Time Series 형태인지 확인 (Alpha Vantage API 형식)
        time_series_key = next((k for k in stock_data.keys() if "Time Series" in k), None)
        
        if time_series_key:
            # Time Series 데이터 구조 (Alpha Vantage API 형식)
            time_series_data = stock_data[time_series_key]
            
            # 날짜와 가격 데이터 추출
            dates = list(time_series_data.keys())
            if not dates:
                return {"error": "유효한 시계열 데이터가 없습니다."}
                
            # 최신 날짜부터 정렬
            dates.sort(reverse=True)
            
            # 데이터 저장을 위한 리스트 생성
            data_rows = []
            
            for date in dates:
                daily_data = time_series_data[date]
                # Alpha Vantage API 응답의 일반적인 키 이름
                open_key = next((k for k in daily_data.keys() if "open" in k.lower()), None)
                high_key = next((k for k in daily_data.keys() if "high" in k.lower()), None)
                low_key = next((k for k in daily_data.keys() if "low" in k.lower()), None)
                close_key = next((k for k in daily_data.keys() if "close" in k.lower()), None)
                volume_key = next((k for k in daily_data.keys() if "volume" in k.lower()), None)
                
                if all([open_key, high_key, low_key, close_key]):
                    data_rows.append({
                        "date": date,
                        "open": float(daily_data[open_key]),
                        "high": float(daily_data[high_key]),
                        "low": float(daily_data[low_key]),
                        "close": float(daily_data[close_key]),
                        "volume": int(daily_data[volume_key]) if volume_key else 0
                    })
            
            # 데이터프레임 생성 (리스트에서 한 번에 생성)
            df = pd.DataFrame(data_rows)
            
            # 가격 변동 계산
            if len(df) >= 2:
                latest_price = df.iloc[0]["close"]
                prev_price = df.iloc[1]["close"]
                price_change = latest_price - prev_price
                price_change_pct = (price_change / prev_price) * 100
                
                # 이동평균 계산
                if len(df) >= 5:
                    df["MA5"] = df["close"].rolling(window=5).mean()
                
                if len(df) >= 20:
                    df["MA20"] = df["close"].rolling(window=20).mean()
                
                if len(df) >= 50:
                    df["MA50"] = df["close"].rolling(window=50).mean()
                
                # 기본 분석 결과
                analysis_results = {
                    "symbol": next((v for k, v in stock_data.get("Meta Data", {}).items() if "Symbol" in k), "Unknown"),
                    "latest_date": dates[0],
                    "latest_price": float(latest_price),
                    "price_change": float(price_change),
                    "price_change_pct": float(price_change_pct),
                    "period": f"{dates[-1]} ~ {dates[0]}",
                    "data_points": int(len(dates)),
                    "min_price": float(df["low"].min()),
                    "max_price": float(df["high"].max()),
                    "avg_price": float(df["close"].mean())
                }
                
                # 이동평균 관련 분석
                if "MA20" in df.columns and "MA50" in df.columns:
                    latest_ma20 = df.iloc[0]["MA20"] if not pd.isna(df.iloc[0]["MA20"]) else None
                    latest_ma50 = df.iloc[0]["MA50"] if not pd.isna(df.iloc[0]["MA50"]) else None
                    
                    if latest_ma20 and latest_ma50:
                        analysis_results["ma_trend"] = "상승" if latest_ma20 > latest_ma50 else "하락"
                
                # 볼륨 분석
                if "volume" in df.columns:
                    analysis_results["avg_volume"] = float(df["volume"].mean())
                    analysis_results["latest_volume"] = int(df.iloc[0]["volume"])
                    
                    if len(df) >= 5:
                        avg_vol_5d = float(df.iloc[:5]["volume"].mean())
                        analysis_results["volume_trend"] = "증가" if df.iloc[0]["volume"] > avg_vol_5d else "감소"
                
                return analysis_results
            else:
                return {"error": "충분한 시계열 데이터가 없습니다."}
        
        # Global Quote 형식 확인 (Alpha Vantage API)
        elif "Global Quote" in stock_data:
            quote = stock_data["Global Quote"]
            symbol = quote.get("01. symbol", "Unknown")
            price = float(quote.get("05. price", 0))
            change = float(quote.get("09. change", 0))
            change_percent = quote.get("10. change percent", "0%").replace("%", "")
            
            return {
                "symbol": symbol,
                "price": price,
                "change": change,
                "change_percent": float(change_percent),
                "latest_trading_day": quote.get("07. latest trading day", "Unknown"),
                "volume": int(quote.get("06. volume", 0)),
                "previous_close": float(quote.get("08. previous close", 0))
            }
        
        # 기술 지표 데이터 (Alpha Vantage Technical Indicators)
        elif "Technical Analysis" in stock_data:
            indicator_type = next((k for k in stock_data.keys() if k != "Technical Analysis" and k != "Meta Data"), "Unknown")
            indicator_data = stock_data["Technical Analysis"][indicator_type]
            
            dates = list(indicator_data.keys())
            dates.sort(reverse=True)
            
            result = {
                "indicator": indicator_type,
                "latest_date": dates[0] if dates else "Unknown",
                "values": []
            }
            
            for date in dates[:10]:  # 최근 10개 데이터만 포함
                result["values"].append({
                    "date": date,
                    "value": float(indicator_data[date][indicator_type])
                })
                
            return result
        
        # 그 외 모든 데이터는 기본 구조로 반환
        else:
            return {"data": stock_data, "message": "데이터 구조를 인식할 수 없어 원본 데이터를 반환합니다."}
            
    except Exception as e:
        logging.error(f"주식 데이터 분석 중 오류: {str(e)}")
        return {"error": f"분석 중 오류 발생: {str(e)}"}

# 주식 분석 API
@app.post("/analyze_stock")
async def analyze_stock(request: StockAnalysisRequest):
    try:
        # 주식 데이터 분석 수행
        analysis_result = analyze_stock_data(
            request.stock_data, 
            request.analysis_type,
            request.timeframe,
            request.indicators
        )
        
        # 분석 결과 기반 텍스트 생성
        analysis_text = generate_analysis_text(analysis_result, request.analysis_type)
        
        return {
            "analysis": analysis_text,
            "charts": None  # 차트 생성 기능은 향후 구현 가능
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stock analysis failed: {str(e)}")

# 분석 텍스트 생성 함수
def generate_analysis_text(analysis_result: Dict[str, Any], analysis_type: str) -> str:
    """
    분석 결과를 기반으로 설명 텍스트 생성
    
    Args:
        analysis_result: 분석 결과 데이터
        analysis_type: 분석 유형
        
    Returns:
        분석 설명 텍스트
    """
    if "error" in analysis_result:
        return f"분석 오류: {analysis_result['error']}"
    
    # 분석 결과를 JSON 문자열로 변환
    analysis_json = json.dumps(analysis_result, indent=2, ensure_ascii=False)
    
    # LLM 클라이언트 초기화
    llm = LLMClient(temperature=0.3)  # 할루시네이션 최소화를 위해 낮은 temperature 설정
    
    # 시스템 프롬프트 - 할루시네이션 방지를 위한 지침 포함
    system_prompt = """
    당신은 주식 데이터 분석 전문가입니다. 제공된 데이터만을 기반으로 객관적이고 사실에 근거한 분석을 제공해야 합니다.
    
    지침:
    1. 제공된 데이터에 명시적으로 포함된 정보만 사용하세요.
    2. 데이터에 포함되지 않은 정보에 대해서는 추측하거나 예측하지 마세요.
    3. 주가 전망이나 투자 조언은 제공하지 마세요.
    4. 모든 수치는 정확하게 인용하고, 반올림할 경우 명시하세요.
    5. 분석은 간결하게 구조화된 형식으로 제공하세요.
    6. 투자에 대한 책임은 개인에게 있음을 항상 명시하세요.
    
    형식:
    - 주식 심볼과 기본 정보 요약
    - 가격 변동 분석 (제공된 경우)
    - 기술적 지표 분석 (제공된 경우)
    - 거래량 분석 (제공된 경우)
    - 주의사항
    """
    
    # 프롬프트 구성 - 데이터 구조에 따라 다른 형식으로 요청
    prompt = f"""
    다음 주식 데이터 분석 결과를 바탕으로 객관적이고 명확한 분석 보고서를 작성해주세요:
    
    ```json
    {analysis_json}
    ```
    
    분석 유형: {analysis_type}
    
    데이터에 제시된 수치와 지표만 사용하여 분석하고, 명시되지 않은 정보나 미래 예측은 피해주세요.
    결과는 구조화된 형식으로 제공하되, 투자 결정은 개인의 책임임을 강조해주세요.
    """
    
    try:
        # LLM 호출
        analysis_text = llm.ask(prompt, system_prompt=system_prompt)
        return analysis_text
    except Exception as e:
        logging.error(f"LLM 호출 중 오류: {str(e)}")
        # 오류 발생 시 기본 텍스트 생성 로직으로 폴백
        return fallback_generate_analysis_text(analysis_result, analysis_type)

# 폴백 텍스트 생성 함수 (LLM 호출 실패 시 사용)
def fallback_generate_analysis_text(analysis_result: Dict[str, Any], analysis_type: str) -> str:
    """
    LLM 호출 실패 시 사용할 기본 텍스트 생성 함수
    
    Args:
        analysis_result: 분석 결과 데이터
        analysis_type: 분석 유형
        
    Returns:
        분석 설명 텍스트
    """
    # Time Series 데이터 분석 결과 처리
    if "symbol" in analysis_result and "latest_price" in analysis_result:
        symbol = analysis_result["symbol"]
        latest_price = analysis_result["latest_price"]
        price_change = analysis_result.get("price_change", 0)
        price_change_pct = analysis_result.get("price_change_pct", 0)
        
        # 텍스트 생성
        text = f"{symbol} 주식 분석 결과입니다.\n\n"
        text += f"현재 가격: {latest_price:.2f}\n"
        
        if price_change >= 0:
            text += f"전일 대비: +{price_change:.2f} (+{price_change_pct:.2f}%)\n"
        else:
            text += f"전일 대비: {price_change:.2f} ({price_change_pct:.2f}%)\n"
        
        text += f"분석 기간: {analysis_result.get('period', '데이터 없음')}\n"
        text += f"최저가: {analysis_result.get('min_price', '데이터 없음'):.2f}\n"
        text += f"최고가: {analysis_result.get('max_price', '데이터 없음'):.2f}\n"
        text += f"평균가: {analysis_result.get('avg_price', '데이터 없음'):.2f}\n\n"
        
        # 이동평균 추세 분석
        if "ma_trend" in analysis_result:
            text += f"이동평균 추세: {analysis_result['ma_trend']}\n"
            text += "20일 이동평균이 50일 이동평균보다 " + ("높으면 단기 상승 추세, " if analysis_result['ma_trend'] == "상승" else "낮으면 단기 하락 추세를 ") + "의미합니다.\n\n"
        
        # 거래량 분석
        if "avg_volume" in analysis_result and "latest_volume" in analysis_result:
            text += f"최근 거래량: {analysis_result['latest_volume']:,}\n"
            text += f"평균 거래량: {analysis_result['avg_volume']:,.0f}\n"
            
            if "volume_trend" in analysis_result:
                text += f"거래량 추세: {analysis_result['volume_trend']}\n"
                text += "최근 거래량이 5일 평균 거래량보다 " + ("높으면 투자자 관심도가 증가하고 있음을 " if analysis_result['volume_trend'] == "증가" else "낮으면 투자자 관심도가 감소하고 있음을 ") + "나타낼 수 있습니다.\n\n"
        
        text += "※ 이 분석은 제공된 데이터만을 기반으로 한 객관적 지표이며, 투자 권유가 아닙니다. 투자 결정은 항상 개인의 판단과 추가적인 리서치를 기반으로 이루어져야 합니다."
        
        return text
    
    # Global Quote 데이터 처리
    elif "symbol" in analysis_result and "price" in analysis_result:
        symbol = analysis_result["symbol"]
        price = analysis_result["price"]
        change = analysis_result["change"]
        change_percent = analysis_result["change_percent"]
        
        text = f"{symbol} 주식 실시간 시세 분석입니다.\n\n"
        text += f"현재 가격: {price:.2f}\n"
        
        if change >= 0:
            text += f"전일 대비: +{change:.2f} (+{change_percent:.2f}%)\n"
        else:
            text += f"전일 대비: {change:.2f} ({change_percent:.2f}%)\n"
        
        text += f"거래일: {analysis_result.get('latest_trading_day', '정보 없음')}\n"
        text += f"거래량: {analysis_result.get('volume', 0):,}\n"
        text += f"전일 종가: {analysis_result.get('previous_close', 0):.2f}\n\n"
        
        text += "※ 이 분석은 제공된 데이터만을 기반으로 한 객관적 시세 정보이며, 투자 권유가 아닙니다."
        
        return text
        
    # 기술 지표 데이터 처리
    elif "indicator" in analysis_result:
        indicator = analysis_result["indicator"]
        latest_date = analysis_result["latest_date"]
        values = analysis_result.get("values", [])
        
        text = f"{indicator} 기술 지표 분석입니다.\n\n"
        text += f"기준일: {latest_date}\n\n"
        
        if values:
            text += "최근 데이터:\n"
            for value in values[:5]:  # 최근 5개 데이터만 표시
                text += f"- {value['date']}: {value['value']:.4f}\n"
            
            # 간단한 추세 분석
            if len(values) >= 2:
                latest_value = values[0]["value"]
                prev_value = values[1]["value"]
                if latest_value > prev_value:
                    text += f"\n{indicator} 지표가 증가하고 있습니다."
                elif latest_value < prev_value:
                    text += f"\n{indicator} 지표가 감소하고 있습니다."
                else:
                    text += f"\n{indicator} 지표가 유지되고 있습니다."
        
        text += "\n\n※ 이 분석은 제공된 데이터만을 기반으로 한 기술적 지표이며, 투자 권유가 아닙니다."
        
        return text
    
    # 그 외 케이스
    else:
        return "제공된 데이터로는 상세한 분석을 수행할 수 없습니다. 데이터 형식이 지원되지 않거나 충분한 정보가 포함되어 있지 않습니다."

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
        stock_data = params.get("stock_data", {})
        analysis_type = params.get("analysis_type", "general")
        timeframe = params.get("timeframe", None)
        indicators = params.get("indicators", None)
        source_task_id = params.get("source_task_id", "unknown")
        
        # 데이터 소스 로깅
        logging.info(f"수신된 stock_data 정보: 타입={type(stock_data).__name__}, 비어있음={not stock_data if isinstance(stock_data, dict) else False}")
        if isinstance(stock_data, dict) and stock_data:
            logging.info(f"stock_data 키: {list(stock_data.keys())}")
        
        # depends_results 파라미터가 있는 경우 (직접 전달된 경우)
        depends_results_param = params.get("depends_results", [])
        if depends_results_param:
            logging.info(f"params를 통해 직접 전달된 의존성 결과: {len(depends_results_param)}개")
            
        # 태스크에 직접 추가된 의존성 결과 확인
        depends_results = task.get("depends_results", [])
        if depends_results:
            logging.info(f"task에 직접 추가된 의존성 결과: {len(depends_results)}개")
        
        # context 필드를 통해 전달된 의존성 결과 확인
        context_depends = []
        if "context" in task and isinstance(task["context"], dict):
            context_depends = task["context"].get("depends_results", [])
            if context_depends:
                logging.info(f"context를 통해 전달된 의존성 결과: {len(context_depends)}개")
        
        # 모든 의존성 결과 통합
        all_depends_results = []
        all_depends_results.extend(depends_results)
        
        if not all_depends_results and context_depends:
            all_depends_results.extend(context_depends)
            logging.info(f"context에서 의존성 결과 {len(context_depends)}개를 통합했습니다")
            
        if not all_depends_results and depends_results_param:
            all_depends_results.extend(depends_results_param)
            logging.info(f"params에서 의존성 결과 {len(depends_results_param)}개를 통합했습니다")
            
        logging.info(f"최종 처리할 의존성 결과: {len(all_depends_results)}개")
        
        # 의존성 데이터 상세 로깅
        if all_depends_results:
            for i, dep_result in enumerate(all_depends_results):
                if isinstance(dep_result, dict):
                    result_role = dep_result.get("role", "unknown")
                    logging.info(f"의존성 {i+1} - 역할: {result_role}, 키: {list(dep_result.keys())}")
                    
                    if "result" in dep_result and isinstance(dep_result["result"], dict):
                        result_keys = list(dep_result["result"].keys())
                        logging.info(f"의존성 {i+1} - result 필드 키: {result_keys}")
                        
                        # raw_data 필드 확인
                        if "raw_data" in dep_result["result"]:
                            raw_data = dep_result["result"]["raw_data"]
                            raw_data_type = type(raw_data).__name__
                            raw_data_info = list(raw_data.keys()) if isinstance(raw_data, dict) else f"비딕셔너리 타입({raw_data_type})"
                            logging.info(f"의존성 {i+1} - raw_data: {raw_data_info}")
                        
                        # data 필드 확인
                        if "data" in dep_result["result"]:
                            data = dep_result["result"]["data"]
                            data_type = type(data).__name__
                            data_info = list(data.keys()) if isinstance(data, dict) else f"비딕셔너리 타입({data_type})"
                            logging.info(f"의존성 {i+1} - data: {data_info}")
                else:
                    logging.info(f"의존성 {i+1} - 비딕셔너리 타입: {type(dep_result)}")
        
        # 의존성 데이터에서 stock_data_agent 결과 추출 (stock_data가 비어있는 경우)
        if not stock_data or (isinstance(stock_data, dict) and not stock_data):
            logging.info("stock_data가 비어있어 의존성 결과에서 데이터를 추출합니다")
            for dep_result in all_depends_results:
                if not isinstance(dep_result, dict):
                    continue
                    
                result_role = dep_result.get("role", "unknown")
                logging.info(f"의존성 결과 역할 확인: {result_role}")
                
                # stock_data_agent의 결과 데이터 확인
                if "result" in dep_result and isinstance(dep_result["result"], dict):
                    result_data = dep_result["result"]
                    
                    # raw_data 필드가 있는 경우 (객체 형태로 직접 전달)
                    if "raw_data" in result_data and result_data["raw_data"]:
                        extracted_data = result_data["raw_data"]
                        logging.info(f"raw_data 필드에서 주식 데이터 추출 (타입: {type(extracted_data).__name__})")
                        
                        if extracted_data:
                            stock_data = extracted_data
                            logging.info("raw_data에서 주식 데이터 추출 성공")
                            break
                    
                    # data 필드가 있는 경우 (일반적인 응답 형식)
                    elif "data" in result_data and result_data["data"]:
                        extracted_data = result_data["data"]
                        logging.info(f"data 필드에서 주식 데이터 추출 (타입: {type(extracted_data).__name__})")
                        
                        if extracted_data:
                            stock_data = extracted_data
                            logging.info("data 필드에서 주식 데이터 추출 성공")
                            break
                    
                    # 결과 자체에 필요한 데이터가 있는 경우 (다른 형태의 응답)
                    elif len(result_data) > 0:
                        # 결과에 Time Series와 같은 주식 데이터 키가 있는지 확인
                        time_series_key = next((k for k in result_data.keys() if k.startswith("Time Series")), None)
                        meta_data_key = "Meta Data" in result_data
                        
                        if time_series_key or meta_data_key:
                            logging.info("결과에서 주식 데이터 직접 발견")
                            stock_data = result_data
                            break
                
                # 결과가 직접 데이터인 경우 (예외 케이스)
                elif "result" in dep_result and dep_result["result"] is not None:
                    result_val = dep_result["result"]
                    if isinstance(result_val, dict) and len(result_val) > 0:
                        # 결과에 Time Series와 같은 주식 데이터 키가 있는지 확인
                        time_series_key = next((k for k in result_val.keys() if k.startswith("Time Series")), None)
                        meta_data_key = "Meta Data" in result_val
                        
                        if time_series_key or meta_data_key:
                            logging.info("result에서 주식 데이터 직접 발견")
                            stock_data = result_val
                            break
        
        # 최종 데이터 로깅
        logging.info(f"분석에 사용할 최종 stock_data 타입: {type(stock_data).__name__}")
        if isinstance(stock_data, dict):
            logging.info(f"최종 stock_data 키: {list(stock_data.keys())}")
        
        # 주식 데이터 유효성 검사
        if stock_data is None or (isinstance(stock_data, dict) and not stock_data):
            logging.warning(f"태스크 {task_id}: 주식 데이터가 없습니다")
            return {
                "status": "error",
                "error": "주식 데이터가 제공되지 않았거나 비어 있습니다",
                "result": {
                    "analysis": "분석할 주식 데이터가 없습니다. 주식 데이터를 제공해주세요.",
                    "source_task_id": source_task_id
                }
            }
            
        # 문자열인 경우 처리
        if isinstance(stock_data, str):
            logging.warning(f"태스크 {task_id}: 문자열 형태의 주식 데이터를 변환 시도합니다")
            
            # 줄바꿈 정보 로깅 (객체 디버깅에 유용)
            if "\n" in stock_data:
                line_count = stock_data.count("\n") + 1
                logging.info(f"문자열에 줄바꿈이 포함되어 있습니다 (줄 수: {line_count})")
            
            try:
                # JSON 문자열인지 확인하고 파싱 시도
                if stock_data.strip().startswith('{') and stock_data.strip().endswith('}'):
                    try:
                        parsed_data = json.loads(stock_data)
                        if isinstance(parsed_data, dict):
                            logging.info("문자열에서 JSON 객체로 변환 성공")
                            stock_data = parsed_data
                            
                            # 파싱된 데이터의 키 확인
                            logging.info(f"파싱된 JSON 키: {list(stock_data.keys())}")
                        else:
                            logging.warning("파싱된 데이터가 딕셔너리가 아닙니다")
                    except json.JSONDecodeError as e:
                        logging.warning(f"JSON 파싱 실패: {str(e)}")
                        # 문자열 일부만 로깅 (너무 길 수 있으므로)
                        preview = stock_data[:100] + "..." if len(stock_data) > 100 else stock_data
                        logging.info(f"파싱 실패한 문자열 시작 부분: {preview}")
                
                # 문자열 형태의 주식 데이터 분석
                if isinstance(stock_data, str):
                    # LLM 클라이언트 초기화
                    llm_client = LLMClient()
                    
                    # 프롬프트 구성
                    system_prompt = """
                    당신은 주식 데이터 분석 전문가입니다. 제공된 주식 데이터를 분석하고 통찰력 있는 결론을 도출해야 합니다.
                    데이터는 문자열 형태로 제공됩니다. 이를 신중히 분석하고, 다음 항목에 대한 분석을 제공하세요:
                    1. 주식 심볼/이름
                    2. 현재 가격 및 변동폭
                    3. 최근 거래량
                    4. 주요 추세
                    5. 기술적 지표의 의미
                    
                    할루시네이션을 피하고 데이터에서 명확하게 확인할 수 있는 정보만 분석하세요.
                    데이터에 없는 정보에 대해서는 '해당 정보 없음'이라고 명시하세요.
                    """
                    
                    # 사용자 프롬프트 구성
                    user_prompt = f"""
                    다음 주식 데이터를 분석해주세요:
                    
                    {stock_data}
                    
                    분석 유형: {analysis_type}
                    """
                    
                    # LLM을 통한 분석
                    try:
                        analysis_text = await llm_client.aask(user_prompt, system_prompt=system_prompt)
                        logging.info("LLM을 통한 분석 완료")
                        
                        return {
                            "status": "success",
                            "result": {
                                "analysis": analysis_text,
                                "data_source": "LLM 분석 (문자열 데이터)",
                                "source_task_id": source_task_id
                            }
                        }
                    except Exception as e:
                        logging.error(f"LLM 분석 중 오류: {str(e)}")
                        return {
                            "status": "error",
                            "error": f"LLM 분석 중 오류가 발생했습니다: {str(e)}",
                            "result": {
                                "analysis": "주식 데이터 분석에 실패했습니다.",
                                "source_task_id": source_task_id
                            }
                        }
            except Exception as e:
                logging.error(f"문자열 데이터 처리 중 오류: {str(e)}")
                
                # 응급 조치: 문자열 그대로 반환
                return {
                    "status": "success",
                    "result": {
                        "analysis": f"제공된 데이터는 분석하기 어려운 형식입니다. 원본 데이터: {stock_data[:200]}...",
                        "error": str(e),
                        "source_task_id": source_task_id
                    }
                }
        
        # 딕셔너리가 아닌 경우
        if not isinstance(stock_data, dict):
            logging.warning(f"태스크 {task_id}: 주식 데이터가 딕셔너리가 아닙니다 ({type(stock_data).__name__})")
            
            # 문자열로 변환하여 LLM 분석 시도
            try:
                str_data = str(stock_data)
                llm_client = LLMClient()
                system_prompt = "주식 데이터 분석 전문가로서, 제공된 데이터를 분석하세요. 데이터에 없는 정보는 추측하지 마세요."
                user_prompt = f"다음 데이터를 분석해주세요:\n\n{str_data}"
                
                analysis_text = await llm_client.aask(user_prompt, system_prompt=system_prompt)
                return {
                    "status": "success",
                    "result": {
                        "analysis": analysis_text,
                        "data_source": "LLM 분석 (비정형 데이터)",
                        "source_task_id": source_task_id
                    }
                }
            except Exception as e:
                logging.error(f"비정형 데이터 분석 중 오류: {str(e)}")
                return {
                    "status": "error",
                    "error": f"비정형 데이터 처리 중 오류: {str(e)}",
                    "result": {
                        "analysis": "지원되지 않는 데이터 형식입니다.",
                        "source_task_id": source_task_id
                    }
                }
        
        # 이 지점에서 stock_data는 딕셔너리 형태임을 보장
        logging.info(f"분석할 주식 데이터 구조: {list(stock_data.keys())}")
        
        # 주식 데이터 분석
        analysis_result = analyze_stock_data(stock_data, analysis_type, timeframe, indicators)
        
        # 분석 결과를 텍스트로 변환
        analysis_text = generate_analysis_text(analysis_result, analysis_type)
        
        # 결과 반환
        return {
            "status": "success",
            "result": {
                "analysis": analysis_text,
                "data": analysis_result,
                "source_task_id": source_task_id
            }
        }
    
    except Exception as e:
        logging.error(f"태스크 실행 중 오류: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "result": {
                "analysis": f"주식 데이터 분석 중 오류가 발생했습니다: {str(e)}"
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