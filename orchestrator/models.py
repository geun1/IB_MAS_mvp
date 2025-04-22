"""
오케스트레이터 데이터 모델 정의
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class AgentParam(BaseModel):
    """에이전트 파라미터 스키마"""
    name: str
    description: str
    type: str = "string"
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None

class Agent(BaseModel):
    """에이전트 정보 모델"""
    id: str
    role: str
    description: str
    endpoint: str
    status: str
    params: List[AgentParam] = []
    load: float = 0.0
    active_tasks: int = 0

class Task(BaseModel):
    """태스크 정보 모델"""
    role: str
    description: str
    params: Dict[str, Any]
    depends_on: List[int] = []

class TaskDecomposition(BaseModel):
    """태스크 분해 결과 모델"""
    tasks: List[Task]
    reasoning: str

class QueryRequest(BaseModel):
    """쿼리 요청 모델"""
    query: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class QueryResponse(BaseModel):
    """쿼리 응답 모델"""
    conversation_id: str
    status: str
    tasks: List[Dict[str, Any]]
    message: str 