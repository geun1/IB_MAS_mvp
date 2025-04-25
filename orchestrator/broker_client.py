"""
Broker 서비스와의 통신을 담당하는 클라이언트
"""
import logging
import httpx
import asyncio
import time
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
        self, 
        role: str, 
        params: Dict[str, Any] = None, 
        conversation_id: str = None,
        context: Dict[str, Any] = None
    ) -> str:
        """
        브로커에 태스크 생성 요청
        
        Args:
            role: 에이전트 역할
            params: 태스크 파라미터
            conversation_id: 대화 ID
            context: 컨텍스트 정보 (이전 태스크 결과 등)
            
        Returns:
            태스크 ID
        """
        logger.info(f"태스크 생성 요청: {role} (대화 ID: {conversation_id})")
        
        try:
            # 태스크 요청 데이터 구성
            task_data = {
                "role": role,
                "params": params or {},
                "conversation_id": conversation_id
            }
            
            # 컨텍스트 정보가 있는 경우 추가
            if context and "depends_results" in context:
                task_data["context"] = context
                depends_results = context.get("depends_results", [])
                logger.info(f"컨텍스트에 {len(depends_results)}개의 의존성 결과 포함됨")
                
                # 태스크가 writer이고 code_generator 결과가 있는 경우, 파라미터에 코드 내용 직접 추가
                if role == "writer":
                    for dep_result in depends_results:
                        if dep_result.get("role") == "code_generator":
                            if "result" in dep_result and isinstance(dep_result["result"], dict):
                                code_data = dep_result["result"]
                                
                                # 코드 파일 내용 추출
                                if "code_files" in code_data and code_data["code_files"]:
                                    # 파라미터 초기화
                                    if "params" not in task_data:
                                        task_data["params"] = {}
                                    
                                    # 코드 파일 내용 및 설명 추가
                                    code_files = code_data["code_files"]
                                    first_file = next(iter(code_files.values())) if code_files else ""
                                    
                                    task_data["params"]["code_content"] = first_file
                                    task_data["params"]["code_explanation"] = code_data.get("explanation", "")
                                    
                                    logger.info(f"writer 태스크에 코드 내용 추가됨: {list(code_files.keys())}")
                                    break
            
            # API 요청 전송
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.broker_url}/tasks",
                    json=task_data,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.error(f"태스크 생성 실패 (상태 코드: {response.status_code}): {response.text}")
                    raise Exception(f"태스크 생성 실패: HTTP {response.status_code}")
                    
                data = response.json()
                task_id = data.get("task_id")
                
                if not task_id:
                    logger.error("응답에 태스크 ID가 없습니다")
                    raise Exception("태스크 ID를 찾을 수 없음")
                    
                logger.info(f"태스크 생성 완료: {task_id}")
                return task_id
                
        except Exception as e:
            logger.error(f"태스크 생성 요청 중 오류: {str(e)}")
            raise e
    
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
    
    async def get_task_result(self, task_id: str, timeout: float = 30.0) -> Dict[str, Any]:
        """
        태스크 결과 조회
        
        Args:
            task_id: 태스크 ID
            timeout: 타임아웃(초)
            
        Returns:
            태스크 결과
        """
        logger.info(f"태스크 결과 조회: {task_id}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.broker_url}/tasks/{task_id}",
                    timeout=timeout
                )
                
                if response.status_code != 200:
                    logger.error(f"태스크 결과 조회 오류 (상태 코드: {response.status_code}): {response.text}")
                    return {
                        "status": "failed",
                        "error": f"태스크 결과 조회 실패: HTTP {response.status_code}"
                    }
                    
                result = response.json()
                
                # 상태 확인 및 대기
                status = result.get("status")
                if status == "pending" or status == "processing":
                    logger.info(f"태스크 {task_id}는 아직 처리 중입니다. 상태: {status}")
                    # 결과 대기 (폴링 방식으로 변경)
                    return await self.wait_for_task_completion(task_id, timeout=timeout)
                
                logger.info(f"태스크 {task_id} 결과 조회 완료: {status}")
                return result
                
        except Exception as e:
            logger.error(f"태스크 결과 조회 중 오류: {str(e)}")
            return {
                "status": "failed",
                "error": f"태스크 결과 조회 중 오류: {str(e)}"
            }

    def _extract_result_content(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        태스크 결과에서 핵심 내용 추출
        
        Args:
            result: 태스크 결과 데이터
            
        Returns:
            추출된 내용
        """
        extracted = {
            "task_id": result.get("task_id", ""),
            "role": result.get("role", "unknown"),
            "description": result.get("description", "")
        }
        
        # 결과 데이터가 있는 경우
        if "result" in result:
            result_data = result["result"]
            
            # 코드 파일이 있는 경우 (code_generator)
            if isinstance(result_data, dict) and "code_files" in result_data:
                extracted["type"] = "code"
                extracted["code_files"] = result_data["code_files"]
                extracted["explanation"] = result_data.get("explanation", "")
                logger.info(f"코드 결과 추출: {list(result_data['code_files'].keys())}")
            
            # 텍스트 콘텐츠가 있는 경우 (writer)
            elif isinstance(result_data, dict) and "content" in result_data:
                extracted["type"] = "text"
                extracted["content"] = result_data["content"]
                logger.info(f"텍스트 결과 추출: {len(result_data['content'])} 자")
            
            # 검색 결과가 있는 경우 (web_search)
            elif isinstance(result_data, dict) and "search_results" in result_data:
                extracted["type"] = "search"
                extracted["search_results"] = result_data["search_results"]
                logger.info(f"검색 결과 추출: {len(result_data.get('search_results', []))}개 항목")
            
            # 기타 결과
            else:
                extracted["type"] = "other"
                extracted["data"] = result_data
                logger.info("기타 유형 결과 추출")
        
        return extracted 