import pytest
import asyncio
import time
import httpx
import os
import json
import logging
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# 프로젝트 루트에 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# 로그 디렉토리 확인 및 생성
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "registry_test.log"

# 로깅 설정 (파일 + 콘솔)
logger = logging.getLogger("registry_test")
logger.setLevel(logging.DEBUG)

# 이전 핸들러 제거
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# 콘솔 핸들러
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

# 파일 핸들러
file_handler = logging.FileHandler(log_file, mode='w')
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# 시작 로그
logger.info(f"Registry 테스트 시작 - 로그 파일: {log_file}")

# Registry API 로컬 엔드포인트
REGISTRY_URL = "http://localhost:8000"

# Registry 서버가 실행 중인지 확인하는 도우미 함수
def is_registry_running():
    try:
        with httpx.Client() as client:
            response = client.get(f"{REGISTRY_URL}/health", timeout=1)
            if response.status_code == 200:
                logger.info(f"Registry 서버 정상 실행 중: {response.json()}")
                return True
            else:
                logger.error(f"Registry 서버 응답 오류: {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"Registry 서버 연결 실패: {str(e)}")
        return False

# Registry가 실행 중이 아니면 테스트 건너뛰기
pytestmark = pytest.mark.skipif(
    not is_registry_running(), 
    reason="Registry 서버가 실행 중이지 않습니다. 테스트 전에 registry 서버를 실행하세요."
)

# 테스트 에이전트 데이터
test_agent = {
    "id": "test-agent-001",
    "role": "test-agent",
    "description": "테스트용 에이전트",
    "params": [
        {
            "name": "query",
            "description": "검색 질의어",
            "required": True,
            "type": "string"
        }
    ],
    "type": "function",
    "endpoint": "http://localhost:8080/run",
    "status": "available",
    "load": 0.0,
    "active_tasks": 0,
    "capabilities": ["검색", "요약"]
}

# 에이전트 정의 추가 (상단에 추가)
web_search_agent = {
    "id": "web_search_agent_1",
    "role": "web_search",
    "description": "웹에서 정보를 검색하고 관련 결과를 반환합니다.",
    "params": [
        {
            "name": "query",
            "description": "검색할 쿼리 또는 키워드",
            "required": True,
            "type": "string"
        }
    ],
    "type": "function",
    "endpoint": "http://agent_web_search:8000/run",
    "status": "available",
    "load": 0.0,
    "active_tasks": 0,
    "capabilities": ["검색", "정보 수집"]
}

writer_agent = {
    "id": "writer_agent_1",
    "role": "writer",
    "description": "주어진 주제와 참고 자료를 바탕으로 문서나 보고서를 작성합니다.",
    "params": [
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
    "type": "function",
    "endpoint": "http://agent_writer:8000/run",
    "status": "available",
    "load": 0.0,
    "active_tasks": 0,
    "capabilities": ["문서 작성", "요약"]
}

# 테스트 클래스
class TestRegistry:
    
    def setup_method(self):
        # 각 테스트 시작 전에 에이전트 등록 상태 초기화
        logger.info("----------테스트 초기화 시작----------")
        self.client = httpx.Client(base_url=REGISTRY_URL)
        
        # 이전 테스트에서 남은 에이전트가 있으면 제거
        try:
            logger.info(f"기존 테스트 에이전트 정리 시도: {test_agent['role']}/{test_agent['id']}")
            response = self.client.post("/unregister", params={
                "role": test_agent["role"],
                "agent_id": test_agent["id"]
            })
            if response.status_code == 200:
                logger.info("기존 에이전트 정리 성공")
            else:
                logger.info(f"에이전트가 없거나 정리 실패: {response.status_code}")
        except Exception as e:
            logger.info(f"정리 과정 예외 발생 (무시): {str(e)}")
        
        logger.info("----------테스트 초기화 완료----------")
            
    def teardown_method(self):
        # 각 테스트 종료 후 에이전트 등록 해제
        logger.info("----------테스트 정리 시작----------")
        try:
            logger.info(f"테스트 에이전트 정리: {test_agent['role']}/{test_agent['id']}")
            response = self.client.post("/unregister", params={
                "role": test_agent["role"],
                "agent_id": test_agent["id"]
            })
            if response.status_code == 200:
                logger.info("테스트 에이전트 정리 성공")
            else:
                logger.info(f"에이전트 정리 실패: {response.status_code}")
        except Exception as e:
            logger.info(f"정리 중 예외 발생 (무시): {str(e)}")
            
        self.client.close()
        logger.info("----------테스트 정리 완료----------\n")
        
    def test_register_agent(self):
        """에이전트 등록 테스트"""
        logger.info("테스트 시작: 에이전트 등록")
        
        # 에이전트 등록 요청
        logger.info(f"에이전트 등록 요청: {json.dumps(test_agent, indent=2)}")
        response = self.client.post("/register", json=test_agent)
        
        # 응답 확인
        logger.info(f"등록 응답 상태 코드: {response.status_code}")
        logger.info(f"등록 응답 내용: {json.dumps(response.json(), indent=2)}")
        
        # 검증
        assert response.status_code == 200, f"등록 실패: {response.text}"
        data = response.json()
        assert data["status"] == "success", f"성공 상태가 아님: {data['status']}"
        assert data["data"]["agent_id"] == test_agent["id"], f"ID 불일치: {data['data']['agent_id']} != {test_agent['id']}"
        
        logger.info("테스트 성공: 에이전트 등록")
        
    def test_heartbeat(self):
        """하트비트 업데이트 테스트"""
        logger.info("테스트 시작: 하트비트 업데이트")
        
        # 먼저 에이전트 등록
        logger.info("사전 작업: 에이전트 등록")
        reg_response = self.client.post("/register", json=test_agent)
        assert reg_response.status_code == 200, "사전 에이전트 등록 실패"
        logger.info(f"에이전트 등록 완료: {reg_response.status_code}")
        
        # 하트비트 정보 준비
        heartbeat_data = {
            "role": test_agent["role"],
            "agent_id": test_agent["id"],
            "status": "busy",
            "load": 0.5,
            "active_tasks": 1
        }
        logger.info(f"하트비트 전송 데이터: {json.dumps(heartbeat_data, indent=2)}")
        
        # 하트비트 전송
        response = self.client.post("/heartbeat", json=heartbeat_data)
        logger.info(f"하트비트 응답 상태 코드: {response.status_code}")
        logger.info(f"하트비트 응답 내용: {json.dumps(response.json(), indent=2)}")
        
        assert response.status_code == 200, f"하트비트 실패: {response.text}"
        data = response.json()
        assert data["status"] == "success", f"성공 상태가 아님: {data['status']}"
        
        # 상태 변경 확인
        logger.info("에이전트 상태 조회 중...")
        agents_response = self.client.get("/agents", params={"role": test_agent["role"]})
        logger.info(f"에이전트 조회 응답 코드: {agents_response.status_code}")
        
        agents_data = agents_response.json()
        logger.info(f"에이전트 조회 결과: {json.dumps(agents_data, indent=2)}")
        
        assert agents_response.status_code == 200, "에이전트 조회 실패"
        assert len(agents_data["agents"]) > 0, "에이전트가 목록에 없음"
        agent_data = agents_data["agents"][0]
        
        # 변경된 상태 확인
        assert agent_data["status"] == "busy", f"상태 변경 안됨: {agent_data['status']} != busy"
        assert agent_data["load"] == 0.5, f"부하 변경 안됨: {agent_data['load']} != 0.5"
        assert agent_data["active_tasks"] == 1, f"작업 수 변경 안됨: {agent_data['active_tasks']} != 1"
        
        logger.info("테스트 성공: 하트비트 업데이트")
        
    def test_list_agents(self):
        """에이전트 목록 조회 테스트"""
        logger.info("테스트 시작: 에이전트 목록 조회")
        
        # 에이전트 등록
        logger.info("사전 작업: 에이전트 등록")
        reg_response = self.client.post("/register", json=test_agent)
        assert reg_response.status_code == 200, "사전 에이전트 등록 실패"
        
        # 전체 목록 조회
        logger.info("전체 에이전트 목록 조회 중...")
        response = self.client.get("/agents")
        logger.info(f"전체 목록 응답 코드: {response.status_code}")
        
        data = response.json()
        logger.info(f"전체 에이전트 수: {data['total']}")
        logger.info(f"전체 목록 첫 5개: {json.dumps(data['agents'][:5], indent=2)}")
        
        assert response.status_code == 200, "전체 목록 조회 실패"
        assert data["total"] >= 1, f"에이전트가 충분하지 않음: {data['total']} < 1"
        
        # 특정 역할로 필터링
        logger.info(f"역할별 필터링: {test_agent['role']}")
        role_response = self.client.get("/agents", params={"role": test_agent["role"]})
        role_data = role_response.json()
        
        logger.info(f"필터링 결과 에이전트 수: {role_data['total']}")
        if role_data["total"] > 0:
            logger.info(f"필터링된 에이전트: {json.dumps(role_data['agents'], indent=2)}")
        
        assert role_response.status_code == 200, "역할별 조회 실패"
        assert role_data["total"] >= 1, f"해당 역할의 에이전트 없음: {role_data['total']} < 1"
        
        # 테스트 에이전트가 포함되었는지 확인
        found = False
        for agent in role_data["agents"]:
            if agent["id"] == test_agent["id"]:
                found = True
                logger.info(f"테스트 에이전트 발견: {agent['id']}")
                break
                
        assert found, f"테스트 에이전트를 찾을 수 없음: {test_agent['id']}"
        
        logger.info("테스트 성공: 에이전트 목록 조회")
    
    def test_agents_by_role(self):
        """역할별 에이전트 조회 테스트"""
        # 에이전트 등록
        self.client.post("/register", json=test_agent)
        
        # 역할별 조회
        response = self.client.get(f"/agents/by-role/{test_agent['role']}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(a["id"] == test_agent["id"] for a in data["agents"])
        
    def test_unregister_agent(self):
        """에이전트 등록 해제 테스트"""
        logger.info("테스트 시작: 에이전트 등록 해제")
        
        # 에이전트 등록
        logger.info("사전 작업: 에이전트 등록")
        reg_response = self.client.post("/register", json=test_agent)
        assert reg_response.status_code == 200, "사전 에이전트 등록 실패"
        
        # 등록 해제
        logger.info(f"에이전트 등록 해제 요청: {test_agent['role']}/{test_agent['id']}")
        response = self.client.post("/unregister", params={
            "role": test_agent["role"],
            "agent_id": test_agent["id"]
        })
        
        logger.info(f"등록 해제 응답 코드: {response.status_code}")
        if response.status_code == 200:
            logger.info(f"등록 해제 응답 내용: {json.dumps(response.json(), indent=2)}")
        
        assert response.status_code == 200, f"등록 해제 실패: {response.text}"
        
        # 목록에서 제거되었는지 확인
        logger.info("에이전트 목록 재확인 중...")
        agents_response = self.client.get("/agents", params={"role": test_agent["role"]})
        agents_data = agents_response.json()
        
        logger.info(f"목록 조회 결과: {json.dumps(agents_data, indent=2)}")
        
        # 특정 에이전트가 목록에 없는지 확인
        for agent in agents_data["agents"]:
            assert agent["id"] != test_agent["id"], f"에이전트가 여전히 목록에 있음: {agent['id']}"
        
        logger.info("테스트 성공: 에이전트가 목록에서 제거됨")
        
    def test_heartbeat_ttl(self):
        """하트비트 TTL 테스트 (TTL이 짧을 경우만 실행)"""
        ttl = int(os.getenv("AGENT_TTL", "30"))
        logger.info(f"테스트 시작: 하트비트 TTL (설정 TTL: {ttl}초)")
        
        # TTL이 10초 미만인지 확인 (테스트를 빠르게 하기 위함)
        if ttl > 10:
            logger.info(f"TTL이 10초보다 깁니다({ttl}초). 테스트 건너뜁니다.")
            pytest.skip("TTL이 10초 초과로 설정되어 테스트를 건너뜁니다.")
        
        # 에이전트 등록
        logger.info("사전 작업: 에이전트 등록")
        reg_response = self.client.post("/register", json=test_agent)
        assert reg_response.status_code == 200, "사전 에이전트 등록 실패"
        
        # 에이전트가 등록되었는지 확인
        check_response = self.client.get("/agents", params={"role": test_agent["role"]})
        check_data = check_response.json()
        logger.info(f"등록 직후 에이전트 확인: {json.dumps(check_data, indent=2)}")
        
        # TTL 기다리기
        wait_time = ttl + 2  # TTL보다 약간 더 대기
        logger.info(f"TTL 만료 대기중... {wait_time}초")
        time.sleep(wait_time)
        
        # 목록에서 제거되었는지 확인
        logger.info("TTL 만료 후 에이전트 목록 확인")
        agents_response = self.client.get("/agents", params={"role": test_agent["role"]})
        agents_data = agents_response.json()
        
        logger.info(f"TTL 만료 후 목록: {json.dumps(agents_data, indent=2)}")
        
        # 특정 에이전트가 목록에 없는지 확인
        for agent in agents_data["agents"]:
            assert agent["id"] != test_agent["id"], f"TTL 만료되었지만 에이전트가 여전히 목록에 있음: {agent['id']}"
        
        logger.info("테스트 성공: TTL 만료 후 에이전트가 목록에서 제거됨")

    def test_dynamic_agent_registration(self):
        """동적 에이전트 등록 테스트"""
        logger.info("테스트 시작: 동적 에이전트 등록")
        
        # 1. 초기 에이전트 목록 확인
        logger.info("초기 상태 확인: 등록된 에이전트 목록")
        initial_response = self.client.get("/agents")
        initial_data = initial_response.json()
        initial_count = initial_data["total"]
        logger.info(f"초기 에이전트 수: {initial_count}")
        
        # 2. 첫 번째 에이전트(web_search) 등록
        logger.info(f"첫 번째 에이전트 등록: {web_search_agent['role']}/{web_search_agent['id']}")
        web_search_response = self.client.post("/register", json=web_search_agent)
        assert web_search_response.status_code == 200, f"web_search 에이전트 등록 실패: {web_search_response.text}"
        logger.info(f"web_search 에이전트 등록 응답: {json.dumps(web_search_response.json(), indent=2)}")
        
        # 3. 두 번째 에이전트(writer) 등록
        logger.info(f"두 번째 에이전트 등록: {writer_agent['role']}/{writer_agent['id']}")
        writer_response = self.client.post("/register", json=writer_agent)
        assert writer_response.status_code == 200, f"writer 에이전트 등록 실패: {writer_response.text}"
        logger.info(f"writer 에이전트 등록 응답: {json.dumps(writer_response.json(), indent=2)}")
        
        # 4. 업데이트된 에이전트 목록 확인
        logger.info("에이전트 등록 후 전체 목록 확인")
        updated_response = self.client.get("/agents")
        updated_data = updated_response.json()
        updated_count = updated_data["total"]
        logger.info(f"업데이트된 전체 에이전트 수: {updated_count}")
        
        # 에이전트 수가 증가했는지 확인
        assert updated_count >= initial_count + 2, f"에이전트 수가 예상대로 증가하지 않음: {updated_count} < {initial_count + 2}"
        
        # 5. 역할별 에이전트 확인 - web_search
        logger.info(f"역할별 에이전트 확인: {web_search_agent['role']}")
        web_search_role_response = self.client.get(f"/agents/by-role/{web_search_agent['role']}")
        web_search_role_data = web_search_role_response.json()
        logger.info(f"web_search 역할 에이전트 수: {web_search_role_data['total']}")
        
        # 해당 역할의 에이전트가 있는지 확인
        assert web_search_role_data["total"] >= 1, f"web_search 역할의 에이전트가 없음"
        assert any(a["id"] == web_search_agent["id"] for a in web_search_role_data["agents"]), f"등록한 web_search 에이전트를 찾을 수 없음"
        
        # 6. 역할별 에이전트 확인 - writer
        logger.info(f"역할별 에이전트 확인: {writer_agent['role']}")
        writer_role_response = self.client.get(f"/agents/by-role/{writer_agent['role']}")
        writer_role_data = writer_role_response.json()
        logger.info(f"writer 역할 에이전트 수: {writer_role_data['total']}")
        
        # 해당 역할의 에이전트가 있는지 확인
        assert writer_role_data["total"] >= 1, f"writer 역할의 에이전트가 없음"
        assert any(a["id"] == writer_agent["id"] for a in writer_role_data["agents"]), f"등록한 writer 에이전트를 찾을 수 없음"
        
        # 7. 하트비트 테스트 - web_search
        logger.info(f"web_search 에이전트 하트비트 테스트")
        web_search_heartbeat = {
            "role": web_search_agent["role"],
            "agent_id": web_search_agent["id"],
            "status": "busy",
            "load": 0.5,
            "active_tasks": 2
        }
        web_search_heartbeat_response = self.client.post("/heartbeat", json=web_search_heartbeat)
        assert web_search_heartbeat_response.status_code == 200, f"web_search 하트비트 실패: {web_search_heartbeat_response.text}"
        logger.info(f"web_search 하트비트 응답: {json.dumps(web_search_heartbeat_response.json(), indent=2)}")
        
        # 8. 하트비트 후 상태 확인 - web_search
        logger.info(f"web_search 에이전트 상태 확인")
        web_search_status_response = self.client.get(f"/agents/by-role/{web_search_agent['role']}")
        web_search_status_data = web_search_status_response.json()
        
        # 에이전트 상태 찾기
        web_search_agent_data = None
        for agent in web_search_status_data["agents"]:
            if agent["id"] == web_search_agent["id"]:
                web_search_agent_data = agent
                break
        
        assert web_search_agent_data is not None, "하트비트 후 web_search 에이전트를 찾을 수 없음"
        assert web_search_agent_data["status"] == "busy", f"web_search 상태가 busy가 아님: {web_search_agent_data['status']}"
        assert web_search_agent_data["load"] == 0.5, f"web_search 부하가 예상과 다름: {web_search_agent_data['load']}"
        assert web_search_agent_data["active_tasks"] == 2, f"web_search 활성 작업 수가 예상과 다름: {web_search_agent_data['active_tasks']}"
        
        # 9. 서비스 상태 확인 (roles 통계 확인)
        logger.info("레지스트리 서비스 상태 확인")
        health_response = self.client.get("/health")
        health_data = health_response.json()
        logger.info(f"서비스 상태: {json.dumps(health_data, indent=2)}")
        
        # roles 통계에 추가한 역할이 포함되어 있는지 확인
        if "data" in health_data and "roles" in health_data["data"]:
            roles = health_data["data"]["roles"]
            assert web_search_agent["role"] in roles, f"web_search 역할이 서비스 통계에 없음"
            assert writer_agent["role"] in roles, f"writer 역할이 서비스 통계에 없음"
        
        logger.info("테스트 성공: 동적 에이전트 등록 완료")

    def test_agent_unregister_then_register(self):
        """에이전트 해제 후 재등록 테스트"""
        logger.info("테스트 시작: 에이전트 해제 후 재등록")
        
        # 1. 에이전트 등록
        logger.info(f"에이전트 초기 등록: {web_search_agent['role']}/{web_search_agent['id']}")
        reg_response = self.client.post("/register", json=web_search_agent)
        assert reg_response.status_code == 200, "에이전트 초기 등록 실패"
        
        # 2. 에이전트가 등록되었는지 확인
        role_response = self.client.get(f"/agents/by-role/{web_search_agent['role']}")
        role_data = role_response.json()
        assert any(a["id"] == web_search_agent["id"] for a in role_data["agents"]), "등록한 에이전트를 찾을 수 없음"
        logger.info("에이전트 초기 등록 확인 완료")
        
        # 3. 에이전트 등록 해제
        logger.info(f"에이전트 등록 해제: {web_search_agent['role']}/{web_search_agent['id']}")
        unreg_response = self.client.post("/unregister", params={
            "role": web_search_agent["role"],
            "agent_id": web_search_agent["id"]
        })
        assert unreg_response.status_code == 200, "에이전트 등록 해제 실패"
        
        # 4. 에이전트가 목록에서 제거되었는지 확인
        after_unreg_response = self.client.get(f"/agents/by-role/{web_search_agent['role']}")
        after_unreg_data = after_unreg_response.json()
        assert not any(a["id"] == web_search_agent["id"] for a in after_unreg_data["agents"]), "해제한 에이전트가 여전히 목록에 있음"
        logger.info("에이전트 등록 해제 확인 완료")
        
        # 5. 에이전트 재등록
        logger.info(f"에이전트 재등록: {web_search_agent['role']}/{web_search_agent['id']}")
        rereg_response = self.client.post("/register", json=web_search_agent)
        assert rereg_response.status_code == 200, "에이전트 재등록 실패"
        
        # 6. 에이전트가 다시 등록되었는지 확인
        after_rereg_response = self.client.get(f"/agents/by-role/{web_search_agent['role']}")
        after_rereg_data = after_rereg_response.json()
        assert any(a["id"] == web_search_agent["id"] for a in after_rereg_data["agents"]), "재등록한 에이전트를 찾을 수 없음"
        logger.info("에이전트 재등록 확인 완료")
        
        logger.info("테스트 성공: 에이전트 해제 후 재등록 테스트 완료")


if __name__ == "__main__":
    # 상세 로그 출력으로 직접 실행
    print("Registry 테스트 상세 모드 실행 중...")
    pytest.main(["-xvs", __file__]) 