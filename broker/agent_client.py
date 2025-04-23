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
        if endpoint.endswith(':8000'):
            endpoint = f"{endpoint}/run"
        elif not endpoint.endswith('/run'):
            # URL의 마지막에 /run이 없으면 추가
            endpoint = f"{endpoint}/run"
        
        # 수정된 엔드포인트 로깅
        self.logger.info(f"수정된 엔드포인트: {endpoint}")
        
        for attempt in range(self.max_retries + 1):
            try:
                self.logger.info(f"에이전트 호출 시도 ({attempt+1}/{self.max_retries+1}): {endpoint}")
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        endpoint,
                        json=task_data,
                        timeout=self.timeout
                    )
                    
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.TimeoutException:
                self.logger.warning(f"에이전트 호출 타임아웃: {endpoint}")
                await asyncio.sleep(0.5 * attempt)  # 지수 백오프
                
            except Exception as e:
                self.logger.error(f"에이전트 호출 실패: {str(e)}")
                if attempt == self.max_retries:
                    break
                await asyncio.sleep(0.5 * attempt)
        
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