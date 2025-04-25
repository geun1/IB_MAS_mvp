import httpx
import json
import logging
import asyncio
from typing import Dict, Any, Optional

class AgentClient:
    def __init__(self, timeout: float = 30.0, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger("agent_client")
    
    async def execute_task(self, endpoint: str, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """에이전트 호출 및 결과 반환"""
        # 원래 엔드포인트 로깅
        self.logger.info(f"원래 엔드포인트: {endpoint}")
        
        # 엔드포인트 수정 로직
        if "code_generator" in endpoint:
            # 코드 생성기 에이전트는 /generate_code 그대로 사용
            if not endpoint.endswith('/generate_code'):
                endpoint = endpoint.replace("/run", "/generate_code")
                if not endpoint.endswith('/generate_code'):
                    endpoint = f"{endpoint}/generate_code"
                
            # 코드 생성기 요청 형식 맞춤 변환
            if task_data:
                # 원본 데이터 백업
                original_data = task_data.copy()
                
                # 코드 생성기 요청 형식으로 변환
                transformed_data = {
                    "description": original_data.get("description", ""),
                    "requirements": original_data.get("requirements", []),
                    "conversation_id": original_data.get("conversation_id", "")
                }
                
                # 설명이 없는 경우 params에서 가져오기
                if not transformed_data["description"] and "params" in original_data:
                    params = original_data.get("params", {})
                    transformed_data["description"] = params.get("description", "사칙연산 기능을 구현하는 Python 프로그램")
                    
                    # 파라미터에 요구사항이 있으면 추가
                    if "requirements" in params:
                        transformed_data["requirements"] = params.get("requirements", [])
                    else:
                        # 기본 요구사항 설정
                        transformed_data["requirements"] = ["덧셈, 뺄셈, 곱셈, 나눗셈 기능 구현", "사용자 입력 처리", "결과 출력"]
                
                # 데이터 교체
                task_data = transformed_data
                self.logger.info(f"코드 생성기 요청 데이터 변환: {task_data}")
                
        elif endpoint.endswith(':8000'):
            endpoint = f"{endpoint}/run"
        elif not endpoint.endswith('/run'):
            # URL의 마지막에 /run이 없으면 추가
            endpoint = f"{endpoint}/run"
        
        # 수정된 엔드포인트 로깅
        self.logger.info(f"수정된 엔드포인트: {endpoint}")
        
        for attempt in range(self.max_retries + 1):
            try:
                self.logger.info(f"에이전트 호출 시도 ({attempt+1}/{self.max_retries+1}): {endpoint}")
                
                # 요청 데이터 로깅
                self.logger.info(f"요청 데이터: {json.dumps(task_data, ensure_ascii=False)}")
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        endpoint,
                        json=task_data,
                        timeout=self.timeout
                    )
                    
                    # 응답 상태 코드와 본문 로깅
                    self.logger.info(f"응답 상태 코드: {response.status_code}")
                    if response.status_code != 200:
                        self.logger.error(f"응답 본문: {response.text}")
                    
                    response.raise_for_status()
                    return response.json()
                
            except Exception as e:
                # 오류 상세 로깅
                self.logger.error(f"에이전트 호출 실패: {str(e)}")
                if attempt == self.max_retries:
                    break
                await asyncio.sleep(0.5 * (attempt + 1))  # 지수 백오프
        
        return None 

    async def invoke_agent(self, agent_url: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        에이전트 호출
        
        Args:
            agent_url: 에이전트 기본 URL
            task_data: 태스크 데이터
            
        Returns:
            에이전트 응답
        """
        # 에이전트 URL 확인 및 수정
        if '/web_search_agent' in agent_url and not agent_url.endswith('/run'):
            agent_url = f"{agent_url}/run"  # 웹 검색 에이전트 실행 경로 수정
        
        # 에이전트 호출
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"에이전트 호출 시도 ({attempt}/{self.max_retries}): {agent_url}")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        agent_url,
                        json=task_data,
                        headers={"Content-Type": "application/json"}
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.TimeoutException:
                logger.warning(f"에이전트 호출 타임아웃: {agent_url}")
                await asyncio.sleep(0.5 * attempt)  # 지수 백오프
            except Exception as e:
                logger.error(f"에이전트 호출 실패: {str(e)}")
                if attempt == self.max_retries:
                    break
                await asyncio.sleep(0.5 * attempt)
        
        return None 