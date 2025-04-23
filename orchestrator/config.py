"""
오케스트레이터 설정 및 환경 변수 모듈
"""
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# 로깅 설정
logger = logging.getLogger(__name__)

# .env 파일 로드
load_dotenv()
logger.info("환경 변수 로드 완료")

# API 설정
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
BROKER_URL = os.getenv("BROKER_URL", "http://broker:8002")

# LLM 설정
# LLM_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("LLM_API_KEY", ""))
LLM_API_KEY = "***REMOVED***proj-Z9xpJQlE6j2LJqUNxWwFk1BrJwgaf6ai1Pase_qZdjBcNwUUqkW-z-iWlymnqON_WlLpXZL8J2T3BlbkFJFdDQE_PlQwnd9h8TQ7NpaZGBAB-ukoN88VWCh0aaS7KYdvKoRtXAJvviTF9inX_sEilr1c5rMA"
logger.info(f"API 키 설정 상태: {'설정됨' if LLM_API_KEY else '설정되지 않음'}")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))


# 앱 설정
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 태스크 설정
DEFAULT_TASK_TIMEOUT = int(os.getenv("DEFAULT_TASK_TIMEOUT", "300"))  # 초 단위
MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "5")) 