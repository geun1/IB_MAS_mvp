#!/usr/bin/env python
"""
에이전트 테스트 스크립트
- Docker Compose로 실행 중인 웹 검색 에이전트와 작성 에이전트를 직접 호출하여 기능 테스트
"""
import os
import sys
import json
import uuid
import asyncio
import logging
import httpx
import socket
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, Optional
import requests
import time
import subprocess

# 프로젝트 루트 경로를 sys.path에 추가
ROOT_DIR = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("에이전트_테스트")

# .env 파일 로드
load_dotenv(Path(__file__).parent / ".env")

# 테스트용 환경 변수
WEB_SEARCH_AGENT_URL = "http://localhost:8010"
WRITER_AGENT_URL = "http://localhost:8011"
REGISTRY_URL = "http://localhost:8000"  # 레지스트리 서비스 URL

def wait_for_service(url: str, max_retries: int = 30, retry_interval: int = 2) -> bool:
    """서비스가 준비될 때까지 대기"""
    for i in range(max_retries):
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"서비스 {url} 준비 완료!")
                return True
        except Exception as e:
            logger.warning(f"서비스 {url}에 연결 시도 중... ({i+1}/{max_retries})")
        time.sleep(retry_interval)
    logger.error(f"서비스 {url}에 연결할 수 없습니다.")
    return False

def test_web_search_agent():
    """웹 검색 에이전트 테스트"""
    logger.info("웹 검색 에이전트 테스트 시작...")
    
    # 1. 헬스 체크
    if not wait_for_service(WEB_SEARCH_AGENT_URL):
        return False
    
    # 2. 검색 기능 테스트
    try:
        search_query = "인공지능 최신 동향"
        response = requests.post(
            f"{WEB_SEARCH_AGENT_URL}/search",
            json={"query": search_query},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"검색 요청 실패: {response.status_code} {response.text}")
            return False
        
        result = response.json()
        if not result.get("results") or not isinstance(result["results"], list):
            logger.error(f"검색 결과 형식 오류: {result}")
            return False
        
        logger.info(f"검색 결과: {json.dumps(result, indent=2, ensure_ascii=False)}")
        logger.info("웹 검색 에이전트 테스트 성공!")
        return True
        
    except Exception as e:
        logger.error(f"웹 검색 에이전트 테스트 중 오류: {str(e)}")
        return False

def test_writer_agent():
    """작성 에이전트 테스트"""
    logger.info("작성 에이전트 테스트 시작...")
    
    # 1. 헬스 체크
    if not wait_for_service(WRITER_AGENT_URL):
        return False
    
    # 2. 작성 기능 테스트
    try:
        topic = "인공지능의 미래"
        response = requests.post(
            f"{WRITER_AGENT_URL}/write",
            json={"topic": topic},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"작성 요청 실패: {response.status_code} {response.text}")
            return False
        
        result = response.json()
        if not result.get("content") or not isinstance(result["content"], str):
            logger.error(f"작성 결과 형식 오류: {result}")
            return False
        
        logger.info(f"작성 결과: {json.dumps(result, indent=2, ensure_ascii=False)}")
        logger.info("작성 에이전트 테스트 성공!")
        return True
        
    except Exception as e:
        logger.error(f"작성 에이전트 테스트 중 오류: {str(e)}")
        return False

def test_agent_integration():
    """에이전트 간 통합 테스트"""
    logger.info("에이전트 통합 테스트 시작...")
    
    try:
        # 1. 웹 검색 실행
        search_query = "블록체인 기술"
        search_response = requests.post(
            f"{WEB_SEARCH_AGENT_URL}/search",
            json={"query": search_query},
            timeout=10
        )
        
        if search_response.status_code != 200:
            logger.error(f"검색 요청 실패: {search_response.status_code}")
            return False
        
        search_results = search_response.json().get("results", [])
        
        # 2. 검색 결과를 작성 에이전트에 전달
        write_response = requests.post(
            f"{WRITER_AGENT_URL}/write",
            json={
                "topic": search_query,
                "references": search_results
            },
            timeout=15
        )
        
        if write_response.status_code != 200:
            logger.error(f"작성 요청 실패: {write_response.status_code}")
            return False
        
        result = write_response.json()
        logger.info(f"통합 테스트 결과: {json.dumps(result, indent=2, ensure_ascii=False)}")
        logger.info("에이전트 통합 테스트 성공!")
        return True
        
    except Exception as e:
        logger.error(f"통합 테스트 중 오류: {str(e)}")
        return False

def test_registry_registration():
    """레지스트리 등록 확인 테스트"""
    logger.info("레지스트리 등록 테스트 시작...")
    
    try:
        # 레지스트리 서비스 확인
        if not wait_for_service(REGISTRY_URL):
            return False
        
        # 에이전트 등록 확인
        response = requests.get(f"{REGISTRY_URL}/agents", timeout=5)
        
        if response.status_code != 200:
            logger.error(f"레지스트리 요청 실패: {response.status_code}")
            return False
        
        agents = response.json()
        web_search_found = False
        writer_found = False
        
        for agent in agents:
            if agent.get("role") == "web_search":
                web_search_found = True
            elif agent.get("role") == "writer":
                writer_found = True
        
        if web_search_found and writer_found:
            logger.info("모든 에이전트가 레지스트리에 등록되었습니다!")
            return True
        else:
            missing = []
            if not web_search_found:
                missing.append("web_search")
            if not writer_found:
                missing.append("writer")
            logger.error(f"일부 에이전트가 레지스트리에 등록되지 않았습니다: {', '.join(missing)}")
            return False
        
    except Exception as e:
        logger.error(f"레지스트리 테스트 중 오류: {str(e)}")
        return False

def run_all_tests():
    """모든 테스트 실행"""
    results = {
        "web_search": test_web_search_agent(),
        "writer": test_writer_agent(),
        "integration": test_agent_integration(),
        "registry": test_registry_registration()
    }
    
    # 테스트 결과 요약
    success = all(results.values())
    logger.info("\n" + "="*50)
    logger.info("테스트 결과 요약:")
    
    for test_name, result in results.items():
        status = "성공" if result else "실패"
        logger.info(f"- {test_name}: {status}")
    
    logger.info("="*50)
    logger.info(f"전체 테스트: {'성공' if success else '실패'}")
    
    return success

if __name__ == "__main__":
    run_all_tests() 