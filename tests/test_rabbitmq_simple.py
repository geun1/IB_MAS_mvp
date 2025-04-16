"""
RabbitMQ 기본 통신 간소화 테스트 모듈

이 모듈은 RabbitMQ 연결 및 기본 메시지 전송만 테스트합니다.
Docker 환경에서 안정적으로 동작하는 간소화된 테스트입니다.

테스트 실행 방법:
    $ python test_rabbitmq_simple.py
"""

import os
import pika
import json
import time
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# RabbitMQ 연결 설정
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

def test_basic_connection():
    """
    RabbitMQ 기본 연결 테스트
    """
    print("RabbitMQ 연결 테스트 중...")
    
    try:
        # 연결 설정
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            connection_attempts=3,
            retry_delay=2
        )
        
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        print("RabbitMQ 연결 성공!")
        
        # 테스트 큐 선언
        queue_name = "simple_test_queue"
        channel.queue_declare(queue=queue_name, durable=True)
        
        # 메시지 발행
        message = {
            "id": "test_message_1",
            "content": "간단한 RabbitMQ 테스트 메시지",
            "timestamp": time.time()
        }
        
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # 메시지 지속성
                content_type='application/json'
            )
        )
        
        print(f"메시지 전송 완료: {message}")
        
        # 큐 크기 확인
        queue_info = channel.queue_declare(queue=queue_name, passive=True)
        message_count = queue_info.method.message_count
        print(f"큐 '{queue_name}'에 {message_count}개의 메시지가 있습니다")
        
        # 메시지 소비 (1개만)
        method_frame, header_frame, body = channel.basic_get(queue_name)
        
        if method_frame:
            received = json.loads(body)
            print(f"수신된 메시지: {received}")
            channel.basic_ack(method_frame.delivery_tag)
            print("메시지 확인(ACK) 완료")
            
            # 테스트 성공 여부 확인
            assert received["id"] == message["id"]
            print("테스트 성공: 메시지 ID 일치 확인됨")
        else:
            print("큐에서 메시지를 가져오지 못했습니다")
            assert False, "메시지 수신 실패"
        
        # 정리
        channel.queue_delete(queue_name)
        connection.close()
        
        return True
    
    except Exception as e:
        print(f"RabbitMQ 테스트 실패: {str(e)}")
        return False

if __name__ == "__main__":
    result = test_basic_connection()
    
    if result:
        print("RabbitMQ 기본 테스트 성공!")
    else:
        print("RabbitMQ 기본 테스트 실패.") 