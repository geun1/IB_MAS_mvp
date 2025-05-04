from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
import uuid
from datetime import datetime

class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"

class AgentParamType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"

class AgentParam(BaseModel):
    name: str
    description: str
    type: str
    required: bool
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None

class Agent(BaseModel):
    id: str
    role: str
    description: str
    params: List[AgentParam] = []
    config_params: List[AgentParam] = []
    type: str = "function"
    endpoint: str
    status: AgentStatus = AgentStatus.AVAILABLE
    load: float = 0.0  # 0.0~1.0 사이의 부하 지표
    active_tasks: int = 0
    last_heartbeat: Optional[float] = Field(default_factory=lambda: datetime.now().timestamp())
    capabilities: List[str] = []
    error_message: Optional[str] = None
    is_enabled: bool = True  # 에이전트 활성화 상태, 기본값은 활성화
    
    @validator('role')
    def role_must_be_lowercase(cls, v):
        if v != v.lower():
            return v.lower()
        return v

class AgentHeartbeat(BaseModel):
    role: str
    agent_id: str
    status: AgentStatus = AgentStatus.AVAILABLE
    load: float = 0.0
    active_tasks: int = 0
    error_message: Optional[str] = None

class AgentList(BaseModel):
    agents: List[Agent]
    total: int
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())

class ApiResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

class AgentStatistics(BaseModel):
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    success_rate: float = 0.0
    avg_execution_time: float = 0.0
    last_task_time: Optional[float] = None 