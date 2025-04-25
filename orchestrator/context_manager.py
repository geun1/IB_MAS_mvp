"""
대화 컨텍스트 관리 모듈
"""
import logging
import time
from typing import Dict, List, Any, Optional, Union
import redis
import json
import inspect

logger = logging.getLogger(__name__)

class ContextManager:
    """대화 컨텍스트 관리 클래스"""
    
    def __init__(self, redis_url: str = "redis://redis:6379/0", max_history: int = 10):
        """
        컨텍스트 관리자 초기화
        
        Args:
            redis_url: Redis 서버 URL
            max_history: 최대 대화 기록 저장 개수
        """
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.max_history = max_history
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
            
            # 대화 관련 태스크 ID 목록도 저장 (있는 경우)
            if isinstance(response, dict) and "tasks" in response:
                conversation["tasks"] = response["tasks"]
            
            # 저장
            key = f"conversation:{conversation_id}"
            await self.redis.set(key, json.dumps(conversation))
            # Redis의 expire는 동기 함수가 아닌 경우가 있으므로 조건부 await 추가
            if inspect.iscoroutinefunction(self.redis.expire):
                await self.redis.expire(key, self.ttl)  # TTL 설정
            else:
                self.redis.expire(key, self.ttl)  # TTL 설정 (동기 함수인 경우)
            
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
            # Redis에서 모든 대화 키 조회
            keys = self.redis.keys("conversation:*")
            conversations = []
            
            for key in keys:
                try:
                    conversation_id = key.replace("conversation:", "")
                    conv_data = await self.get_conversation(conversation_id)
                    
                    if conv_data:
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