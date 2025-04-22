"""
대화 흐름 관리 모듈
"""
import logging
import json
from typing import Dict, List, Any, Optional
from .models import Task

logger = logging.getLogger(__name__)

class ConversationFlow:
    """대화 흐름 관리 클래스"""
    
    def __init__(self, context_manager=None):
        """
        대화 흐름 관리자 초기화
        
        Args:
            context_manager: 컨텍스트 관리자
        """
        self.context_manager = context_manager
        logger.info("대화 흐름 관리자 초기화 완료")
    
    async def analyze_query_intent(self, query: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        쿼리 의도 분석
        
        Args:
            query: 사용자 쿼리
            conversation_id: 대화 ID
            
        Returns:
            의도 분석 결과
        """
        # 이전 대화 컨텍스트 가져오기
        context = ""
        if conversation_id and self.context_manager:
            context = await self.context_manager.format_history_for_llm(conversation_id, limit=3)
        
        # 여기서 실제로는 LLM을 호출하여 의도 분석
        # 간단한 예시만 구현
        intent = "task_execution"  # 기본값
        
        # 간단한 규칙 기반 의도 분석
        if any(word in query.lower() for word in ["취소", "중지", "그만"]):
            intent = "cancel_task"
        elif any(word in query.lower() for word in ["상태", "진행", "어디까지"]):
            intent = "status_check"
        elif any(word in query.lower() for word in ["도움", "사용법", "어떻게"]):
            intent = "help_request"
        
        return {
            "intent": intent,
            "query": query,
            "context": context
        }
    
    async def handle_follow_up(self, original_query: str, follow_up_query: str, conversation_id: str) -> Dict[str, Any]:
        """
        후속 쿼리 처리
        
        Args:
            original_query: 원래 쿼리
            follow_up_query: 후속 쿼리
            conversation_id: 대화 ID
            
        Returns:
            처리 결과
        """
        # 대화 컨텍스트와 태스크 결과를 활용하여 후속 쿼리 처리
        # 여기서 필요에 따라 이전 태스크 정보를 참조하여 처리
        
        # 예시: 단순히 후속 쿼리에 대한 처리 지시
        return {
            "type": "follow_up",
            "original_query": original_query,
            "follow_up_query": follow_up_query,
            "conversation_id": conversation_id,
            "should_reuse_tasks": False,  # 기존 태스크 결과 재사용 여부
            "task_modifications": []  # 필요한 태스크 수정 사항
        } 