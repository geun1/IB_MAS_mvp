from typing import Dict, List, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    role: str
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    agent_id: Optional[str] = None
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    completed_at: Optional[float] = None
    execution_time: Optional[float] = None
    cache_hit: bool = False
    agent_configs: Optional[Dict[str, Dict[str, str]]] = None
    exclude_agent: Optional[str] = None

class TaskList(BaseModel):
    tasks: List[TaskResult]
    total: int
    page: int
    page_size: int

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str
    params: Dict[str, Any]
    conversation_id: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    agent_id: Optional[str] = None
    agent_configs: Optional[Dict[str, Dict[str, str]]] = None
    exclude_agent: Optional[str] = None 