"""
WebSocket 연결 관리 모듈
"""
import logging
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket 연결 관리 클래스"""
    
    def __init__(self):
        """WebSocket 관리자 초기화"""
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        logger.info("WebSocket 관리자 초기화 완료")
    
    async def connect(self, websocket: WebSocket, conversation_id: str):
        """
        WebSocket 연결 수락
        
        Args:
            websocket: WebSocket 객체
            conversation_id: 대화 ID
        """
        await websocket.accept()
        
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = set()
            
        self.active_connections[conversation_id].add(websocket)
        logger.info(f"WebSocket 연결 수락 (대화 ID: {conversation_id}, 총 연결: {len(self.active_connections[conversation_id])})")
    
    def disconnect(self, websocket: WebSocket, conversation_id: str):
        """
        WebSocket 연결 종료
        
        Args:
            websocket: WebSocket 객체
            conversation_id: 대화 ID
        """
        if conversation_id in self.active_connections:
            self.active_connections[conversation_id].discard(websocket)
            
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]
                
        logger.info(f"WebSocket 연결 종료 (대화 ID: {conversation_id})")
    
    async def broadcast(self, conversation_id: str, message: Dict[str, Any]):
        """
        특정 대화의 모든 연결에 메시지 브로드캐스트
        
        Args:
            conversation_id: 대화 ID
            message: 전송할 메시지
        """
        if conversation_id not in self.active_connections:
            return
            
        disconnected = set()
        for connection in self.active_connections[conversation_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"메시지 전송 중 오류: {str(e)}")
                disconnected.add(connection)
        
        # 끊어진 연결 정리
        for connection in disconnected:
            self.disconnect(connection, conversation_id) 