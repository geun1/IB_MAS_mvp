import json
import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable, Optional
import aio_pika

class QueueManager:
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
        self.logger = logging.getLogger("queue_manager")
    
    async def connect(self):
        """RabbitMQ 연결 설정"""
        max_retries = 10
        retry_count = 0
        retry_delay = 5  # 초 단위
        
        while retry_count < max_retries:
            try:
                self.logger.info(f"RabbitMQ 연결 시도 중... ({retry_count+1}/{max_retries}) URL: {self.rabbitmq_url}")
                self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
                self.channel = await self.connection.channel()
                self.logger.info("RabbitMQ 연결 성공")
                return
            except Exception as e:
                retry_count += 1
                self.logger.warning(f"RabbitMQ 연결 시도 {retry_count}/{max_retries} 실패: {str(e)}")
                
                if retry_count < max_retries:
                    # 다음 시도 전에 대기 (지수 백오프)
                    wait_time = retry_delay * (2 ** (retry_count - 1))
                    self.logger.info(f"{wait_time}초 후 다시 시도합니다...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"최대 재시도 횟수 초과, RabbitMQ 연결 실패: {str(e)}")
                    # 연결 실패를 던지지 않고 로깅만 함 (애플리케이션이 계속 실행될 수 있도록)
        
        self.logger.warning("RabbitMQ 연결 없이 제한된 기능으로 계속 실행합니다")
    
    async def publish_task(self, queue_name: str, task_data: Dict[str, Any]) -> bool:
        """태스크를 큐에 발행"""
        try:
            if not self.channel:
                self.logger.warning("RabbitMQ 채널이 없습니다. 연결을 재시도합니다.")
                await self.connect()
                
            if not self.channel:
                self.logger.error("RabbitMQ 채널을 설정할 수 없습니다. 메시지를 발행할 수 없습니다.")
                return False
                
            queue = await self.channel.declare_queue(queue_name, durable=True)
            message_body = json.dumps(task_data).encode()
            
            await self.channel.default_exchange.publish(
                aio_pika.Message(body=message_body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=queue_name
            )
            
            return True
        except Exception as e:
            self.logger.error(f"태스크 발행 실패: {str(e)}")
            return False
    
    async def consume_tasks(self, queue_name: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        """태스크 큐 소비"""
        try:
            if not self.channel:
                self.logger.warning("RabbitMQ 채널이 없습니다. 연결을 재시도합니다.")
                await self.connect()
                
            if not self.channel:
                self.logger.error("RabbitMQ 채널을 설정할 수 없습니다. 메시지를 소비할 수 없습니다.")
                return
                
            queue = await self.channel.declare_queue(queue_name, durable=True)
            
            async def process_message(message):
                async with message.process():
                    try:
                        data = json.loads(message.body.decode())
                        await callback(data)
                    except Exception as e:
                        self.logger.error(f"메시지 처리 오류: {str(e)}")
            
            await queue.consume(process_message)
            
        except Exception as e:
            self.logger.error(f"큐 소비 설정 실패: {str(e)}") 