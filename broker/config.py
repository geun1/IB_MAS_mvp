import os
from typing import Dict, Any
from pydantic import BaseSettings

class BrokerSettings(BaseSettings):
    # 서비스 설정
    APP_NAME: str = "Broker Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # 서비스 연결 설정
    REGISTRY_URL: str = os.getenv("REGISTRY_URL", "http://registry:8000")
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS: str = os.getenv("RABBITMQ_PASS", "guest")
    
    # 태스크 설정
    TASK_TIMEOUT: float = float(os.getenv("TASK_TIMEOUT", "30.0"))
    AGENT_RETRY_COUNT: int = int(os.getenv("AGENT_RETRY_COUNT", "2"))
    
    # LLM 설정
    DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "gpt-4o-mini")
    LLM_API_KEY: str = "REMOVEDproj-Z9xpJQlE6j2LJqUNxWwFk1BrJwgaf6ai1Pase_qZdjBcNwUUqkW-z-iWlymnqON_WlLpXZL8J2T3BlbkFJFdDQE_PlQwnd9h8TQ7NpaZGBAB-ukoN88VWCh0aaS7KYdvKoRtXAJvviTF9inX_sEilr1c5rMA"

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

# 설정 인스턴스 생성
settings = BrokerSettings() 