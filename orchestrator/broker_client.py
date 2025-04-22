"""
Broker 서비스와의 통신을 담당하는 클라이언트
"""
import logging
import httpx
import asyncio
from typing import Dict, List, Any, Optional
from .config import BROKER_URL

# 로깅 설정
logger = logging.getLogger(__name__)

class BrokerClient:
    """브로커 서비스 클라이언트"""
    
    def __init__(self, broker_url: str = BROKER_URL):
        """
        브로커 클라이언트 초기화
        
        Args:
            broker_url: 브로커 서비스 URL
        """
        self.broker_url = broker_url
        logger.info(f"브로커 클라이언트 초기화 (URL: {broker_url})")
    
    async def create_task(
        self, role: str, params: Dict[str, Any], conversation_id: str
    ) -> Dict[str, Any]:
        """
        브로커에 새 태스크 생성 요청
        
        Args:
            role: 에이전트 역할
            params: 태스크 파라미터
            conversation_id: 대화 ID
            
        Returns:
            생성된 태스크 정보
        """
        try:
            task_request = {
                "role": role,
                "params": params,
                "conversation_id": conversation_id
            }
            
            logger.info(f"태스크 생성 요청: {role} (대화 ID: {conversation_id})")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.broker_url}/tasks",
                    json=task_request,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"태스크 생성 성공: {result.get('task_id')}")
                return result
                
        except Exception as e:
            logger.error(f"태스크 생성 요청 중 오류: {str(e)}")
            raise
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        태스크 상태 조회
        
        Args:
            task_id: 태스크 ID
            
        Returns:
            태스크 상태 정보
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.broker_url}/tasks/{task_id}")
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"태스크 상태 조회 중 오류: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def wait_for_task_completion(
        self, task_id: str, timeout: int = 60, interval: int = 2
    ) -> Dict[str, Any]:
        """
        태스크 완료 대기
        
        Args:
            task_id: 태스크 ID
            timeout: 최대 대기 시간(초)
            interval: 폴링 간격(초)
            
        Returns:
            태스크 결과 정보
        """
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            task_info = await self.get_task_status(task_id)
            status = task_info.get("status")
            
            if status in ["completed", "failed", "cancelled"]:
                logger.info(f"태스크 {task_id}가 상태 '{status}'로 완료되었습니다")
                return task_info
                
            logger.debug(f"태스크 {task_id} 상태: {status}, 대기 중...")
            await asyncio.sleep(interval)
            
        logger.warning(f"태스크 {task_id}가 제한 시간({timeout}초) 내에 완료되지 않았습니다")
        return {"status": "timeout", "error": f"제한 시간 {timeout}초 초과"}
    
    async def check_health(self) -> Dict[str, Any]:
        """
        브로커 서비스 상태 확인
        
        Returns:
            상태 정보 딕셔너리
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.broker_url}/health")
                if response.status_code == 200:
                    return {"status": "healthy", "details": response.json()}
                else:
                    return {"status": "unhealthy", "details": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "unhealthy", "details": str(e)}
    
    async def create_task_with_retry(
        self, 
        role: str, 
        params: Dict[str, Any], 
        conversation_id: str,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ) -> Dict[str, Any]:
        """
        재시도 메커니즘이 적용된 태스크 생성
        
        Args:
            role: 에이전트 역할
            params: 태스크 파라미터
            conversation_id: 대화 ID
            max_retries: 최대 재시도 횟수
            backoff_factor: 재시도 간격 증가 계수
            
        Returns:
            생성된 태스크 정보
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    logger.info(f"태스크 생성 재시도 {retry_count}/{max_retries} (역할: {role})")
                    
                # 태스크 생성 시도
                result = await self.create_task(role, params, conversation_id)
                return result
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                # 최대 재시도 횟수 초과 시 예외 발생
                if retry_count > max_retries:
                    logger.error(f"최대 재시도 횟수 초과: {str(e)}")
                    raise
                    
                # 지수 백오프 적용
                wait_time = backoff_factor ** retry_count
                logger.warning(f"태스크 생성 실패, {wait_time:.1f}초 후 재시도: {str(e)}")
                await asyncio.sleep(wait_time)
        
        # 여기까지 오면 모든 재시도가 실패한 것
        raise last_error 