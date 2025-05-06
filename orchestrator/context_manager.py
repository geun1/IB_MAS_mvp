"""
대화 컨텍스트 관리 모듈
"""
import logging
import time
from typing import Dict, List, Any, Optional, Union
import redis
import json
import inspect
import uuid

logger = logging.getLogger(__name__)

class ContextManager:
    """대화 컨텍스트 관리 클래스"""
    
    def __init__(self, redis_url: str = "redis://redis:6379/0", max_history: int = 10, ttl: int = 60*60*24):
        """
        컨텍스트 관리자 초기화
        
        Args:
            redis_url: Redis 서버 URL
            max_history: 최대 대화 기록 저장 개수
            ttl: 키 만료 시간 (초)
        """
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.max_history = max_history
        self.ttl = ttl
        logger.info("컨텍스트 관리자 초기화 완료")
    
    async def save_query(self, conversation_id: str, query: str, user_id: Optional[str] = None) -> None:
        """
        사용자 쿼리 저장
        
        Args:
            conversation_id: 대화 ID
            query: 사용자 쿼리
            user_id: 사용자 ID
        """
        key = f"conv:{conversation_id}:history"
        timestamp = time.time()
        
        # 쿼리 저장
        entry = {
            "role": "user",
            "content": query,
            "timestamp": timestamp,
            "user_id": user_id
        }
        
        self.redis.lpush(key, json.dumps(entry))
        self.redis.ltrim(key, 0, (self.max_history * 2) - 1)  # 최근 N개 대화만 유지
        
        # 메타데이터 업데이트
        self.redis.hset(f"conv:{conversation_id}:meta", mapping={
            "last_update": timestamp,
            "query_count": self.redis.hincrby(f"conv:{conversation_id}:meta", "query_count", 1)
        })
    
    async def save_response(self, conversation_id: str, response: Union[Dict[str, Any], str]) -> None:
        """
        대화 응답 저장
        
        Args:
            conversation_id: 대화 ID
            response: 응답 데이터
        """
        try:
            # 기존 대화 데이터 가져오기
            conversation = await self.get_conversation(conversation_id)
            
            if not conversation:
                conversation = {"conversation_id": conversation_id, "status": "completed"}
            
            # 상태가 있으면 업데이트
            if isinstance(response, dict) and "status" in response:
                conversation["status"] = response["status"]
            else:
                conversation["status"] = "completed"  # 기본값은 완료
                
            # 응답 저장
            conversation["result"] = response

            # 쿼리가 있으면 저장
            if isinstance(response, dict) and "query" in response:
                conversation["query"] = response["query"]
                
            # 대화 관련 태스크 ID 목록도 저장 (있는 경우)
            if isinstance(response, dict) and "tasks" in response:
                conversation["tasks"] = response["tasks"]
                
            # 자연어 태스크 설명 저장 (있는 경우)
            if isinstance(response, dict) and "task_descriptions" in response:
                conversation["task_descriptions"] = response["task_descriptions"]
                
            # 태스크 분해 설명 저장 (있는 경우)
            if isinstance(response, dict) and "taskDecomposition" in response:
                conversation["taskDecomposition"] = response["taskDecomposition"]
                
            # 실행 레벨 정보 저장 (있는 경우)
            if isinstance(response, dict) and "execution_levels" in response:
                conversation["execution_levels"] = response["execution_levels"]
            
            # 최종 메시지 저장 (있는 경우)
            if isinstance(response, dict) and "message" in response:
                conversation["message"] = response["message"]
                
            # 생성 시간과 업데이트 시간 저장
            if isinstance(response, dict) and "created_at" in response:
                conversation["created_at"] = response["created_at"]
            if isinstance(response, dict) and "updated_at" in response:
                conversation["updated_at"] = response["updated_at"]
            else:
                conversation["updated_at"] = time.time()
            
            # 저장
            key = f"conversation:{conversation_id}"
            self.redis.set(key, json.dumps(conversation))
            self.redis.expire(key, self.ttl)
            
            logger.info(f"대화 ID {conversation_id}의 응답 저장 완료")
        except Exception as e:
            logger.error(f"대화 응답 저장 중 오류: {str(e)}")
    
    async def get_conversation_history(self, conversation_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        대화 기록 조회
        
        Args:
            conversation_id: 대화 ID
            limit: 최대 조회 개수
            
        Returns:
            대화 기록 목록
        """
        key = f"conv:{conversation_id}:history"
        max_items = limit if limit is not None else self.max_history * 2
        
        # Redis에서 대화 기록 가져오기
        raw_history = self.redis.lrange(key, 0, max_items - 1)
        
        # JSON 파싱 및 시간순 정렬
        history = [json.loads(item) for item in raw_history]
        history.reverse()  # 시간순 정렬
        
        return history
    
    async def format_history_for_llm(self, conversation_id: str, limit: int = 5) -> str:
        """
        LLM 프롬프트에 사용할 대화 기록 포맷팅
        
        Args:
            conversation_id: 대화 ID
            limit: 최대 대화 개수
            
        Returns:
            포맷팅된 대화 기록
        """
        history = await self.get_conversation_history(conversation_id, limit * 2)
        formatted = []
        
        for item in history:
            role = "사용자" if item["role"] == "user" else "시스템"
            formatted.append(f"{role}: {item['content']}")
        
        return "\n\n".join(formatted)

    async def list_conversations(self) -> List[Dict[str, Any]]:
        """
        모든 대화 목록 조회
        
        Returns:
            대화 목록 (ID, 상태, 마지막 업데이트 시간 등)
        """
        try:
            # Redis에서 모든 대화 키 조회 (message:* 키는 제외)
            keys = self.redis.keys("conversation:*")
            conversations = []
            
            for key in keys:
                try:
                    # conversation: 접두사를 제거하여 ID 추출
                    conversation_id = key.replace("conversation:", "")
                    
                    # UUID 형태의 유효한 conversation_id 확인 (메시지 ID와 구분)
                    is_valid_uuid = False
                    try:
                        # UUID 형식으로 변환 시도 (유효한 UUID인지 확인)
                        uuid_obj = uuid.UUID(conversation_id)
                        is_valid_uuid = True
                    except ValueError:
                        # 임의로 생성된 conversation_id 패턴 확인
                        # 예: "n3o1mx26qsuvd1saqq2oh"와 같은 형식
                        if len(conversation_id) > 20:
                            is_valid_uuid = True
                    
                    # 유효한 대화 ID인 경우에만 처리
                    if is_valid_uuid:
                        conv_data = await self.get_conversation(conversation_id)
                        
                        if conv_data:
                            # 대화 내용이 있는지 확인 (messages 필드 확인)
                            has_messages = "messages" in conv_data and len(conv_data.get("messages", [])) > 0
                            
                            # 실제 대화가 있는 경우만 포함
                            if has_messages:
                                # 요약 정보만 포함
                                summary = {
                                    "conversation_id": conversation_id,
                                    "status": conv_data.get("status", "unknown"),
                                    "created_at": conv_data.get("created_at", 0),
                                    "updated_at": conv_data.get("updated_at", 0),
                                    "query": conv_data.get("query", ""),
                                    "task_count": len(conv_data.get("tasks", []))
                                }
                                conversations.append(summary)
                except Exception as e:
                    logger.warning(f"대화 {key} 정보 로드 중 오류: {str(e)}")
            
            # 시간 역순 정렬
            conversations.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            
            return conversations
        except Exception as e:
            logger.error(f"대화 목록 조회 중 오류: {str(e)}")
            return []

    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        대화 정보 조회
        
        Args:
            conversation_id: 대화 ID
            
        Returns:
            대화 정보
        """
        try:
            key = f"conversation:{conversation_id}"
            data = self.redis.get(key)
            
            if data:
                return json.loads(data)
            return None
        
        except Exception as e:
            logger.error(f"대화 정보 조회 중 오류: {str(e)}")
            return None
    
    async def get_tasks_by_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        대화와 연관된 태스크 목록 조회
        
        Args:
            conversation_id: 대화 ID
            
        Returns:
            태스크 목록
        """
        try:
            # 대화 정보 조회
            conversation = await self.get_conversation(conversation_id)
            if not conversation:
                return []
            
            # 태스크 ID 목록 추출
            task_ids = []
            if "tasks" in conversation and isinstance(conversation["tasks"], list):
                # 태스크 정보가 배열로 되어 있는 경우
                for task_info in conversation["tasks"]:
                    if isinstance(task_info, dict) and "id" in task_info:
                        task_ids.append(task_info["id"])
                    elif isinstance(task_info, str):
                        task_ids.append(task_info)
            
            # 각 태스크 상세 정보 조회
            tasks = []
            for task_id in task_ids:
                task_key = f"task:{task_id}"
                task_data = self.redis.get(task_key)
                
                if task_data:
                    task = json.loads(task_data)
                    tasks.append(task)
                else:
                    # 태스크 정보가 없으면 기본 정보만 추가
                    tasks.append({
                        "id": task_id,
                        "status": "unknown",
                        "conversation_id": conversation_id
                    })
            
            return tasks
        
        except Exception as e:
            logger.error(f"대화 태스크 조회 중 오류: {str(e)}")
            return []

    async def create_conversation(self, user_id: Optional[str] = None) -> str:
        """
        새 대화 생성
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            생성된 대화 ID
        """
        try:
            # 대화 ID 생성
            conversation_id = str(uuid.uuid4())
            
            # 현재 시간 기록
            timestamp = time.time()
            
            # 대화 메타데이터 저장
            conversation = {
                "conversation_id": conversation_id,
                "status": "active",
                "created_at": timestamp,
                "updated_at": timestamp,
                "user_id": user_id,
                "messages": []
            }
            
            # Redis에 저장
            key = f"conversation:{conversation_id}"
            self.redis.set(key, json.dumps(conversation))
            self.redis.expire(key, self.ttl)
            
            logger.info(f"새 대화 생성: {conversation_id}")
            return conversation_id
        except Exception as e:
            logger.error(f"대화 생성 중 오류: {str(e)}")
            # 실패 시 임의의 ID 반환
            return str(uuid.uuid4())
    
    async def create_message(self, conversation_id: str, query: str, user_id: Optional[str] = None) -> str:
        """
        새 메시지 생성
        
        Args:
            conversation_id: 대화 ID
            query: 사용자 쿼리
            user_id: 사용자 ID
            
        Returns:
            생성된 메시지 ID
        """
        try:
            # 대화 정보 확인
            conversation = await self.get_conversation(conversation_id)
            if not conversation:
                # 대화가 없으면 새로 생성
                conversation_id = await self.create_conversation(user_id)
                conversation = await self.get_conversation(conversation_id)
                
            # 메시지 ID 생성
            message_id = str(uuid.uuid4())
            
            # 현재 시간 기록
            timestamp = time.time()
            
            # 메시지 저장
            message = {
                "id": message_id,
                "conversation_id": conversation_id,
                "request": query,
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "pending",
                "user_id": user_id
            }
            
            # Redis에 메시지 저장
            key = f"message:{message_id}"
            self.redis.set(key, json.dumps(message))
            self.redis.expire(key, self.ttl)
            
            # 대화 메시지 목록 업데이트
            if "messages" not in conversation:
                conversation["messages"] = []
            conversation["messages"].append(message_id)
            conversation["updated_at"] = timestamp
            
            # 대화 정보 업데이트
            conv_key = f"conversation:{conversation_id}"
            self.redis.set(conv_key, json.dumps(conversation))
            self.redis.expire(conv_key, self.ttl)
            
            logger.info(f"새 메시지 생성: {message_id} (대화: {conversation_id})")
            return message_id
        except Exception as e:
            logger.error(f"메시지 생성 중 오류: {str(e)}")
            # 실패 시 임의의 ID 반환
            return str(uuid.uuid4())
    
    async def create_message_with_id(self, message_id: str, conversation_id: str, query: str, user_id: Optional[str] = None) -> str:
        """
        클라이언트가 제공한 ID로 새 메시지 생성
        
        Args:
            message_id: 클라이언트가 제공한 메시지 ID
            conversation_id: 대화 ID
            query: 사용자 쿼리
            user_id: 사용자 ID
            
        Returns:
            사용한 메시지 ID
        """
        try:
            # 이미 존재하는지 확인
            existing = await self.get_message(message_id)
            if existing:
                logger.warning(f"메시지 ID {message_id}가 이미 존재합니다.")
                # 메시지의 대화 ID가 요청된 대화 ID와 일치하는지 확인
                if existing.get("conversation_id") != conversation_id:
                    logger.error(f"메시지 ID {message_id}가 다른 대화 ID({existing.get('conversation_id')})에 이미 연결되어 있습니다.")
                    # 새 메시지 ID 생성
                    new_message_id = str(uuid.uuid4())
                    logger.info(f"대화 ID 불일치로 새 메시지 ID 생성: {new_message_id}")
                    return await self.create_message_with_id(new_message_id, conversation_id, query, user_id)
                return message_id
            
            # 대화 정보 확인
            conversation = await self.get_conversation(conversation_id)
            if not conversation:
                # 대화가 없으면 새로 생성
                logger.warning(f"대화 ID {conversation_id}가 존재하지 않아 새로 생성합니다.")
                conversation_id = await self.create_conversation(user_id)
                conversation = await self.get_conversation(conversation_id)
                
            # 현재 시간 기록
            timestamp = time.time()
            
            # 메시지 저장
            message = {
                "id": message_id,
                "conversation_id": conversation_id,
                "request": query,
                "created_at": timestamp,
                "updated_at": timestamp,
                "status": "pending",
                "user_id": user_id
            }
            
            # Redis에 메시지 저장
            key = f"message:{message_id}"
            self.redis.set(key, json.dumps(message))
            self.redis.expire(key, self.ttl)
            
            # 대화 메시지 목록 업데이트
            if "messages" not in conversation:
                conversation["messages"] = []
            
            # 메시지 ID가 이미 대화에 있는지 확인 (중복 방지)
            if message_id not in conversation["messages"]:
                conversation["messages"].append(message_id)
                conversation["updated_at"] = timestamp
                
                # 대화 정보 업데이트
                conv_key = f"conversation:{conversation_id}"
                self.redis.set(conv_key, json.dumps(conversation))
                self.redis.expire(conv_key, self.ttl)
                
                logger.info(f"클라이언트 제공 ID로 메시지 생성: {message_id} (대화: {conversation_id})")
            else:
                logger.warning(f"메시지 ID {message_id}가 이미 대화 {conversation_id}에 있습니다.")
            
            return message_id
        except Exception as e:
            logger.error(f"클라이언트 ID 메시지 생성 중 오류: {str(e)}")
            # 오류 발생 시 새 ID 생성하여 재시도
            new_message_id = str(uuid.uuid4())
            logger.info(f"오류로 인해 새 메시지 ID 생성: {new_message_id}")
            try:
                return await self.create_message(conversation_id, query, user_id)
            except:
                return new_message_id  # 최후의 수단
    
    async def update_message(self, message_id: str, response: Dict[str, Any]) -> None:
        """
        메시지 업데이트 (응답 저장)
        
        Args:
            message_id: 메시지 ID
            response: 응답 데이터
        """
        try:
            # 메시지 정보 확인
            key = f"message:{message_id}"
            message_data = self.redis.get(key)
            
            if not message_data:
                logger.warning(f"메시지 {message_id}가 존재하지 않습니다.")
                return
                
            message = json.loads(message_data)
            
            # 메시지 업데이트
            message["response"] = response.get("message", "")
            message["status"] = "completed"
            message["updated_at"] = time.time()
            
            # 태스크 결과 저장
            if "tasks" in response:
                message["tasks"] = response["tasks"]
            
            # Redis에 메시지 업데이트
            self.redis.set(key, json.dumps(message))
            self.redis.expire(key, self.ttl)
            
            logger.info(f"메시지 {message_id} 업데이트 완료")
        except Exception as e:
            logger.error(f"메시지 업데이트 중 오류: {str(e)}")
    
    async def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        메시지 정보 조회
        
        Args:
            message_id: 메시지 ID
            
        Returns:
            메시지 정보
        """
        try:
            key = f"message:{message_id}"
            data = self.redis.get(key)
            
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"메시지 정보 조회 중 오류: {str(e)}")
            return None
    
    async def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        대화에 속한 메시지 목록 조회
        
        Args:
            conversation_id: 대화 ID
            
        Returns:
            메시지 목록
        """
        try:
            # 대화 정보 확인
            conversation = await self.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"대화 ID {conversation_id}가 존재하지 않습니다.")
                return []
                
            messages = []
            
            # 대화에 저장된 메시지 ID 목록 가져오기
            message_ids = []
            if "messages" in conversation and isinstance(conversation["messages"], list):
                message_ids = conversation["messages"]
                logger.info(f"대화 {conversation_id}에 저장된 메시지 ID: {message_ids}")
            else:
                logger.warning(f"대화 {conversation_id}에 메시지 목록이 없습니다.")
                return []
                
            # 각 메시지 정보 조회
            for message_id in message_ids:
                try:
                    message = await self.get_message(message_id)
                    if message:
                        # 메시지의 대화 ID가 요청된 대화 ID와 일치하는지 확인
                        if message.get("conversation_id") == conversation_id:
                            messages.append(message)
                        else:
                            logger.warning(f"메시지 ID {message_id}의 대화 ID가 요청된 대화 ID {conversation_id}와 일치하지 않습니다.")
                    else:
                        logger.warning(f"메시지 ID {message_id}를 찾을 수 없습니다.")
                except Exception as e:
                    logger.error(f"메시지 {message_id} 조회 중 오류 발생: {str(e)}")
                    continue
                    
            # 메시지 생성 시간 순으로 정렬
            messages.sort(key=lambda x: x.get("created_at", 0))
            
            return messages
        except Exception as e:
            logger.error(f"대화 {conversation_id}의 메시지 목록 조회 중 오류 발생: {str(e)}")
            return [] 