import pytest
import httpx
import os
import json
import asyncio
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Broker 서비스 엔드포인트
BROKER_URL = "http://localhost:8002"

# 서비스가 실행 중인지 확인
def is_broker_running():
    try:
        with httpx.Client() as client:
            response = client.get(f"{BROKER_URL}/health", timeout=1)
            return response.status_code == 200
    except Exception:
        return False

# 테스트는 서비스가 실행 중일 때만 실행
pytestmark = pytest.mark.skipif(
    not is_broker_running(),
    reason="Broker 서비스가 실행 중이지 않습니다."
)

class TestBroker:
    def test_health_check(self):
        """상태 확인 테스트"""
        with httpx.Client() as client:
            response = client.get(f"{BROKER_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
    
    def test_task_routing(self):
        """태스크 라우팅 테스트"""
        test_task = {
            "role": "writer",
            "params": {
                "topic": "테스트 주제"
            },
            "conversation_id": "test-conv-001"
        }
        
        with httpx.Client() as client:
            response = client.post(f"{BROKER_URL}/task", json=test_task)
            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "accepted" 