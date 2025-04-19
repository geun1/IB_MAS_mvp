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
        try:
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            self.logger.info("RabbitMQ 연결 성공")
        except Exception as e:
            self.logger.error(f"RabbitMQ 연결 실패: {str(e)}")
            raise
    
    async def publish_task(self, queue_name: str, task_data: Dict[str, Any]) -> bool:
        """태스크를 큐에 발행"""
        try:
            if not self.channel:
                await self.connect()
                
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
                await self.connect()
                
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