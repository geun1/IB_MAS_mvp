"""
에이전트 타입 정의 모듈
"""
from enum import Enum, auto
from typing import Dict, Any, List, Optional, Union

class AgentType(str, Enum):
    """에이전트 유형 열거형"""
    WEB_SEARCH = "web_search"
    WRITER = "writer"
    CODE_GENERATOR = "code_generator"
    DATA_ANALYZER = "data_analyzer"
    CHATBOT = "chatbot"
    SUMMARIZER = "summarizer"
    TRANSLATOR = "translator"
    IMAGE_GENERATOR = "image_generator"
    TRAVEL_PLANNER = "travel_planner"
    CUSTOM = "custom"

class AgentStatus(str, Enum):
    """에이전트 상태 열거형"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"

# 에이전트 역할별 기본 설명
AGENT_DESCRIPTIONS = {
    AgentType.WEB_SEARCH: "웹에서 정보를 검색하고 관련 결과를 반환합니다.",
    AgentType.WRITER: "주어진 주제와 참고 자료를 바탕으로 문서나 보고서를 작성합니다.",
    AgentType.CODE_GENERATOR: "사용자 요구사항에 따라 구조화된 코드를 생성합니다.",
    AgentType.DATA_ANALYZER: "데이터를 분석하고 인사이트를 제공합니다.",
    AgentType.CHATBOT: "자연어 대화를 통해 사용자와 상호작용합니다.",
    AgentType.SUMMARIZER: "긴 문서나 텍스트를 요약합니다.",
    AgentType.TRANSLATOR: "텍스트를 다른 언어로 번역합니다.",
    AgentType.IMAGE_GENERATOR: "텍스트 설명을 기반으로 이미지를 생성합니다.",
    AgentType.TRAVEL_PLANNER: "사용자 요구사항에 맞는 여행 계획을 세우고 추천합니다.",
    AgentType.CUSTOM: "사용자 정의 기능을 수행합니다."
}

# 역할별 기본 파라미터 정의
AGENT_DEFAULT_PARAMS = {
    AgentType.WEB_SEARCH: [
        {
            "name": "query",
            "description": "검색할 쿼리 또는 키워드",
            "required": True,
            "type": "string"
        }
    ],
    AgentType.WRITER: [
        {
            "name": "topic",
            "description": "작성할 주제",
            "required": True,
            "type": "string"
        },
        {
            "name": "references",
            "description": "참고할 자료 목록",
            "required": False,
            "type": "array"
        }
    ],
    AgentType.CODE_GENERATOR: [
        {
            "name": "requirements",
            "description": "코드 생성을 위한 요구사항 및 기능 설명",
            "required": True,
            "type": "string"
        },
        {
            "name": "language",
            "description": "사용할 프로그래밍 언어",
            "required": False,
            "type": "string",
            "default": "python" 
        }
    ],
    AgentType.TRAVEL_PLANNER: [
        {
            "name": "query",
            "description": "여행 계획에 대한 요구사항",
            "required": True,
            "type": "string"
        },
        {
            "name": "context",
            "description": "추가 컨텍스트 정보",
            "required": False,
            "type": "string"
        },
        {
            "name": "max_steps",
            "description": "최대 ReACT 단계 수",
            "required": False,
            "type": "integer",
            "default": 10
        }
    ]
    # 다른 에이전트 타입에 대한 파라미터도 추가 가능
} 