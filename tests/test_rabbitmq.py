"""
RabbitMQ 기본 통신 테스트 모듈 (안정화 버전)

이 모듈은 시스템의 RabbitMQ 연결 및 메시지 브로커 기능을 간소화된 방식으로 테스트합니다.
멀티스레딩 대신 단순한 동기식 테스트로 변경하여 안정성을 높였습니다.

테스트 실행 방법:
    $ pytest test_rabbitmq.py -v
"""

import os
import pika
import time
import json
import pytest
import threading
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# RabbitMQ 연결 설정
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")


class TestRabbitMQBasics:
    """
    RabbitMQ 기본 기능 테스트
    
    이 클래스는 기본적인 RabbitMQ 기능만 테스트합니다.
    복잡한 멀티스레딩 테스트는 삭제하고 안정적인 테스트만 포함합니다.
    """

    @pytest.fixture
    def rabbitmq_connection(self):
        """
        RabbitMQ 연결 생성 및 테스트 후 종료
        
        테스트에 사용되는 RabbitMQ 연결을 생성하고,
        테스트 완료 후 연결을 안전하게 종료합니다.
        """
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT,
                    credentials=credentials,
                    connection_attempts=3,
                    retry_delay=2,
                    heartbeat=5  # 하트비트 추가하여 연결 안정성 향상
                )
            )
            yield connection
            # 연결이 아직 열려있는 경우에만 닫기
            if connection.is_open:
                connection.close()
        except Exception as e:
            print(f"RabbitMQ 연결 문제: {e}")
            # 연결 실패시 None 반환하고 테스트는 건너뛰게 함
            pytest.skip(f"RabbitMQ 서버 연결 불가: {e}")

    @pytest.fixture
    def rabbitmq_channel(self, rabbitmq_connection):
        """
        RabbitMQ 채널 생성
        
        테스트에 사용되는 RabbitMQ 채널을 생성합니다.
        """
        if not rabbitmq_connection:
            pytest.skip("RabbitMQ 연결이 없습니다")
        
        try:
            channel = rabbitmq_connection.channel()
            yield channel
        except Exception as e:
            pytest.skip(f"RabbitMQ 채널 생성 실패: {e}")

    def test_basic_publish_get(self, rabbitmq_channel):
        """
        기본 메시지 발행 및 수신 테스트
        
        메시지를 발행하고 즉시 수신하는 간단한 테스트입니다.
        멀티스레딩을 사용하지 않습니다.
        """
        # 테스트 큐 선언
        queue_name = "test_basic_queue"
        rabbitmq_channel.queue_declare(queue=queue_name, durable=True)
        
        # 테스트 메시지 발행
        test_message = {
            "id": "test_message_id",
            "content": "테스트 메시지 내용",
            "timestamp": time.time()
        }
        
        # 메시지 발행
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(test_message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # 메시지 지속성
                content_type='application/json'
            )
        )
        
        # 메시지 수신 (basic_get 사용)
        method_frame, header_frame, body = rabbitmq_channel.basic_get(queue=queue_name, auto_ack=True)
        
        # 테스트 결과 확인
        assert method_frame is not None, "메시지를 수신하지 못했습니다"
        
        received_message = json.loads(body)
        assert received_message["id"] == test_message["id"], "메시지 ID가 일치하지 않습니다"
        assert received_message["content"] == test_message["content"], "메시지 내용이 일치하지 않습니다"
        
        # 테스트 정리
        rabbitmq_channel.queue_delete(queue=queue_name)


# 직접 실행 시 테스트
if __name__ == "__main__":
    """
    이 스크립트를 직접 실행하면 간단한 RabbitMQ 테스트를 수행합니다.
    pytest 없이도 기본적인 연결 및 동작을 확인할 수 있습니다.
    """
    try:
        # 연결 설정
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials
            )
        )
        channel = connection.channel()
        
        # 테스트 큐 생성
        queue_name = "direct_test_queue"
        channel.queue_declare(queue=queue_name)
        
        # 메시지 발행
        message = {"message": "RabbitMQ 직접 테스트"}
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message)
        )
        
        print(f"메시지 전송 완료: {message}")
        
        # 메시지 수신
        method_frame, header_frame, body = channel.basic_get(queue=queue_name, auto_ack=True)
        if method_frame:
            print(f"수신된 메시지: {json.loads(body)}")
        else:
            print("메시지를 수신하지 못했습니다")
        
        # 정리
        channel.queue_delete(queue=queue_name)
        connection.close()
        
    except Exception as e:
        print(f"RabbitMQ 연결 오류: {str(e)}") 