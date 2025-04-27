import redis
import json
import time
import hashlib
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from .models import TaskStatus, TaskResult

class TaskStore:
    def __init__(self, redis_url: str, cache_ttl: int = 3600 * 24):
        """
        태스크 상태 및 결과 저장소
        
        Args:
            redis_url: Redis 연결 URL
            cache_ttl: 캐시 유효 기간(초), 기본 24시간
        """
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger("task_store")
        
    def _generate_cache_key(self, role: str, params: Dict[str, Any]) -> str:
        """태스크 캐시 키 생성"""
        # 파라미터를 정렬하여 동일 파라미터에 대해 동일 키 생성
        param_str = json.dumps(params, sort_keys=True)
        key = f"{role}:{hashlib.md5(param_str.encode()).hexdigest()}"
        return key
        
    async def create_task(
        self, 
        task_id: str, 
        role: str, 
        params: Dict[str, Any],
        conversation_id: Optional[str] = None,
        agent_configs: Optional[Dict[str, Dict[str, str]]] = None
    ) -> TaskResult:
        """
        새 태스크 생성
        
        Args:
            task_id: 태스크 ID
            role: 에이전트 역할
            params: 태스크 파라미터
            conversation_id: 대화 ID
            agent_configs: 에이전트 설정

        Returns:
            생성된 태스크
        """
        try:
            # 대화 ID가 없으면 새로 생성
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # 현재 시간
            now = time.time()
            
            # 태스크 데이터 생성
            task_data = {
                "task_id": task_id,
                "role": role,
                "params": params,
                "conversation_id": conversation_id,
                "status": TaskStatus.PENDING,
                "created_at": now,
                "updated_at": now
            }
            
            # 에이전트 설정이 있으면 추가
            if agent_configs:
                task_data["agent_configs"] = agent_configs
            
            # Redis에 태스크 저장
            self.redis.set(
                f"task:{task_id}", 
                json.dumps(task_data),
                ex=self.cache_ttl
            )
            
            # 대화 ID에 대한 태스크 인덱스 추가
            self.redis.sadd(f"conversation:{conversation_id}:tasks", task_id)
            self.redis.expire(f"conversation:{conversation_id}:tasks", self.cache_ttl)
            
            # 태스크 결과 변환하여 반환
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.PENDING,
                role=role,
                params=params,
                created_at=now,
                updated_at=now,
                agent_configs=agent_configs
            )
            
        except Exception as e:
            self.logger.error(f"태스크 생성 중 오류: {str(e)}")
            raise ValueError(f"태스크 생성 실패: {str(e)}")
        
    async def update_task_status(self, task_id: str, status: TaskStatus, 
                               agent_id: Optional[str] = None, 
                               result: Optional[Dict[str, Any]] = None,
                               error: Optional[str] = None) -> Optional[TaskResult]:
        """태스크 상태 업데이트"""
        task_key = f"task:{task_id}"
        task_data = self.redis.get(task_key)
        
        if not task_data:
            self.logger.warning(f"Task not found: {task_id}")
            return None
            
        task_dict = json.loads(task_data)
        task = TaskResult(**task_dict)
        
        # 이전 상태 기록
        old_status = task.status
        
        # 새 상태로 업데이트
        task.status = status
        task.updated_at = time.time()
        
        if agent_id:
            task.agent_id = agent_id
            
        if result is not None:
            task.result = result
            
        if error is not None:
            task.error = error
            
        if status == TaskStatus.COMPLETED or status == TaskStatus.FAILED:
            task.completed_at = time.time()
            task.execution_time = task.completed_at - task.created_at
            
            # 완료된 태스크는 캐시에 저장
            if status == TaskStatus.COMPLETED and task.result and not task.cache_hit:
                cache_key = self._generate_cache_key(task.role, task.params)
                self.redis.set(f"cache:{cache_key}", json.dumps(task.dict()), ex=self.cache_ttl)
        
        # Redis 트랜잭션으로 상태 및 인덱스 업데이트
        pipe = self.redis.pipeline()
        pipe.set(task_key, json.dumps(task.dict()))
        
        # 이전 상태에서 제거
        if old_status == TaskStatus.PENDING:
            pipe.zrem("tasks:pending", task_id)
        elif old_status == TaskStatus.PROCESSING:
            pipe.zrem("tasks:processing", task_id)
            
        # 새 상태에 추가
        if status == TaskStatus.PROCESSING:
            pipe.zadd("tasks:processing", {task_id: time.time()})
        elif status == TaskStatus.COMPLETED:
            pipe.zadd("tasks:completed", {task_id: time.time()})
        elif status == TaskStatus.FAILED:
            pipe.zadd("tasks:failed", {task_id: time.time()})
            
        pipe.execute()
        return task
        
    async def get_task(self, task_id: str) -> Optional[TaskResult]:
        """태스크 상태 조회"""
        task_data = self.redis.get(f"task:{task_id}")
        if task_data:
            return TaskResult(**json.loads(task_data))
        return None
        
    async def list_tasks(self, status: Optional[str] = None, 
                        role: Optional[str] = None, 
                        page: int = 1, 
                        page_size: int = 20) -> Tuple[List[TaskResult], int]:
        """태스크 목록 조회"""
        task_ids = set()
        
        # 상태별 필터링
        if status:
            if status == TaskStatus.PENDING:
                ids = self.redis.zrange("tasks:pending", 0, -1)
            elif status == TaskStatus.PROCESSING:
                ids = self.redis.zrange("tasks:processing", 0, -1)
            elif status == TaskStatus.COMPLETED:
                ids = self.redis.zrange("tasks:completed", 0, -1)
            elif status == TaskStatus.FAILED:
                ids = self.redis.zrange("tasks:failed", 0, -1)
            else:
                ids = []
                
            task_ids.update(ids)
            
        # 역할별 필터링
        if role:
            role_ids = self.redis.smembers(f"tasks:role:{role}")
            if task_ids:
                task_ids = task_ids.intersection(role_ids)
            else:
                task_ids = role_ids
                
        # 필터 없는 경우 모든 태스크
        if not task_ids and not status and not role:
            # 모든 태스크 ID 가져오기 (키 패턴 스캔)
            cursor = 0
            task_ids = set()
            while True:
                cursor, keys = self.redis.scan(cursor, match="task:*", count=1000)
                for key in keys:
                    if key.startswith("task:"):
                        task_id = key.split(":", 1)[1]
                        task_ids.add(task_id)
                if cursor == 0:
                    break
        
        # 총 태스크 수
        total = len(task_ids)
        
        # 페이지네이션
        start = (page - 1) * page_size
        end = start + page_size
        
        # 페이지 태스크 ID 목록
        page_ids = list(task_ids)[start:end]
        
        # 태스크 정보 조회
        tasks = []
        for task_id in page_ids:
            task_data = self.redis.get(f"task:{task_id}")
            if task_data:
                tasks.append(TaskResult(**json.loads(task_data)))
                
        return tasks, total 

    async def get_tasks_by_conversation(
        self, conversation_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[TaskResult], int]:
        """
        대화 ID로 태스크 검색
        
        Args:
            conversation_id: 대화 ID
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지 크기
            
        Returns:
            태스크 목록, 총 태스크 수
        """
        try:
            # 대화 ID로 태스크 ID 검색
            task_ids = set()
            cursor = 0
            
            while True:
                cursor, keys = self.redis.scan(
                    cursor, match=f"task:*:{conversation_id}", count=1000
                )
                for key in keys:
                    if key.startswith("task:"):
                        task_id = key.split(":", 1)[1]
                        task_ids.add(task_id)
                if cursor == 0:
                    break
                
            # 태스크 정보 조회
            tasks = []
            for task_id in task_ids:
                task_data = self.redis.get(f"task:{task_id}")
                if task_data:
                    tasks.append(TaskResult(**json.loads(task_data)))
                    
            # 정렬 (최신순)
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            
            # 페이지네이션
            total = len(tasks)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_tasks = tasks[start_idx:end_idx]
            
            return page_tasks, total
            
        except Exception as e:
            self.logger.error(f"대화 ID로 태스크 검색 중 오류: {str(e)}")
            return [], 0 