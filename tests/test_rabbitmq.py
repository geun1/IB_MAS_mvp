"""
RabbitMQ 기본 통신 테스트 모듈

이 모듈은 시스템의 RabbitMQ 연결 및 메시지 브로커 기능을 테스트합니다.
다음과 같은 기능을 테스트합니다:
1. 기본 연결 확인
2. 메시지 전송 및 수신
3. 브로커-에이전트 간 양방향 통신

RabbitMQ는 시스템의 비동기 통신을 담당하며, 에이전트 간 작업 분배에 중요합니다.
테스트는 실제 시스템 구성과 유사한 환경에서 메시지 라우팅을 검증합니다.

테스트 실행 방법:
    $ pytest test_rabbitmq.py -v
    또는
    $ python test_rabbitmq.py
"""

import pika
import os
import time
import json
import threading
import pytest
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# RabbitMQ 연결 설정
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")


class TestRabbitMQConnection:
    """
    RabbitMQ 기본 연결 및 메시지 전송 테스트
    
    이 클래스는 RabbitMQ의 다양한 메시징 패턴을 검증하기 위한 테스트 케이스를 포함합니다.
    - 기본 메시지 전송 및 수신
    - 요청-응답 패턴 (브로커-에이전트 통신)
    
    각 테스트는 독립적인 채널과 큐를 사용하며, fixture를 통해 연결 및 채널을 초기화합니다.
    """

    @pytest.fixture
    def rabbitmq_connection(self):
        """
        RabbitMQ 연결 생성 및 테스트 후 종료
        
        테스트에 사용되는 RabbitMQ 연결을 생성하고,
        테스트 완료 후 연결을 종료합니다.
        """
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials
            )
        )
        yield connection
        connection.close()

    @pytest.fixture
    def rabbitmq_channel(self, rabbitmq_connection):
        """
        RabbitMQ 채널 및 테스트용 큐/익스체인지 생성
        
        1. 채널 생성
        2. 테스트용 큐 선언 (durable=True로 설정하여 메시지 지속성 보장)
        3. 테스트용 익스체인지 선언 (direct 타입)
        4. 큐와 익스체인지 바인딩 (라우팅 키 사용)
        """
        channel = rabbitmq_connection.channel()
        # 테스트용 큐 선언
        channel.queue_declare(queue='test_queue', durable=True)
        channel.exchange_declare(exchange='test_exchange', exchange_type='direct')
        channel.queue_bind(exchange='test_exchange', queue='test_queue', routing_key='test_key')
        yield channel

    def test_send_receive_message(self, rabbitmq_channel):
        """
        기본 메시지 전송 및 수신 테스트
        
        1. 채널에 메시지 콜백 함수 등록
        2. 별도 스레드에서 메시지 소비 시작
        3. 테스트 메시지 발행
        4. 정상적으로 메시지가 수신되는지 확인
        
        이 테스트는 RabbitMQ의 기본적인 메시지 발행-구독 기능을 검증합니다.
        """
        # 수신된 메시지 저장용 리스트
        received_messages = []
        message_event = threading.Event()
        
        # 콜백 함수 정의
        def callback(ch, method, properties, body):
            received_messages.append(json.loads(body))
            message_event.set()
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        # 메시지 수신 설정
        rabbitmq_channel.basic_consume(queue='test_queue', on_message_callback=callback)
        
        # 별도 스레드에서 메시지 소비 시작
        consumer_thread = threading.Thread(
            target=lambda: rabbitmq_channel.start_consuming()
        )
        consumer_thread.daemon = True
        consumer_thread.start()
        
        # 메시지 전송
        test_message = {"type": "test", "content": "테스트 메시지"}
        rabbitmq_channel.basic_publish(
            exchange='test_exchange',
            routing_key='test_key',
            body=json.dumps(test_message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # 메시지 지속성 설정 (2 = 지속적)
                content_type='application/json'
            )
        )
        
        # 메시지 수신 대기 (최대 5초)
        message_event.wait(timeout=5)
        
        # 소비 중단
        rabbitmq_channel.stop_consuming()
        consumer_thread.join(timeout=1)
        
        # 결과 확인
        assert len(received_messages) == 1
        assert received_messages[0]["type"] == "test"
        assert received_messages[0]["content"] == "테스트 메시지"

    def test_broker_agent_communication(self, rabbitmq_channel):
        """
        브로커-에이전트 간 통신 시뮬레이션 테스트
        
        실제 시스템에서 브로커와 에이전트 간의 양방향 통신을 시뮬레이션합니다:
        1. 브로커가 에이전트에게 작업 요청 전송
        2. 에이전트가 작업 수행 후 결과 반환
        3. 브로커가 결과 수신
        
        이 테스트는 다음 RabbitMQ 패턴을 사용합니다:
        - 요청-응답 패턴 (correlation_id로 요청과 응답 매핑)
        - 전용 응답 큐 
        - 메시지 확인 (acknowledgment)
        """
        # 에이전트 큐 설정
        agent_queue = "test_agent_queue"
        rabbitmq_channel.queue_declare(queue=agent_queue, durable=True)
        
        # 응답 큐 설정
        response_queue = "test_response_queue"
        rabbitmq_channel.queue_declare(queue=response_queue, durable=True)
        
        # 수신 메시지 및 이벤트
        agent_messages = []
        broker_messages = []
        agent_event = threading.Event()
        broker_event = threading.Event()
        
        # 에이전트 콜백 (작업 수신 및 응답 전송)
        def agent_callback(ch, method, properties, body):
            message = json.loads(body)
            agent_messages.append(message)
            
            # 에이전트가 응답 생성
            response = {
                "task_id": message["task_id"],
                "status": "completed",
                "result": f"에이전트가 '{message['action']}' 작업을 처리했습니다."
            }
            
            # 응답 전송
            ch.basic_publish(
                exchange='',
                routing_key=response_queue,
                body=json.dumps(response),
                properties=pika.BasicProperties(
                    correlation_id=properties.correlation_id,
                    content_type='application/json'
                )
            )
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            agent_event.set()
        
        # 브로커 콜백 (응답 수신)
        def broker_callback(ch, method, properties, body):
            broker_messages.append(json.loads(body))
            ch.basic_ack(delivery_tag=method.delivery_tag)
            broker_event.set()
        
        # 소비자 설정
        rabbitmq_channel.basic_consume(queue=agent_queue, on_message_callback=agent_callback)
        rabbitmq_channel.basic_consume(queue=response_queue, on_message_callback=broker_callback)
        
        # 소비 스레드 시작
        consumer_thread = threading.Thread(
            target=lambda: rabbitmq_channel.start_consuming()
        )
        consumer_thread.daemon = True
        consumer_thread.start()
        
        # 브로커에서 에이전트로 태스크 전송
        task = {
            "task_id": "test_task_123",
            "action": "search",
            "params": {"query": "테스트 쿼리"}
        }
        
        correlation_id = "test_corr_id"
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key=agent_queue,
            body=json.dumps(task),
            properties=pika.BasicProperties(
                correlation_id=correlation_id,
                reply_to=response_queue,
                content_type='application/json'
            )
        )
        
        # 양방향 통신 완료 대기 (최대 5초)
        agent_event.wait(timeout=5)
        broker_event.wait(timeout=5)
        
        # 소비 중단
        rabbitmq_channel.stop_consuming()
        consumer_thread.join(timeout=1)
        
        # 결과 확인
        assert len(agent_messages) == 1
        assert agent_messages[0]["task_id"] == "test_task_123"
        
        assert len(broker_messages) == 1
        assert broker_messages[0]["task_id"] == "test_task_123"
        assert broker_messages[0]["status"] == "completed"


# 직접 실행 시 간단한 테스트
if __name__ == "__main__":
    """
    이 스크립트를 직접 실행하면 간단한 RabbitMQ 테스트를 수행합니다.
    pytest 없이도 기본적인 연결 및 메시지 전송을 확인할 수 있습니다.
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
        channel.queue_declare(queue='direct_test_queue')
        
        # 메시지 발행
        message = {"message": "RabbitMQ 직접 테스트"}
        channel.basic_publish(
            exchange='',
            routing_key='direct_test_queue',
            body=json.dumps(message)
        )
        
        print(f"메시지 전송 완료: {message}")
        connection.close()
        
    except Exception as e:
        print(f"RabbitMQ 연결 오류: {str(e)}") 