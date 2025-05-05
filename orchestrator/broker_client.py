"""
Broker 서비스와의 통신을 담당하는 클라이언트
"""
import logging
import httpx
import asyncio
import time
from typing import Dict, List, Any, Optional, Union
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
            
            # 컨텍스트 정보가 있는 경우 추가 및 처리
            if context:
                # 컨텍스트 구조 로깅
                logger.info(f"컨텍스트 키: {list(context.keys())}")
                task_data["context"] = context
                
                # 의존성 결과가 있는지 확인
                if "depends_results" in context:
                    depends_results = context.get("depends_results", [])
                    logger.info(f"컨텍스트에 {len(depends_results)}개의 의존성 결과 포함됨")
                    
                    # 로그에 각 의존성 결과의 구조 출력
                    for i, dep in enumerate(depends_results):
                        if not isinstance(dep, dict):
                            logger.warning(f"의존성 결과 {i+1}가 딕셔너리가 아님: {type(dep)}")
                            continue
                            
                        dep_role = dep.get("role", "unknown")
                        logger.info(f"의존성 결과 {i+1} - 역할: {dep_role}, 구조: {list(dep.keys())}")
                        
                        # 태스크 ID 정보 로깅
                        if "task_id" in dep:
                            logger.info(f"의존성 결과 {i+1} - 태스크 ID: {dep['task_id']}")
                        
                        # result 필드가 있는 경우 그 구조도 확인
                        if "result" in dep and isinstance(dep["result"], dict):
                            result_keys = list(dep["result"].keys())
                            logger.info(f"의존성 결과 {i+1}의 result 필드 구조: {result_keys}")
                            
                            # result 필드 내부의 result 필드 확인 (중첩된 구조)
                            if "result" in dep["result"] and isinstance(dep["result"]["result"], dict):
                                inner_result_keys = list(dep["result"]["result"].keys())
                                logger.info(f"의존성 결과 {i+1}의 중첩 result 필드 구조: {inner_result_keys}")
                            
                            # raw_data 필드가 있는지 확인
                            if "raw_data" in dep["result"]:
                                raw_data = dep["result"]["raw_data"]
                                raw_data_type = type(raw_data).__name__
                                if isinstance(raw_data, dict):
                                    raw_data_keys = list(raw_data.keys())
                                    logger.info(f"의존성 결과 {i+1}에 raw_data 필드가 있습니다. 타입: {raw_data_type}, 키: {raw_data_keys}")
                                else:
                                    logger.info(f"의존성 결과 {i+1}에 raw_data 필드가 있습니다. 타입: {raw_data_type}")
                                    
                            # data 필드가 있는지 확인    
                            if "data" in dep["result"]:
                                data = dep["result"]["data"]
                                data_type = type(data).__name__
                                if isinstance(data, dict):
                                    data_keys = list(data.keys())
                                    logger.info(f"의존성 결과 {i+1}에 data 필드가 있습니다. 타입: {data_type}, 키: {data_keys}")
                                else:
                                    logger.info(f"의존성 결과 {i+1}에 data 필드가 있습니다. 타입: {data_type}")
                                
                    # 특별 처리: stock_analysis 태스크인 경우 stock_data_agent 결과 직접 전달
                    if role == "stock_analysis" or role == "stock_analysis_agent":
                        # 1. 이전 결과가 stock_data_agent인지 확인하는 함수
                        def find_stock_data_result(results):
                            for i, res in enumerate(results):
                                if isinstance(res, dict):
                                    # 역할이 stock_data인 결과 찾기
                                    if res.get("role") == "stock_data":
                                        logger.info(f"stock_data 역할의 결과 발견 (인덱스: {i})")
                                        return res
                            return None
                        
                        # 2. stock_data_agent 결과 찾기
                        stock_data_result = find_stock_data_result(depends_results)
                        if stock_data_result:
                            logger.info("stock_data_agent 결과를 찾았습니다")
                            
                            # 3. result 필드 구조 확인
                            if "result" in stock_data_result and isinstance(stock_data_result["result"], dict):
                                result_data = stock_data_result["result"]
                                logger.info(f"stock_data_agent의 result 필드 구조: {list(result_data.keys())}")
                                
                                # 4. 다양한 위치에서 주식 데이터 추출 시도
                                stock_data = None
                                
                                # 4.1. raw_data 필드 확인
                                if "raw_data" in result_data and result_data["raw_data"]:
                                    stock_data = result_data["raw_data"]
                                    logger.info("raw_data 필드에서 주식 데이터 추출 성공")
                                    
                                # 4.2. data 필드 확인
                                elif "data" in result_data and result_data["data"]:
                                    stock_data = result_data["data"]
                                    logger.info("data 필드에서 주식 데이터 추출 성공")
                                    
                                # 4.3. result 내의 중첩된 필드 확인
                                elif "result" in result_data and isinstance(result_data["result"], dict):
                                    inner_result = result_data["result"]
                                    
                                    # 4.3.1. 중첩된 data 필드 확인
                                    if "data" in inner_result and inner_result["data"]:
                                        stock_data = inner_result["data"]
                                        logger.info("중첩 result.data 필드에서 주식 데이터 추출 성공")
                                    
                                    # 4.3.2. 중첩된 raw_data 필드 확인
                                    elif "raw_data" in inner_result and inner_result["raw_data"]:
                                        stock_data = inner_result["raw_data"]
                                        logger.info("중첩 result.raw_data 필드에서 주식 데이터 추출 성공")
                                
                                # 5. 데이터 추출에 성공했는지 확인 및 파라미터에 추가
                                if stock_data:
                                    data_type = type(stock_data).__name__
                                    if isinstance(stock_data, dict):
                                        logger.info(f"추출된 주식 데이터: 타입={data_type}, 키={list(stock_data.keys())}")
                                    else:
                                        logger.info(f"추출된 주식 데이터: 타입={data_type}")
                                    
                                    # 태스크 파라미터에 데이터 추가
                                    task_data["params"]["stock_data"] = stock_data
                                    task_data["params"]["source_task_id"] = stock_data_result.get("task_id", "unknown")
                                    logger.info("주식 데이터를 태스크 파라미터에 성공적으로 추가했습니다")
                                else:
                                    logger.warning("stock_data_agent 결과에서 데이터를 추출할 수 없습니다")
                                    
                                    # 원본 데이터 직접 전달
                                    task_data["params"]["source_result"] = result_data
                                    logger.info("원본 결과 데이터를 source_result 필드로 전달합니다")
                            else:
                                logger.warning("stock_data_agent 결과에 result 필드가 없거나 딕셔너리가 아닙니다")
                        else:
                            logger.warning("stock_data 역할의 결과를 찾을 수 없습니다")
                            
                            # 의존성 결과 전체를 그대로 태스크에 전달
                            task_data["depends_results"] = depends_results
                            logger.info("모든 의존성 결과를 태스크에 직접 추가했습니다")
                
                # writer 태스크인 경우 code_generator의 결과를 직접 전달
                if role == "writer":
                    # 코드 생성기 결과 처리
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
                    
                    # 웹검색 결과 처리
                    for dep_result in depends_results:
                        if dep_result.get("role") == "web_search":
                            logger.info("writer 태스크에 web_search 결과 추가 시도")
                            
                            if "result" in dep_result and isinstance(dep_result["result"], dict):
                                search_data = dep_result["result"]
                                
                                # 파라미터 초기화
                                if "params" not in task_data:
                                    task_data["params"] = {}
                                
                                # 검색 결과 데이터 추가
                                if "raw_results" in search_data:
                                    task_data["params"]["search_results"] = search_data["raw_results"]
                                    logger.info(f"writer 태스크에 검색 결과 추가됨: {len(search_data['raw_results'])}개")
                                
                                # 검색 콘텐츠 추가
                                if "content" in search_data:
                                    task_data["params"]["search_content"] = search_data["content"]
                                    logger.info("writer 태스크에 검색 콘텐츠 추가됨")
                    
                    # 항상 의존성 결과 직접 전달
                    task_data["depends_results"] = depends_results
                    logger.info("의존성 결과를 writer 태스크에 직접 추가했습니다")
            
            # 요청 데이터 로깅
            logger.info(f"브로커 요청 데이터: {task_data}")
            
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
    
    async def get_task_status(self, task_id: Union[str, Dict]) -> Dict[str, Any]:
        """
        태스크 상태 조회
        
        Args:
            task_id: 태스크 ID (문자열 또는 객체)
            
        Returns:
            태스크 상태 정보
        """
        try:
            # task_id가 객체인 경우 처리
            if isinstance(task_id, dict):
                if 'task_id' in task_id:
                    task_id = task_id['task_id']
                elif 'id' in task_id and isinstance(task_id['id'], dict) and 'task_id' in task_id['id']:
                    task_id = task_id['id']['task_id']
                elif 'id' in task_id and isinstance(task_id['id'], str):
                    task_id = task_id['id']
            
            # task_id가 여전히 딕셔너리인 경우 로그 출력 후 기본값 반환
            if isinstance(task_id, dict):
                logger.error(f"태스크 ID를 추출할 수 없습니다: {str(task_id)}")
                return {"status": "unknown", "description": "유효하지 않은 태스크 ID 형식"}
            
            # 태스크 ID만 전달하도록 수정
            async with httpx.AsyncClient() as client:
                logger.debug(f"태스크 상태 조회 요청: {task_id}")
                response = await client.get(f"{self.broker_url}/tasks/{task_id}")
                return response.json()
                
        except Exception as e:
            logger.error(f"태스크 상태 조회 중 오류: {str(e)}")
            return {"status": "unknown", "description": "태스크 정보를 가져올 수 없습니다."}
    
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