"""
오케스트레이터 설정 및 환경 변수 모듈
"""
import os
import logging
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# 로깅 설정
logger = logging.getLogger(__name__)

# 프로젝트 루트 디렉토리 찾기
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"

# .env 파일 로드
load_dotenv(env_path)
logger.info(f"환경 변수 로드 완료: {env_path}")

# API 설정
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
BROKER_URL = os.getenv("BROKER_URL", "http://broker:8002")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# LLM 설정
LLM_API_KEY = os.getenv("OPENAI_API_KEY", os.getenv("LLM_API_KEY", ""))
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

# 실행 환경 설정
def get_execution_context() -> Dict[str, Any]:
    """
    실행 환경 정보 반환
    
    Returns:
        Dict[str, Any]: 환경 정보 딕셔너리
    """
    return {
        "environment": os.getenv("ENVIRONMENT", "production"),
        "version": os.getenv("VERSION", "0.1.0"),
        "development_mode": DEBUG,
    } 