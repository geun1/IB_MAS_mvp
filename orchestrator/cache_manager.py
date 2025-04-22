"""
태스크 결과 캐싱 모듈
"""
import logging
import hashlib
import json
import time
from typing import Dict, Any, Optional
import redis

logger = logging.getLogger(__name__)

class CacheManager:
    """태스크 결과 캐싱 관리 클래스"""
    
    def __init__(self, redis_url: str = "redis://redis:6379/1", ttl: int = 3600):
        """
        캐시 관리자 초기화
        
        Args:
            redis_url: Redis 서버 URL
            ttl: 캐시 유효 시간(초)
        """
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl
        logger.info("캐시 관리자 초기화 완료")
    
    def _generate_key(self, role: str, params: Dict[str, Any]) -> str:
        """
        캐시 키 생성
        
        Args:
            role: 에이전트 역할
            params: 태스크 파라미터
            
        Returns:
            캐시 키
        """
        # 파라미터를 정렬하여 일관된 해시 생성
        params_str = json.dumps(params, sort_keys=True)
        key_str = f"{role}:{params_str}"
        return f"cache:{hashlib.md5(key_str.encode()).hexdigest()}"
    
    async def get_cached_result(self, role: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        캐시된 태스크 결과 조회
        
        Args:
            role: 에이전트 역할
            params: 태스크 파라미터
            
        Returns:
            캐시된 결과 또는 None
        """
        key = self._generate_key(role, params)
        cached = self.redis.get(key)
        
        if cached:
            logger.info(f"캐시 적중: {role}")
            return json.loads(cached)
        
        return None
    
    async def cache_result(self, role: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        태스크 결과 캐싱
        
        Args:
            role: 에이전트 역할
            params: 태스크 파라미터
            result: 태스크 결과
        """
        # 실패한 결과는 캐싱하지 않음
        if result.get("status") != "completed":
            return
            
        key = self._generate_key(role, params)
        self.redis.setex(key, self.ttl, json.dumps(result))
        logger.info(f"결과 캐싱 완료: {role}") 