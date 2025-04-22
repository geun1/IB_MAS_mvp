from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class Metrics(BaseModel):
    memory_usage: float = Field(..., description="메모리 사용률(%)")
    cpu_usage: float = Field(..., description="CPU 사용률(%)")
    active_tasks: int = Field(0, description="활성 태스크 수")

class AgentHeartbeat(BaseModel):
    status: str = Field(..., description="에이전트 상태 (active, busy, error 등)")
    timestamp: str = Field(..., description="ISO 형식의 타임스탬프")
    metrics: Metrics = Field(..., description="에이전트 성능 지표")
    version: str = Field(..., description="에이전트 버전")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="추가 정보") 