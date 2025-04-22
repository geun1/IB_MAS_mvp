"""
대화 컨텍스트 관리 모듈
"""
import logging
import time
from typing import Dict, List, Any, Optional
import redis
import json

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
    
    async def save_response(self, conversation_id: str, response: str) -> None:
        """
        시스템 응답 저장
        
        Args:
            conversation_id: 대화 ID
            response: 시스템 응답
        """
        key = f"conv:{conversation_id}:history"
        timestamp = time.time()
        
        # 응답 저장
        entry = {
            "role": "assistant",
            "content": response,
            "timestamp": timestamp
        }
        
        self.redis.lpush(key, json.dumps(entry))
        self.redis.ltrim(key, 0, (self.max_history * 2) - 1)  # 최근 N개 대화만 유지
        
        # 메타데이터 업데이트
        self.redis.hset(f"conv:{conversation_id}:meta", mapping={
            "last_update": timestamp,
            "response_count": self.redis.hincrby(f"conv:{conversation_id}:meta", "response_count", 1)
        })
    
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