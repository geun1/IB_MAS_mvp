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