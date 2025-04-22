"""
API 보안 모듈
"""
import logging
import time
import hashlib
import hmac
import os
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# API 키 헤더
API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

# API 키 목록 (실제로는 환경 변수나 안전한 저장소에서 관리)
API_KEYS = {
    os.getenv("ORCHESTRATOR_API_KEY", "default-api-key"): {
        "role": "admin",
        "rate_limit": 100  # 분당 요청 수
    }
}

# 요청 제한 (rate limiting)
REQUEST_LIMITS = {}

class SecurityManager:
    """API 보안 관리 클래스"""
    
    @staticmethod
    async def verify_api_key(api_key: str = Depends(API_KEY_HEADER)) -> Dict[str, Any]:
        """
        API 키 검증
        
        Args:
            api_key: API 키
            
        Returns:
            API 키 정보
            
        Raises:
            HTTPException: API 키가 유효하지 않은 경우
        """
        if api_key not in API_KEYS:
            logger.warning(f"잘못된 API 키 사용 시도: {api_key[:5]}...")
            raise HTTPException(status_code=401, detail="인증 실패: 잘못된 API 키")
            
        return API_KEYS[api_key]
    
    @staticmethod
    async def check_rate_limit(request: Request, api_key_info: Dict[str, Any]) -> None:
        """
        요청 제한 확인
        
        Args:
            request: 요청 객체
            api_key_info: API 키 정보
            
        Raises:
            HTTPException: 요청 제한을 초과한 경우
        """
        client_ip = request.client.host
        api_key = request.headers.get("X-API-Key", "")
        
        # 분 단위 시간 창 계산
        current_minute = int(time.time() / 60)
        rate_key = f"{api_key}:{client_ip}:{current_minute}"
        
        # 현재 요청 수 가져오기
        current_count = REQUEST_LIMITS.get(rate_key, 0)
        
        # 제한 확인
        if current_count >= api_key_info.get("rate_limit", 60):
            logger.warning(f"요청 제한 초과: {client_ip}, API 키: {api_key[:5]}...")
            raise HTTPException(status_code=429, detail="요청이 너무 많습니다. 잠시 후 다시 시도하세요.")
        
        # 요청 수 증가
        REQUEST_LIMITS[rate_key] = current_count + 1
        
        # 오래된 항목 정리
        for key in list(REQUEST_LIMITS.keys()):
            if not key.endswith(str(current_minute)):
                del REQUEST_LIMITS[key] 