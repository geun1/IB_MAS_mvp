"""
Redis 기본 통신 테스트 모듈

이 모듈은 시스템의 Redis 연결 및 주요 데이터 작업을 테스트합니다.
다음과 같은 기능을 테스트합니다:
1. 기본 연결 확인 (ping)
2. Key-Value 작업 (set/get)
3. 해시 작업 (hset/hget)
4. 리스트 작업 (lpush/rpop)
5. Publish-Subscribe 패턴 테스트

테스트 실행 방법:
    $ pytest test_redis.py -v
    또는
    $ python test_redis.py
"""

import redis
import os
import time
import pytest
import json
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Redis 연결 설정
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


class TestRedisConnection:
    """
    Redis 기본 연결 및 작업 테스트
    
    이 클래스는 다양한 Redis 작업을 검증하기 위한 테스트 케이스를 포함합니다.
    각 테스트는 독립적으로 실행되며, fixture를 통해 Redis 클라이언트를 초기화합니다.
    """

    @pytest.fixture
    def redis_client(self):
        """
        Redis 클라이언트 생성 및 테스트 후 정리
        
        테스트에 사용되는 Redis 클라이언트를 생성하고,
        테스트 완료 후 생성된 테스트 키들을 정리합니다.
        """
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        yield client
        # 테스트에 사용된 키 정리
        client.delete("test:key", "test:hash", "test:list", "test:pubsub")

    def test_ping(self, redis_client):
        """
        기본 연결 테스트
        
        Redis 서버에 PING 명령을 보내 연결이 정상적으로 작동하는지 확인합니다.
        """
        assert redis_client.ping() is True

    def test_set_get(self, redis_client):
        """
        기본 Set/Get 작업 테스트
        
        1. 문자열 값 설정 및 조회 테스트
        2. TTL(Time To Live) 설정 및 만료 테스트
        """
        # 문자열 값 설정 및 조회
        redis_client.set("test:key", "테스트 값")
        assert redis_client.get("test:key") == "테스트 값"
        
        # TTL 설정
        redis_client.setex("test:key:ttl", 5, "만료되는 값")
        assert redis_client.get("test:key:ttl") == "만료되는 값"
        assert redis_client.ttl("test:key:ttl") <= 5
        
        # 만료 테스트
        time.sleep(6)
        assert redis_client.get("test:key:ttl") is None

    def test_hash_operations(self, redis_client):
        """
        해시 작업 테스트
        
        Redis 해시 자료구조를 사용하여 필드 설정 및 조회 기능을 테스트합니다.
        1. 해시 필드 개별 설정 (hset)
        2. 단일 필드 조회 (hget)
        3. 전체 해시 조회 (hgetall)
        """
        # 해시 필드 설정
        redis_client.hset("test:hash", "field1", "값1")
        redis_client.hset("test:hash", "field2", "값2")
        
        # 해시 필드 조회
        assert redis_client.hget("test:hash", "field1") == "값1"
        assert redis_client.hgetall("test:hash") == {"field1": "값1", "field2": "값2"}

    def test_list_operations(self, redis_client):
        """
        리스트 작업 테스트
        
        Redis 리스트 자료구조를 사용한 작업을 테스트합니다.
        1. 리스트 왼쪽에 데이터 추가 (lpush)
        2. 리스트 길이 확인 (llen)
        3. 리스트 범위 조회 (lrange)
        4. 리스트 오른쪽에서 데이터 추출 (rpop)
        """
        # 리스트에 값 추가
        redis_client.lpush("test:list", "항목1", "항목2", "항목3")
        
        # 리스트 값 조회
        assert redis_client.llen("test:list") == 3
        assert redis_client.lrange("test:list", 0, -1) == ["항목3", "항목2", "항목1"]
        
        # 리스트에서 값 추출
        assert redis_client.rpop("test:list") == "항목1"

    def test_pubsub(self, redis_client):
        """
        PubSub 패턴 테스트
        
        Redis의 발행-구독(Publish-Subscribe) 패턴을 테스트합니다.
        단순화된 방식으로 메시지 발행 및 수신을 테스트합니다.
        """
        # 구독 설정
        pubsub = redis_client.pubsub()
        pubsub.subscribe("test:channel")
        
        # 초기 구독 메시지 처리
        pubsub.get_message()
        
        # 메시지 발행
        redis_client.publish("test:channel", "테스트 메시지1")
        redis_client.publish("test:channel", "테스트 메시지2")
        
        # 메시지 직접 수신 - 스레드 사용하지 않음
        time.sleep(0.5)  # 메시지가 처리될 시간 제공
        
        # 메시지 수신
        messages = []
        for _ in range(3):  # 충분한 메시지 수신 시도
            message = pubsub.get_message(timeout=1.0)
            if message and message.get('type') == 'message':
                messages.append(message.get('data'))
        
        # 구독 정리
        pubsub.unsubscribe()
        pubsub.close()
        
        # 결과 확인 (최소 하나의 메시지 수신 확인)
        assert len(messages) > 0, f"메시지가 수신되지 않았습니다: {messages}"
        print(f"수신된 메시지: {messages}")


# 직접 실행 시 테스트
if __name__ == "__main__":
    """
    이 스크립트를 직접 실행하면 간단한 Redis 테스트를 수행합니다.
    pytest 없이도 기본적인 연결 및 동작을 확인할 수 있습니다.
    """
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    print(f"Redis 연결 테스트: {r.ping()}")
    
    # 기본 세트 작업
    r.set("test:direct", "직접 실행 테스트")
    print(f"Set/Get 테스트: {r.get('test:direct')}")
    
    # 정리
    r.delete("test:direct") 